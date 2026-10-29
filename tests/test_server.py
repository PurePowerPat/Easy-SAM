"""API: the local server, background weather retrieval, a run that reads the cache, and the exports
(no internet: NSRDB requests return synthetic files)."""
import io
import json
import threading
import time
import urllib.error
import urllib.request
import zipfile

import pytest

from ppe_sam import __version__, config, jobs, server, weather

YEARS = [2010, 2011, 2012]

DESIGN = {"location_mode": "coords", "lat": "33.4", "lon": "-112.0", "interval": "60", "module_source": "cec",
          "module_name": "TEST Bifacial 530W", "isc_datasheet": "13.9", "inverter_name": "TEST Central 2500kW",
          "modules_per_string": "26", "system_voltage": "1500",
          "racking": "tracker", "azimuth": "180", "rotlim": "60", "orientation": "portrait",
          "modules_high": "1", "modules_across": "26", "rows": "1", "self_shading": "standard",
          "gcr_mode": "pitch", "pitch": "236.22",
          "pitch_units": "in", "bifaciality_base": "70", "bifaciality_tol": "5", "bifacial_gain": "10",
          "ground_clearance": "98.4", "ground_clearance_units": "in"}
REQUESTS = []      # (year, lat, lon) of every (fake) NSRDB request


@pytest.fixture(scope="module", autouse=True)
def app(tmp_path_factory):
    """The app on a free port, with its own data folder and a slow fake NSRDB (so jobs overlap)."""
    def fake_request(year, lat, lon, interval):
        REQUESTS.append((year, lat, lon))
        time.sleep(0.4)
        return weather._selftest_csv(year, lat, lon, interval).replace("\n", "\r\n").encode()

    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("LOCALAPPDATA", str(tmp_path_factory.mktemp("appdata")))
        mp.setattr(weather, "requested_years", lambda: list(YEARS))
        mp.setattr(config, "NSRDB_MIN_SECONDS_BETWEEN_REQUESTS", 0)
        mp.setattr(weather, "_request", fake_request)
        httpd = server.make_server(0)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        yield f"127.0.0.1:{httpd.server_address[1]}"
        httpd.shutdown()
        httpd.server_close()


def request(app, method, path, body=None, headers=None, raw=None):
    data = raw if raw is not None else (None if body is None else json.dumps(body).encode())
    req = urllib.request.Request(f"http://{app}{path}", method=method, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), dict(e.headers)


def call(app, method, path, body=None):
    code, data, _ = request(app, method, path, body)
    return code, json.loads(data)


def wait(app, job_id, proceed=True):
    while True:
        s = call(app, "GET", f"/api/job/{job_id}")[1]
        if s["status"] == "confirm":
            call(app, "POST", f"/api/job/{job_id}/continue", {"proceed": proceed})
        if s["status"] in ("done", "error", "cancelled"):
            return s
        time.sleep(0.2)


def test_info_and_library_lookup(app):
    info = call(app, "GET", "/api/info")[1]
    assert info["version"] == __version__ and info["cec_tip"]
    assert [r["name"] for r in call(app, "GET", "/api/modules?name=TEST%20Mono%20400W")[1]] == ["TEST Mono 400W"]
    assert call(app, "GET", "/api/modules?name=TEST%20Mono")[1] == []                     # exact names only
    assert len(call(app, "GET", "/api/inverters?name=TEST%20Central%202500kW")[1]) == 1


def test_static_files_have_explicit_types(app):
    code, html, hdr = request(app, "GET", "/")
    assert code == 200 and hdr["Content-Type"].startswith("text/html")
    assert b"/static/app.js" in html and b"/static/app.css" in html
    assert request(app, "GET", "/static/app.js")[2]["Content-Type"].startswith("text/javascript")
    assert request(app, "GET", "/static/app.css")[2]["Content-Type"].startswith("text/css")
    assert request(app, "GET", "/static/../server.py")[0] == 404


def test_only_the_apps_own_page_may_call_it(app):
    port = app.split(":")[1]
    assert request(app, "POST", "/api/validate", {}, {"Origin": f"http://{app}"})[0] == 200
    assert request(app, "POST", "/api/validate", {}, {"Origin": f"http://localhost:{port}"})[0] == 200
    assert request(app, "POST", "/api/cache/clear", {}, {"Origin": "https://evil.example"})[0] == 403
    assert request(app, "GET", "/api/info", headers={"Host": f"evil.example:{port}"})[0] == 403


@pytest.mark.parametrize("raw", [b"{not json", b"[1, 2]", b'"text"'])
def test_bad_request_body_is_400(app, raw):
    code, data, _ = request(app, "POST", "/api/run", raw=raw)
    assert code == 400 and json.loads(data)["error"]


def test_validate_defaults_self_shading_to_ppe_standard(app):
    v = call(app, "POST", "/api/validate", {k: v for k, v in DESIGN.items() if k != "self_shading"})[1]
    assert v["ok"] and dict(v["groups"][4][1])["Self-shading"] == "Standard", v


def test_run_reads_weather_retrieved_earlier(app):
    jw = call(app, "POST", "/api/weather", {"lat": 33.4, "lon": -112.0, "interval": 60})[1]["job"]
    assert wait(app, jw)["status"] == "done"
    n0 = len(REQUESTS)
    s = wait(app, call(app, "POST", "/api/run", DESIGN)[1]["job"])
    assert s["status"] == "done", s["error"]
    assert len(REQUESTS) == n0                                              # everything came from the cache
    assert not any("Parallel run unavailable" in line for line in s["log"])  # the process pool worked
    assert s["result"]["nec"]["isc_stc_module"] == 13.9 and round(s["result"]["nec"]["floor_70pct"], 4) == 13.3788
    sh = [r for r in s["result"]["inputs_used"] if r["input"] == "Self-shading"][0]
    assert sh["value"] == "Standard" and sh["section"] == "Settings"
    again = call(app, "POST", "/api/weather", {"lat": 33.4, "lon": -112.0, "interval": 60})[1]["job"]
    assert again != jw and wait(app, again)["weather"]["cached"] == len(YEARS)   # finished jobs are not reused


def test_run_waits_for_running_retrieval_then_exports(app):
    jw = call(app, "POST", "/api/weather", {"lat": 35.0, "lon": -110.0, "interval": 60})[1]["job"]
    time.sleep(0.2)
    design = {**DESIGN, "lat": "35.0", "lon": "-110.0", "self_shading": "none"}
    jr = call(app, "POST", "/api/run", design)[1]["job"]
    s = wait(app, jr)
    assert s["status"] == "done", s["error"]
    assert len([r for r in REQUESTS if r[1] == 35.0]) == len(YEARS)          # downloaded once, not twice
    assert wait(app, jw)["status"] == "done"

    code, data, _ = request(app, "GET", f"/api/job/{jr}/export/all")
    assert code == 200 and len(zipfile.ZipFile(io.BytesIO(data)).namelist()) == 7
    code, data, hdr = request(app, "GET", f"/api/job/{jr}/export/sam_json")
    sam, year = json.loads(data), s["result"]["sam_json_year"]
    assert code == 200 and sam["compute_module_0"] == "pvsamv1" and sam["subarray1_shade_mode"] == 0
    assert sam["solar_resource_file"].endswith(f"/{year}.csv")
    assert f"SAM_case_inputs_{year}.json" in hdr["Content-Disposition"]
    code, data, _ = request(app, "GET", f"/api/job/{jr}/export/inputs_json")
    saved = json.loads(data)
    assert code == 200 and saved["format"] == "PPE SAM inputs" and saved["app_version"] == __version__
    assert saved["inputs"] == design                                         # exactly what was run


def test_finished_jobs_are_pruned(app):
    with jobs._jobs_lock:
        kept = [j for j in jobs.JOBS.values() if j.kind == "weather"]
        prefetch = [j for j in jobs.PREFETCH.values()]
    assert len(kept) <= jobs.MAX_KEPT_JOBS
    assert all(j.id in jobs.JOBS for j in prefetch)                          # no stale prefetch entries
