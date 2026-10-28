"""Download every available NSRDB PSM v4 (GOES Aggregated) year for one site.

One CSV per year from the direct-CSV endpoint (single point, single year per request).
Files are cached locally so re-running a project (or a weather retrieval started early from the
Configure page) does not re-download.

The cache is organised by NSRDB grid cell ("Location ID" in each file's header), not by the exact
coordinates entered: every site inside the same cell gets identical NSRDB data, so a nearby site
reuses the cached years after a single download. locations.json remembers which cell each set of
coordinates belongs to. Folders from older versions (named by coordinates) are moved into the
grid-cell folders the first time they are used.
"""
import csv
import datetime as dt
import io
import json
import os
import re
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import config

_last_request = [0.0]
_throttle_lock = threading.Lock()   # weather prefetch and a run can download at the same time
_cache_lock = threading.Lock()      # guards locations.json and folder moves
INDEX_FILE = "locations.json"


class NsrdbAccessError(RuntimeError):
    """NSRDB refused the API key or the request limit is used up. Stops the download: retrying every
    remaining year would fail the same way (and would wrongly report the years as "not available")."""


def expected_rows(interval: int) -> int:
    return 8760 * (60 // interval)


def requested_years():
    return list(range(config.NSRDB_FIRST_YEAR, config.nsrdb_last_year() + 1))


def site_key(lat: float, lon: float, interval: int) -> str:
    """One key per (lat, lon, time step). Also the cache folder name used before v0.3.0."""
    return f"{float(lat):.6f}_{float(lon):.6f}_psm4_{int(interval)}"


def _clean_location_id(v):
    v = (v or "").strip()
    return v if re.fullmatch(r"[A-Za-z0-9_-]{1,40}", v) else None


def _header_location_id(text: str):
    """NSRDB 'Location ID' from the first two (header) lines of a weather file, or None."""
    rows = list(csv.reader(io.StringIO("\n".join(text.splitlines()[:2]))))
    if len(rows) < 2:
        return None
    info = {k.strip(): v.strip() for k, v in zip(rows[0], rows[1])}
    return _clean_location_id(info.get("Location ID"))


def _file_location_id(path: Path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return _header_location_id(fh.readline() + fh.readline())
    except OSError:
        return None


def _location_folder(location_id: str, interval: int) -> Path:
    return config.weather_cache_dir() / f"loc_{location_id}_psm4_{int(interval)}"


def _read_index() -> dict:
    try:
        with open(config.weather_cache_dir() / INDEX_FILE, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_index(index: dict):
    path = config.weather_cache_dir() / INDEX_FILE
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")       # two app windows never share a tmp file
    tmp.write_text(json.dumps(index, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _migrate_legacy(legacy: Path, key: str, interval: int, index: dict):
    """Move a pre-v0.3.0 coordinate folder into its grid-cell folder (no re-download).
    Returns (folder, location id)."""
    valid = [p for p in sorted(legacy.glob("*.csv")) if validate_file(p, interval)]
    loc = _file_location_id(valid[0]) if valid else None
    if loc is None:
        return legacy, None                # nothing usable to move: keep using the folder as before
    dest = _location_folder(loc, interval)
    dest.mkdir(parents=True, exist_ok=True)
    for p in valid:
        target = dest / p.name
        if _file_location_id(p) == loc and not (target.exists() and validate_file(target, interval)):
            try:
                os.replace(p, target)
            except OSError:
                pass                       # left behind: that year is downloaded again when needed
    shutil.rmtree(legacy, ignore_errors=True)
    index[key] = loc
    _write_index(index)
    return dest, loc


def _known_folder(lat: float, lon: float, interval: int):
    """(cache folder, location id) for these coordinates if already known, else (None, None)."""
    key = site_key(lat, lon, interval)
    with _cache_lock:
        index = _read_index()
        loc = _clean_location_id(index.get(key))
        if loc:
            folder = _location_folder(loc, interval)
            folder.mkdir(parents=True, exist_ok=True)
            return folder, loc
        legacy = config.weather_cache_dir() / key
        if legacy.is_dir():
            return _migrate_legacy(legacy, key, interval, index)
    return None, None


def _assign_folder(lat: float, lon: float, interval: int, loc):
    """Remember the grid cell named by a downloaded file and return its folder."""
    key = site_key(lat, lon, interval)
    with _cache_lock:
        if loc is None:                    # no Location ID in the file: keep this site's files to itself
            folder = config.weather_cache_dir() / key
        else:
            index = _read_index()
            index[key] = loc
            _write_index(index)
            folder = _location_folder(loc, interval)
        folder.mkdir(parents=True, exist_ok=True)
        return folder


def cache_info() -> dict:
    root = config.weather_cache_dir()
    files = [p for p in root.rglob("*.csv") if p.is_file()]
    sites = [p for p in root.iterdir() if p.is_dir()]
    return {"path": str(root), "sites": len(sites), "files": len(files),
            "mb": round(sum(p.stat().st_size for p in files) / 1e6, 1)}


def clear_cache() -> dict:
    before = cache_info()
    root = config.weather_cache_dir()
    for child in root.iterdir():
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            child.unlink(missing_ok=True)
    return before


def validate_file(path: Path, interval: int) -> bool:
    """Header (2 rows) + column row + exactly 8760 (60-min) / 17520 (30-min) data rows."""
    try:
        with open(path, newline="", encoding="utf-8", errors="replace") as fh:
            lines = sum(1 for _ in fh)
        return lines - 3 == expected_rows(interval)
    except OSError:
        return False


def _throttle():
    with _throttle_lock:
        wait = config.NSRDB_MIN_SECONDS_BETWEEN_REQUESTS - (time.time() - _last_request[0])
        if wait > 0:
            time.sleep(wait)
        _last_request[0] = time.time()


def _request(year: int, lat: float, lon: float, interval: int) -> bytes:
    params = {
        "api_key": config.NSRDB_API_KEY, "wkt": f"POINT({lon} {lat})", "names": str(year),
        "interval": str(interval), "attributes": config.NSRDB_ATTRIBUTES,
        "utc": "false",          # local standard time, same as SAM's normal download
        "leap_day": "false",     # 8760 rows/yr, matches the existing workbook layout
        "email": config.NSRDB_EMAIL,
    }
    last_err = None
    outcomes = []                  # per host: "refused" (401/403), "limited" (429) or "error"
    for host in config.NSRDB_HOSTS:
        url = host + config.NSRDB_PATH + "?" + urllib.parse.urlencode(params)
        outcome = "error"
        for attempt in range(4):
            _throttle()
            try:
                with urllib.request.urlopen(url, timeout=180) as r:
                    return r.read()
            except urllib.error.HTTPError as e:
                body = e.read()[:500].decode("utf-8", "replace")
                last_err = f"HTTP {e.code}: {body}"
                if e.code in (401, 403):
                    outcome = "refused"
                    break                  # retrying will not help; try the other host
                if e.code == 429 or e.code >= 500:
                    outcome = "limited" if e.code == 429 else "error"
                    time.sleep(5 * (attempt + 1))
                    continue
                raise LookupError(last_err) from e
            except (urllib.error.URLError, TimeoutError) as e:
                outcome, last_err = "error", str(e)
                time.sleep(3 * (attempt + 1))
        outcomes.append(outcome)
    if all(o == "refused" for o in outcomes):
        raise NsrdbAccessError(f"NSRDB refused the app's API key ({last_err[:160]}). "
                               "The key may be invalid or disabled: contact the app owner.")
    if all(o in ("refused", "limited") for o in outcomes):
        raise NsrdbAccessError(f"NSRDB request limit reached ({last_err[:160]}). "
                               "Wait an hour, then run again.")
    raise ConnectionError(last_err or "NSRDB request failed")


def nsrdb_site_info(path: Path) -> dict:
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        rdr = csv.reader(fh)
        keys, vals = next(rdr), next(rdr)
    return {k.strip(): v.strip() for k, v in zip(keys, vals)}


def download_all(lat, lon, interval, log, cancelled=lambda: False, on_year=None):
    """Return (list of (year, path), list of failed years).

    on_year(year, status): "cached" | "downloaded" | "unavailable" | "failed" (progress display).
    """
    folder, folder_loc = _known_folder(lat, lon, interval)   # None until a download names the grid cell
    if folder_loc:
        log(f"NSRDB grid cell {folder_loc}: cached years are shared with every site in this cell")
    report = on_year or (lambda y, s: None)
    results, errors = [], []
    for year in requested_years():
        if cancelled():
            raise InterruptedError("Cancelled")
        if folder is not None:
            path = folder / f"{year}.csv"
            if path.exists() and validate_file(path, interval):
                log(f"{year}: using cached weather file")
                results.append((year, path)); report(year, "cached")
                continue
        try:
            data = _request(year, lat, lon, interval)
        except LookupError as e:
            log(f"{year}: not available ({str(e)[:120]})"); report(year, "unavailable")
            continue
        except ConnectionError as e:
            errors.append(year); log(f"{year}: download FAILED ({str(e)[:160]})"); report(year, "failed")
            continue
        except NsrdbAccessError as e:
            log(f"{year}: download STOPPED. {e}")
            raise
        text = data.decode("utf-8", "replace")
        if not text.lstrip().startswith(("Source", "\"Source")):
            log(f"{year}: unexpected response, skipped ({text[:120]!r})"); report(year, "unavailable")
            continue
        loc = _header_location_id(text)
        if folder is None:
            folder, folder_loc = _assign_folder(lat, lon, interval, loc), loc
            if loc:
                log(f"NSRDB grid cell {loc}: cached years are shared with every site in this cell")
        target = folder
        if folder_loc and loc != folder_loc:   # never expected; keep each file with its own grid cell
            log(f"WARNING: {year} file is for NSRDB grid cell {loc}, expected {folder_loc}.")
            target = _location_folder(loc, interval) if loc else config.weather_cache_dir() / site_key(lat, lon, interval)
            target.mkdir(parents=True, exist_ok=True)
        path = target / f"{year}.csv"
        if path.exists() and validate_file(path, interval):   # a nearby site in this cell already has it
            log(f"{year}: using cached weather file (same NSRDB grid cell)")
            results.append((year, path)); report(year, "cached")
            continue
        tmp = path.with_name(f"{year}.{os.getpid()}.{threading.get_ident()}.tmp")   # never a half-written .csv
        tmp.write_text(text, encoding="utf-8", newline="")
        if not validate_file(tmp, interval):
            tmp.unlink(missing_ok=True)
            log(f"{year}: file had the wrong number of rows, skipped"); report(year, "unavailable")
            continue
        os.replace(tmp, path)
        log(f"{year}: downloaded")
        results.append((year, path)); report(year, "downloaded")
    if errors:
        log(f"WARNING: {len(errors)} year(s) failed to download because of a connection problem: "
            f"{', '.join(map(str, errors))}. Re-run to retry them (successful years are cached).")
    return results, errors


def read_timestamps(path: Path):
    out = []
    with open(path, newline="", encoding="utf-8", errors="replace") as fh:
        rdr = csv.reader(fh)
        next(rdr); next(rdr)
        cols = [c.strip() for c in next(rdr)]
        iy, im, idd, ih, imin = (cols.index(c) for c in ("Year", "Month", "Day", "Hour", "Minute"))
        for r in rdr:
            if r:
                out.append(dt.datetime(int(r[iy]), int(r[im]), int(r[idd]), int(r[ih]), int(r[imin])))
    return out


def _selftest_csv(year: int, lat: float, lon: float, interval: int = 60) -> str:
    """Synthetic NSRDB-format file, used only by the automated tests."""
    import math
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["Source", "Location ID", "City", "State", "Country", "Latitude", "Longitude",
                "Time Zone", "Elevation", "Local Time Zone", "Version"])
    loc_id = f"{round((lat + 90) * 25):04d}{round((lon + 180) * 25):04d}"    # fake 0.04° grid cells
    w.writerow(["NSRDB", loc_id, "-", "-", "-", lat, lon, -5, 10, -5, "4.0.0"])
    w.writerow(["Year", "Month", "Day", "Hour", "Minute", "GHI", "DNI", "DHI", "Temperature",
                "Wind Speed", "Wind Direction", "Surface Albedo", "Pressure", "Dew Point",
                "Relative Humidity"])
    t = dt.datetime(year, 1, 1)
    step = dt.timedelta(minutes=interval)
    n = 0
    while n < expected_rows(interval):
        if t.month == 2 and t.day == 29:
            t += step
            continue
        doy = t.timetuple().tm_yday
        hr = t.hour + t.minute / 60 + interval / 120
        decl = 23.45 * math.sin(math.radians(360 * (284 + doy) / 365))
        ha = 15 * (hr - 12)
        cosz = (math.sin(math.radians(lat)) * math.sin(math.radians(decl))
                + math.cos(math.radians(lat)) * math.cos(math.radians(decl)) * math.cos(math.radians(ha)))
        cloud = 0.55 + 0.45 * abs(math.sin(doy * 1.7 + year))
        ghi = max(0.0, 1050 * cosz * cloud) if cosz > 0 else 0.0
        dni = max(0.0, 900 * cloud * cosz ** 0.3) if cosz > 0.05 else 0.0
        dhi = max(0.0, ghi - dni * max(cosz, 0))
        temp = 12 - 14 * math.cos(math.radians(360 * (doy - 15) / 365)) + 6 * max(cosz, 0)
        w.writerow([t.year, t.month, t.day, t.hour, t.minute, round(ghi), round(dni), round(dhi),
                    round(temp, 1), 2.0, 180, 0.2, 1013, round(temp - 6, 1), 60])
        t += step
        n += 1
    return buf.getvalue()
