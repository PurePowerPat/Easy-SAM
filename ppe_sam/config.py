"""Fixed settings. Everything an engineer should NOT change lives here."""
import datetime as _dt
import os
import sys
from pathlib import Path

APP_NAME = "PPE SAM Multi-Year"

# --- NSRDB (NLR Developer Network) -------------------------------------------
NSRDB_API_KEY = "7QfrbzC6P9tzrHCdmPjchqbFjhfQhRzPmpzt7wTG"
NSRDB_EMAIL = "pcarroll@purepower.com"
NSRDB_HOSTS = ["https://developer.nlr.gov", "https://developer.nrel.gov"]  # nlr first, nrel fallback
NSRDB_PATH = "/api/nsrdb/v2/solar/nsrdb-GOES-aggregated-v4-0-0-download.csv"
NSRDB_DATASET = "NSRDB PSM v4 GOES Aggregated"
NSRDB_ATTRIBUTES = ",".join([
    "ghi", "dni", "dhi", "air_temperature", "wind_speed", "wind_direction",
    "surface_albedo", "surface_pressure", "dew_point", "relative_humidity",
])
NSRDB_FIRST_YEAR = 1998
NSRDB_MIN_SECONDS_BETWEEN_REQUESTS = 1.1   # CSV endpoint limit = 1 request / second
RECOMMENDED_MIN_YEARS = 20

# SAM uses the weather-file albedo when it is present and valid (between 0 and 1). If the column is
# missing or a value is invalid (e.g. 0), SAM falls back to the monthly albedo array, which is left
# at SAM's default of 0.2 for every month.
ALBEDO_FALLBACK = 0.2

# --- Address geocoding --------------------------------------------------------
CENSUS_GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
GEOCODER_USER_AGENT = f"PPE-SAM-MultiYear ({NSRDB_EMAIL})"


def nsrdb_last_year() -> int:
    """Last year requested: the previous calendar year."""
    return _dt.date.today().year - 1


# --- CEC libraries (pinned to the commit the user specified) -----------------
SAM_LIB_COMMIT = "cba319ded1c32a7f5b3ac76545a29e1f7181d238"
SAM_LIB_BASE = ("https://raw.githubusercontent.com/NatLabRockies/SAM/"
                f"{SAM_LIB_COMMIT}/deploy/libraries/")
MODULE_LIB_FILE = "CEC Modules.csv"
INVERTER_LIB_FILE = "CEC Inverters.csv"

# --- Racking ----------------------------------------------------------------
RACKING_LABELS = {"tracker": "Single-axis tracker", "fixed": "Fixed-tilt", "carport": "Carport"}
RACKING_TYPES = tuple(RACKING_LABELS)
# Used only for MONOFACIAL runs, where SAM ignores ground clearance.
GROUND_CLEARANCE_DEFAULT_M = {"tracker": 2.5, "fixed": 1.0, "carport": 5.0}
CARPORT_GCR = 0.01
SYSTEM_VOLTAGES = (1000, 1500)
BIFACIAL_TRANSMISSION_DEFAULT = 0.013     # SAM default, guide: "leave at default"
INCH_TO_M = 0.0254
PPE_STANDARD_ROWS = 1

# Self-shading (SAM subarray1_shade_mode): 0 = None, 1 = Standard (non-linear), 2 = Thin film (linear)
SELF_SHADING = {"none": (0, "None"), "standard": (1, "Standard"), "thin_film": (2, "Thin film")}

THIN_FILM_TECH = {"cdte", "cigs", "cis", "a-si", "amorphous", "thin film", "thin-film"}


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def bundle_dir() -> Path:
    return Path(getattr(sys, "_MEIPASS", _base_dir()))


def data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    p = Path(root) / "PPE_SAM_MultiYear"
    p.mkdir(parents=True, exist_ok=True)
    return p


def weather_cache_dir() -> Path:
    p = data_dir() / "weather"
    p.mkdir(parents=True, exist_ok=True)
    return p


def library_search_paths():
    """Order: PPE_SAM_LIB_DIR (tests only) -> next to exe -> bundled copy -> downloaded cache."""
    override = os.environ.get("PPE_SAM_LIB_DIR")
    first = [Path(override)] if override else []
    return first + [_base_dir() / "libraries", bundle_dir() / "libraries", data_dir() / "libraries"]
