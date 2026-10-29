"""Weather download: NSRDB error handling and the grid-cell cache (no internet)."""
import io
import types
import urllib.error

import pytest

from ppe_sam import config, weather


@pytest.fixture
def sleeps(monkeypatch):
    """Record retry waits instead of sleeping."""
    calls = []
    monkeypatch.setattr(weather.time, "sleep", calls.append)
    return calls


@pytest.fixture
def nsrdb(monkeypatch, fast_nsrdb, data_dir, sleeps):
    """Fake NSRDB HTTP: set `codes` to the HTTP error raised by each call (None = success)."""
    fake = types.SimpleNamespace(codes=[], calls=[])

    def urlopen(url, timeout=None):
        fake.calls.append(url)
        code = fake.codes[min(len(fake.calls), len(fake.codes)) - 1]
        if code is None:
            return io.BytesIO(weather._selftest_csv(2010, -10.0, 10.0).encode())
        raise urllib.error.HTTPError("https://example", code, "x", {},
                                     io.BytesIO(b'{"error":{"code":"TEST_%d"}}' % code))
    monkeypatch.setattr(weather.urllib.request, "urlopen", urlopen)
    return fake


@pytest.fixture
def fake_request(monkeypatch, fast_nsrdb, data_dir):
    """Replace the NSRDB request with synthetic files; returns the list of requests made."""
    requests = []

    def request(year, lat, lon, interval):
        requests.append((year, lat, lon))
        return weather._selftest_csv(year, lat, lon, interval).encode()
    monkeypatch.setattr(weather, "_request", request)
    return requests


def download(lat, lon):
    return weather.download_all(lat, lon, 60, lambda msg: None)


def test_key_refused_stops_immediately(nsrdb):
    nsrdb.codes = [403]
    with pytest.raises(weather.NsrdbAccessError, match="API key") as e:
        download(1.0, 1.0)
    assert "TEST_403" in str(e.value)
    assert len(nsrdb.calls) == len(config.NSRDB_HOSTS)          # one try per host, then stop: no other years


def test_rate_limit_stops_after_retries(nsrdb, sleeps):
    nsrdb.codes = [429]
    with pytest.raises(weather.NsrdbAccessError, match="request limit"):
        download(2.0, 2.0)
    n = weather.ATTEMPTS_PER_HOST
    assert len(nsrdb.calls) == n * len(config.NSRDB_HOSTS)      # retried, but only for the first year
    assert sleeps == [5 * (i + 1) for i in range(n - 1)] * len(config.NSRDB_HOSTS)   # no wait after the last try


def test_unavailable_year_and_host_fallback(nsrdb):
    nsrdb.codes = [400, 403, None]                                # 2010 not available
    files, failed = download(3.0, 3.0)                           # 2011: host 1 refuses, host 2 answers
    assert [y for y, _ in files] == [2011, 2012] and failed == [] and len(nsrdb.calls) == 4


def test_sites_in_same_grid_cell_share_the_cache(fake_request):
    a, _ = download(33.40, -112.00)
    assert len(fake_request) == 3
    b, _ = download(33.41, -112.01)                              # same (fake) 0.04° grid cell
    assert len(fake_request) == 4 and [p for _, p in b] == [p for _, p in a]
    download(33.41, -112.01)                                     # coordinates now known: no request at all
    assert len(fake_request) == 4
    c, _ = download(35.0, -110.0)                                # different cell: full download
    assert len(fake_request) == 7 and len({p.parent for _, p in a + c}) == 2
    assert not list(config.weather_cache_dir().rglob("*.tmp"))


def test_old_coordinate_folder_is_moved_not_redownloaded(fake_request, fast_nsrdb):
    lat, lon = 40.0, -75.0
    legacy = config.weather_cache_dir() / weather.site_key(lat, lon, 60)     # v0.2.x folder layout
    legacy.mkdir(parents=True)
    for y in fast_nsrdb:
        (legacy / f"{y}.csv").write_text(weather._selftest_csv(y, lat, lon, 60))
    files, _ = download(lat, lon)
    assert fake_request == [] and len(files) == 3 and not legacy.exists()
    assert all(p.parent.name.startswith("loc_") for _, p in files)
