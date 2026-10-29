"""Address -> latitude / longitude.

Tries the US Census Geocoder first (US street addresses with a house number), then OpenStreetMap
Nominatim (any place name, worldwide). Returns the first match. The coordinates found are filled
into the Latitude / Longitude fields; the weather download always uses those coordinates.
"""
import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from . import config

_lock = threading.Lock()
_last_osm = [0.0]


class GeocodeError(LookupError):
    pass


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": config.GEOCODER_USER_AGENT,
                                               "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _census(address):
    q = urllib.parse.urlencode({"address": address, "benchmark": "Public_AR_Current", "format": "json"})
    data = _get(f"{config.CENSUS_GEOCODER_URL}?{q}")
    matches = (data.get("result") or {}).get("addressMatches") or []
    if not matches:
        return None
    m = matches[0]
    c = m.get("coordinates") or {}
    return {"lat": float(c["y"]), "lon": float(c["x"]), "matched": m.get("matchedAddress", ""),
            "source": "US Census Geocoder"}


def _nominatim(address):
    with _lock:                                   # Nominatim usage policy: max 1 request per second
        wait = 1.1 - (time.time() - _last_osm[0])
        if wait > 0:
            time.sleep(wait)
        _last_osm[0] = time.time()
    q = urllib.parse.urlencode({"q": address, "format": "json", "limit": 1})
    data = _get(f"{config.NOMINATIM_URL}?{q}")
    if not data:
        return None
    m = data[0]
    return {"lat": float(m["lat"]), "lon": float(m["lon"]), "matched": m.get("display_name", ""),
            "source": "OpenStreetMap Nominatim"}


def lookup(address: str) -> dict:
    address = (address or "").strip()
    if len(address) < 3:
        raise GeocodeError("Enter an address.")
    errors = []
    for fn in (_census, _nominatim):
        try:
            r = fn(address)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as e:
            errors.append(f"{fn.__name__.strip('_')}: {e}")
            continue
        if r:
            r["lat"], r["lon"] = round(r["lat"], 6), round(r["lon"], 6)
            return r
    if len(errors) == 2:                          # both services unreachable
        raise GeocodeError("Address lookup failed (no internet connection or the services are unavailable). "
                           "Switch to Coordinates and enter latitude and longitude.")
    raise GeocodeError("No match found for this address. Check the spelling, add the city and state, "
                       "or switch to Coordinates.")
