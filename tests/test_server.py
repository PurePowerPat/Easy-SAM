"""API smoke test: background weather retrieval, then a run that reads the cache (no internet)."""
import io, json, os, sys, tempfile, threading, time, urllib.request, urllib.error, zipfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()
os.environ["PPE_SAM_LIB_DIR"] = str(ROOT / "tests" / "fixtures")
from ppe_sam import config, weather, server  # noqa: E402

YEARS = [2010, 2011, 2012]
REQUESTS = []
weather.requested_years = lambda: list(YEARS)
config.NSRDB_MIN_SECONDS_BETWEEN_REQUESTS = 0


def fake_request(year, lat, lon, interval):
    REQUESTS.append((year, lat, lon))
    time.sleep(0.4)
    return weather._selftest_csv(year, lat, lon, interval).replace("\n", "\r\n").encode()


weather._request = fake_request
PORT = 8799


def call(method, path, body=None, raw=False):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method,
                                 data=None if body is None else json.dumps(body).encode())
    try:
        with urllib.request.urlopen(req) as r:
            data = r.read()
            return r.status, (data, dict(r.headers)) if raw else json.loads(data)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def status_with(method, path, headers):
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", method=method, headers=headers,
                                 data=b"{}" if method == "POST" else None)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def wait(jid, answer=True):
    while True:
        s = call("GET", f"/api/job/{jid}")[1]
        if s["status"] == "confirm":
            call("POST", f"/api/job/{jid}/continue", {"proceed": answer})
        if s["status"] in ("done", "error", "cancelled"):
            return s
        time.sleep(0.2)


DESIGN = {"location_mode": "coords", "lat": "33.4", "lon": "-112.0", "interval": "60", "module_source": "cec",
          "module_name": "TEST Bifacial 530W", "isc_datasheet": "13.9", "inverter_name": "TEST Central 2500kW",
          "modules_per_string": "26", "system_voltage": "1500",
          "racking": "tracker", "azimuth": "180", "rotlim": "60", "orientation": "portrait",
          "modules_high": "1", "modules_across": "26", "rows": "1", "self_shading": "standard",
          "gcr_mode": "pitch", "pitch": "236.22",
          "pitch_units": "in", "bifaciality_base": "70", "bifaciality_tol": "5", "bifacial_gain": "10",
          "ground_clearance": "98.4", "ground_clearance_units": "in"}

if __name__ == "__main__":
    threading.Thread(target=server.serve, kwargs={"open_browser": False, "port": PORT}, daemon=True).start()
    time.sleep(1)
    assert call("GET", "/api/info")[1]["version"] == "0.3.2"
    assert [r["name"] for r in call("GET", "/api/modules?name=TEST%20Mono%20400W")[1]] == ["TEST Mono 400W"]
    assert call("GET", "/api/modules?name=TEST%20Mono")[1] == []                      # exact names only
    assert len(call("GET", "/api/inverters?name=TEST%20Central%202500kW")[1]) == 1
    own = f"http://127.0.0.1:{PORT}"
    assert status_with("POST", "/api/validate", {"Origin": own}) == 200                  # the app's own page
    assert status_with("POST", "/api/validate", {"Origin": f"http://localhost:{PORT}"}) == 200
    assert status_with("POST", "/api/cache/clear", {"Origin": "https://evil.example"}) == 403
    assert status_with("GET", "/api/info", {"Host": f"evil.example:{PORT}"}) == 403
    v = call("POST", "/api/validate", {k: v for k, v in DESIGN.items() if k != "self_shading"})[1]
    assert not v["ok"] and [e["field"] for e in v["errors"]] == ["self_shading"], v
    jw = call("POST", "/api/weather", {"lat": 33.4, "lon": -112.0, "interval": 60})[1]["job"]
    assert wait(jw)["status"] == "done"
    n0 = len(REQUESTS)
    s = wait(call("POST", "/api/run", DESIGN)[1]["job"])
    assert s["status"] == "done", s["error"]
    assert len(REQUESTS) == n0
    assert s["result"]["nec"]["isc_stc_module"] == 13.9 and round(s["result"]["nec"]["floor_70pct"], 4) == 13.3788
    sh = [r for r in s["result"]["inputs_used"] if r["input"] == "Self-shading"][0]
    assert sh["value"] == "Standard" and sh["section"] == "Settings"
    jw2 = call("POST", "/api/weather", {"lat": 35.0, "lon": -110.0, "interval": 60})[1]["job"]
    time.sleep(0.2)
    jr = call("POST", "/api/run", {**DESIGN, "lat": "35.0", "lon": "-110.0", "self_shading": "none"})[1]["job"]
    s = wait(jr)
    assert s["status"] == "done", s["error"]
    assert len([r for r in REQUESTS if r[1] == 35.0]) == 3
    assert wait(jw2)["status"] == "done"
    code, (data, hdr) = call("GET", f"/api/job/{jr}/export/all", raw=True)
    assert code == 200 and len(zipfile.ZipFile(io.BytesIO(data)).namelist()) == 7
    code, (data, hdr) = call("GET", f"/api/job/{jr}/export/sam_json", raw=True)
    sam = json.loads(data)
    assert code == 200 and sam["compute_module_0"] == "pvsamv1" and sam["subarray1_shade_mode"] == 0
    assert sam["solar_resource_file"].endswith(f"/{s['result']['sam_json_year']}.csv")
    assert f"SAM_case_inputs_{s['result']['sam_json_year']}.json" in hdr["Content-Disposition"]
    code, (data, hdr) = call("GET", f"/api/job/{jr}/export/inputs_json", raw=True)
    saved = json.loads(data)
    assert code == 200 and saved["format"] == "PPE SAM inputs" and saved["app_version"] == "0.3.2"
    assert saved["inputs"] == {**DESIGN, "lat": "35.0", "lon": "-110.0", "self_shading": "none"}   # exactly what was run
    print("SERVER TEST PASSED")
