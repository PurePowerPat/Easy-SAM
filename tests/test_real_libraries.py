"""The real CEC library CSVs in the libraries folder parse correctly (skipped if they are not there)."""
from collections import Counter
from pathlib import Path

import pytest

from ppe_sam import config, libraries

REAL = Path(__file__).resolve().parent.parent / "libraries"


@pytest.fixture
def real_libraries(monkeypatch):
    if not (REAL / config.MODULE_LIB_FILE).exists() or not (REAL / config.INVERTER_LIB_FILE).exists():
        pytest.skip("Real CEC libraries not present (run scripts/setup_env.bat)")
    monkeypatch.delenv("PPE_SAM_LIB_DIR")          # the other tests use the small fixture libraries
    monkeypatch.setattr(libraries, "_cache", {})


def test_real_libraries_parse(real_libraries):
    info = libraries.library_info()
    assert Path(info["modules_file"]).parent == REAL
    assert info["module_count"] > 1000 and info["inverter_count"] > 100, "Library parse looks wrong"
    mods = libraries.modules()
    with_gamma = sum(1 for m in mods.values() if m["gamma_r"] is not None)
    assert info["gamma_pmp_column"] is not None and with_gamma >= 0.5 * len(mods)
    techs = Counter(m["technology"] for m in mods.values())
    print(f"\nModules: {info['module_count']:,}   Inverters: {info['inverter_count']:,}   "
          f"Pmp coefficient column: {info['gamma_pmp_column']} ({with_gamma:,} of {len(mods):,} have a value)")
    for t, n in techs.most_common():
        sam_type = libraries.CELLTECH_TEXT.get(libraries.celltech_code(t), "NO MATCH")
        print(f"  {t or '(blank)':<20} {n:>6,} -> {sam_type}")
    # Crystalline modules (nearly all of the library) must map to a SAM cell type.
    unmatched = sum(n for t, n in techs.items() if libraries.celltech_code(t) is None and "thin" not in t.lower())
    assert unmatched == 0
