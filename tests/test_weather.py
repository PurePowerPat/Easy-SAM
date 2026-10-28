"""Weather download: NSRDB error handling and the grid-cell cache (no internet)."""
import io, os, sys, tempfile, urllib.error
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()
from ppe_sam import config, weather  # noqa: E402

YEARS = [2010, 2011, 2012]
weather.requested_years = lambda: list(YEARS)
config.NSRDB_MIN_SECONDS_BETWEEN_REQUESTS = 0
weather.time.sleep = lambda s: None        # no retry waits in tests
REAL_REQUEST, LOG = weather._request, []


def http_error(code, body=b"{}"):
    return urllib.error.HTTPError("https://example", code, "x", {}, io.BytesIO(body))


def fake_urlopen(codes):
    """Each call raises the next HTTP error code; None = success (synthetic weather file)."""
    calls = []

    def urlopen(url, timeout=None):
        calls.append(url)
        code = codes[min(len(calls), len(codes)) - 1]
        if code is None:
            return io.BytesIO(weather._selftest_csv(2010, -10.0, 10.0).encode())   # a cell no other test uses
        raise http_error(code, b'{"error":{"code":"TEST_%d"}}' % code)
    return urlopen, calls


def download(lat, lon):
    return weather.download_all(lat, lon, 60, LOG.append)


def test_key_refused_stops_immediately():
    weather._request = REAL_REQUEST
    weather.urllib.request.urlopen, calls = fake_urlopen([403])
    try:
        download(1.0, 1.0)
        raise AssertionError("expected NsrdbAccessError")
    except weather.NsrdbAccessError as e:
        assert "API key" in str(e) and "TEST_403" in str(e), e
    assert len(calls) == len(config.NSRDB_HOSTS)          # one try per host, then stop: no other years


def test_rate_limit_stops_after_retries():
    weather._request = REAL_REQUEST
    weather.urllib.request.urlopen, calls = fake_urlopen([429])
    try:
        download(2.0, 2.0)
        raise AssertionError("expected NsrdbAccessError")
    except weather.NsrdbAccessError as e:
        assert "request limit" in str(e), e
    assert len(calls) == 4 * len(config.NSRDB_HOSTS)      # retried, but only for the first year


def test_unavailable_year_and_host_fallback():
    weather._request = REAL_REQUEST
    weather.urllib.request.urlopen, calls = fake_urlopen([400, 403, None])   # 2010 not available
    files, failed = download(3.0, 3.0)                     # 2011: host 1 refuses, host 2 answers
    assert [y for y, _ in files] == [2011, 2012] and failed == [] and len(calls) == 4


REQUESTS = []


def fake_request(year, lat, lon, interval):
    REQUESTS.append((year, lat, lon))
    return weather._selftest_csv(year, lat, lon, interval).encode()


def test_sites_in_same_grid_cell_share_the_cache():
    weather._request = fake_request
    REQUESTS.clear()
    a, _ = download(33.40, -112.00)
    assert len(REQUESTS) == 3
    b, _ = download(33.41, -112.01)                        # same (fake) 0.04° grid cell
    assert len(REQUESTS) == 4 and [p for _, p in b] == [p for _, p in a]
    download(33.41, -112.01)                               # coordinates now known: no request at all
    assert len(REQUESTS) == 4
    c, _ = download(35.0, -110.0)                          # different cell: full download
    assert len(REQUESTS) == 7 and len({p.parent for _, p in a + c}) == 2
    assert not list(config.weather_cache_dir().rglob("*.tmp"))


def test_old_coordinate_folder_is_moved_not_redownloaded():
    weather._request = fake_request
    REQUESTS.clear()
    lat, lon = 40.0, -75.0
    legacy = config.weather_cache_dir() / weather.site_key(lat, lon, 60)     # v0.2.x folder layout
    legacy.mkdir(parents=True)
    for y in YEARS:
        (legacy / f"{y}.csv").write_text(weather._selftest_csv(y, lat, lon, 60))
    files, _ = download(lat, lon)
    assert REQUESTS == [] and len(files) == 3 and not legacy.exists()
    assert all(p.parent.name.startswith("loc_") for _, p in files)


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
    print("WEATHER TEST PASSED")
