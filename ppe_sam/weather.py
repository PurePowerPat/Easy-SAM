"""Download every available NSRDB PSM v4 (GOES Aggregated) year for one site.

One CSV per year from the direct-CSV endpoint (single point, single year per request).
Files are cached locally so re-running a project (or a weather retrieval started early from the
Configure page) does not re-download.
"""
import csv
import datetime as dt
import io
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import config

_last_request = [0.0]


def expected_rows(interval: int) -> int:
    return 8760 * (60 // interval)


def requested_years():
    return list(range(config.NSRDB_FIRST_YEAR, config.nsrdb_last_year() + 1))


def site_key(lat: float, lon: float, interval: int) -> str:
    """Same key as the cache folder name: one weather set per (lat, lon, time step)."""
    return f"{float(lat):.6f}_{float(lon):.6f}_psm4_{int(interval)}"


def _site_folder(lat: float, lon: float, interval: int) -> Path:
    p = config.weather_cache_dir() / site_key(lat, lon, interval)
    p.mkdir(parents=True, exist_ok=True)
    return p


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
    for host in config.NSRDB_HOSTS:
        url = host + config.NSRDB_PATH + "?" + urllib.parse.urlencode(params)
        for attempt in range(4):
            _throttle()
            try:
                with urllib.request.urlopen(url, timeout=180) as r:
                    return r.read()
            except urllib.error.HTTPError as e:
                body = e.read()[:500].decode("utf-8", "replace")
                if e.code == 429 or e.code >= 500:
                    last_err = f"HTTP {e.code}: {body}"
                    time.sleep(5 * (attempt + 1))
                    continue
                raise LookupError(f"HTTP {e.code}: {body}") from e
            except (urllib.error.URLError, TimeoutError) as e:
                last_err = str(e)
                time.sleep(3 * (attempt + 1))
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
    folder = _site_folder(lat, lon, interval)
    report = on_year or (lambda y, s: None)
    results, errors = [], []
    for year in requested_years():
        if cancelled():
            raise InterruptedError("Cancelled")
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
        text = data.decode("utf-8", "replace")
        if not text.lstrip().startswith(("Source", "\"Source")):
            log(f"{year}: unexpected response, skipped ({text[:120]!r})"); report(year, "unavailable")
            continue
        path.write_text(text, encoding="utf-8", newline="")
        if not validate_file(path, interval):
            path.unlink(missing_ok=True)
            log(f"{year}: file had the wrong number of rows, skipped"); report(year, "unavailable")
            continue
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
    w.writerow(["NSRDB", "0", "-", "-", "-", lat, lon, -5, 10, -5, "4.0.0"])
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
