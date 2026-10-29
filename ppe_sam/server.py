"""Local-only web server (127.0.0.1) that serves the guided UI and a small JSON API."""
import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from . import __date__, __version__, config, geocode, jobs, libraries, model, report, weather

STATIC = Path(__file__).resolve().parent / "static"
LOCAL_HOSTS = ("127.0.0.1", "localhost")
PORTS = range(8765, 8800)      # first free one is used
# Explicit types: on Windows, mimetypes reads the registry, which can map .js to text/plain.
CONTENT_TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8",
                 ".js": "text/javascript; charset=utf-8", ".png": "image/png", ".svg": "image/svg+xml",
                 ".jpg": "image/jpeg"}


class BadRequest(ValueError):
    pass


def _static_dir():
    bundled = config.bundle_dir() / "ppe_sam" / "static"
    return bundled if bundled.exists() else STATIC


class Handler(BaseHTTPRequestHandler):
    server_version = "PPE-SAM/" + __version__

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json", filename=None):
        data = body if isinstance(body, bytes) else json.dumps(body, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        if filename:
            self.send_header("Content-Disposition",
                             f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}")
        self.end_headers()
        self.wfile.write(data)

    def _from_this_app(self, post=False):
        """Only the app's own page may use it. Rejects other host names (a website pointing its own name at
        127.0.0.1) and, for POSTs, requests sent by other websites (browsers name the sending site in Origin)."""
        allowed = {f"{h}:{self.server.server_address[1]}" for h in LOCAL_HOSTS}
        if self.headers.get("Host") not in allowed:
            return False
        origin = self.headers.get("Origin")
        return not post or origin is None or origin in {f"http://{a}" for a in allowed}

    def _body(self) -> dict:
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError as e:
            raise BadRequest(f"Request body is not valid JSON ({e}).") from e
        if not isinstance(body, dict):
            raise BadRequest("Request body must be a JSON object.")
        return body

    def do_GET(self):  # noqa: N802
        if not self._from_this_app():
            return self._send(403, {"error": "forbidden"})
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ("/", "/index.html"):
                return self._send(200, (_static_dir() / "index.html").read_bytes(), "text/html; charset=utf-8")
            if u.path.startswith("/static/"):
                p = (_static_dir() / u.path[len("/static/"):]).resolve()
                if _static_dir().resolve() in p.parents and p.is_file():
                    return self._send(200, p.read_bytes(),
                                      CONTENT_TYPES.get(p.suffix.lower(), "application/octet-stream"))
                return self._send(404, {"error": "not found"})
            if u.path == "/api/info":
                years = weather.requested_years()
                logo = next((f"/static/{n}" for n in ("logo.png", "logo.svg", "logo.jpg")
                             if (_static_dir() / n).is_file()), None)
                return self._send(200, {"version": __version__, "date": __date__,
                                        "libraries": libraries.library_info(), "logo": logo,
                                        "cec_tip": report.CEC_SPECS_TIP,
                                        "weather": {"dataset": config.NSRDB_DATASET, "first": years[0],
                                                    "last": years[-1], "requested": len(years),
                                                    "min_years": config.RECOMMENDED_MIN_YEARS,
                                                    "albedo_fallback": config.ALBEDO_FALLBACK}})
            if u.path in ("/api/modules", "/api/inverters"):
                if "name" in q:
                    return self._send(200, libraries.exact(u.path[5:], q["name"]))
                return self._send(200, libraries.search(u.path[5:], q.get("q", "")))
            if u.path == "/api/geocode":
                try:
                    return self._send(200, geocode.lookup(q.get("q", "")))
                except geocode.GeocodeError as e:
                    return self._send(404, {"error": str(e)})
            if u.path == "/api/cache":
                return self._send(200, weather.cache_info())
            if u.path.startswith("/api/job/"):
                parts = u.path.split("/")
                job = jobs.get(parts[3]) if len(parts) > 3 else None
                if not job:
                    return self._send(404, {"error": "This run is no longer available. Run the simulation again."})
                if len(parts) == 6 and parts[4] == "export":
                    if job.kind != "run":
                        return self._send(404, {"error": "No results for a weather retrieval."})
                    try:
                        name, data, ctype = job.export(parts[5])
                    except LookupError as e:
                        return self._send(404, {"error": str(e)})
                    return self._send(200, data, ctype, filename=name)
                return self._send(200, job.snapshot())
            return self._send(404, {"error": "not found"})
        except Exception as e:  # noqa: BLE001
            return self._send(500, {"error": str(e)})

    def do_POST(self):  # noqa: N802
        if not self._from_this_app(post=True):
            return self._send(403, {"error": "forbidden"})
        u = urlparse(self.path)
        try:
            if u.path == "/api/validate":
                body = self._body()
                try:
                    return self._send(200, {"ok": True, "errors": [], **jobs.review(body)})
                except model.DesignError as e:
                    return self._send(200, {"ok": False, "errors": e.errors})
            if u.path == "/api/run":
                body = self._body()
                model.validate_design(body)
                return self._send(200, {"job": jobs.start(body).id})
            if u.path == "/api/weather":
                b = self._body()
                try:
                    lat, lon = float(b.get("lat")), float(b.get("lon"))
                    interval = int(float(b.get("interval") or 60))
                except (TypeError, ValueError):
                    return self._send(400, {"error": "Enter a valid latitude and longitude first."})
                if not (-90 <= lat <= 90 and -180 <= lon <= 180) or interval not in (30, 60):
                    return self._send(400, {"error": "Latitude, longitude or time step out of range."})
                return self._send(200, {"job": jobs.start_weather(lat, lon, interval).id})
            if u.path == "/api/cache/clear":
                if jobs.any_active():
                    return self._send(409, {"error": "A job is running. Wait for it to finish or cancel it first."})
                return self._send(200, {"removed": weather.clear_cache(), "now": weather.cache_info()})
            parts = u.path.split("/")
            if len(parts) == 5 and parts[1] == "api" and parts[2] == "job":
                job = jobs.get(parts[3])
                if not job:
                    return self._send(404, {"error": "unknown job"})
                if parts[4] == "continue" and job.kind == "run":
                    job.answer(bool(self._body().get("proceed")))
                elif parts[4] == "cancel":
                    job.cancel()
                return self._send(200, job.snapshot())
            return self._send(404, {"error": "not found"})
        except model.DesignError as e:
            return self._send(400, {"error": str(e), "errors": e.errors})
        except BadRequest as e:
            return self._send(400, {"error": str(e)})
        except Exception as e:  # noqa: BLE001
            return self._send(500, {"error": str(e)})


class _Server(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second socket bind a port that is already in use, so a second app
    # window would share the first one's port instead of moving to the next.
    allow_reuse_address = os.name != "nt"


def make_server(port=None) -> ThreadingHTTPServer:
    """Bind 127.0.0.1 on `port` (0 = any free port), or on the first free port in PORTS."""
    if port is not None:
        return _Server(("127.0.0.1", port), Handler)
    for p in PORTS:
        try:
            return _Server(("127.0.0.1", p), Handler)
        except OSError:            # in use (e.g. a second app window)
            continue
    return _Server(("127.0.0.1", 0), Handler)


def serve(open_browser=True, port=None):
    httpd = make_server(port)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"{config.APP_NAME} v{__version__} running at {url}")
    print("Keep this window open while using the app. Close it to stop the app.")
    threading.Thread(target=libraries.library_info, daemon=True).start()
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    httpd.serve_forever()
