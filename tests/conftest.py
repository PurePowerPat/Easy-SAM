"""Shared test setup. Every test runs offline: fixture CEC libraries, synthetic NSRDB weather and a
temporary data folder (never the real %LOCALAPPDATA%\\PPE_SAM_MultiYear)."""
import os
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"

# Set before ppe_sam is imported: the library cache is filled from the first folder found.
os.environ["PPE_SAM_LIB_DIR"] = str(FIXTURES)
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="ppe_sam_tests_")

from ppe_sam import config, weather  # noqa: E402

YEARS = [2010, 2011, 2012]


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    """A fresh, empty app data folder (weather cache, downloaded libraries) for one test."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return tmp_path


@pytest.fixture
def fast_nsrdb(monkeypatch):
    """Three requested years and no 1-request-per-second throttle."""
    monkeypatch.setattr(weather, "requested_years", lambda: list(YEARS))
    monkeypatch.setattr(config, "NSRDB_MIN_SECONDS_BETWEEN_REQUESTS", 0)
    return YEARS
