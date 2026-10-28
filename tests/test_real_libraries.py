"""Checks that the real CEC library CSVs in the libraries folder parse correctly."""
import sys
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ppe_sam import libraries, model  # noqa: E402

if __name__ == "__main__":
    if not (ROOT / "libraries" / "CEC Modules.csv").exists():
        print("Real libraries not present - skipped")
        sys.exit(0)
    info = libraries.library_info()
    print(f"Modules: {info['module_count']:,}   Inverters: {info['inverter_count']:,}")
    assert info["module_count"] > 1000 and info["inverter_count"] > 100, "Library parse looks wrong"
    mods = libraries.modules()
    with_gamma = sum(1 for m in mods.values() if m["gamma_r"] is not None)
    print(f"Pmp coefficient column: {info['gamma_pmp_column'] or 'NOT FOUND'} ({with_gamma:,} of {len(mods):,} have a value)")
    assert info["gamma_pmp_column"] is not None and with_gamma >= 0.5 * len(mods)
    for t, n in Counter(m["technology"] for m in mods.values()).most_common():
        c = model.celltech_code(t)
        print(f"  {t or '(blank)':<20} {n:>6,} -> {model.CELLTECH_TEXT.get(c, 'NO MATCH')}")
    print("REAL LIBRARY TEST PASSED")
