"""Load the SAM CEC module and inverter libraries (CSV files from the SAM repo).

SAM library CSVs have three header rows (names, units, SSC names); data starts on row 4.
"""
import csv
import threading
import urllib.request
from pathlib import Path

from . import config

_lock = threading.Lock()
_cache = {}

# Pmp temperature coefficient (%/C): "gamma_pmp" in the current library, "gamma_r" in older files.
GAMMA_PMP_COLUMNS = ("gamma_pmp", "gamma_r")


def _f(v, default=None):
    try:
        if v is None or str(v).strip() == "":
            return default
        return float(v)
    except ValueError:
        return default


def _first(r, names):
    for n in names:
        v = _f(r.get(n))
        if v is not None:
            return v
    return None


def _locate(filename: str) -> Path:
    for folder in config.library_search_paths():
        p = folder / filename
        if p.exists() and p.stat().st_size > 200:
            return p
    target = config.data_dir() / "libraries"
    target.mkdir(parents=True, exist_ok=True)
    dest = target / filename
    url = config.SAM_LIB_BASE + urllib.request.quote(filename)
    try:
        with urllib.request.urlopen(url, timeout=60) as r, open(dest, "wb") as fh:
            fh.write(r.read())
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Could not find or download '{filename}'. Download it from\n{url}\n"
            f"and place it in: {config.library_search_paths()[0]}\n({exc})") from exc
    return dest


def _read(filename: str):
    path = _locate(filename)
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as fh:
        rows = list(csv.reader(fh))
    header = [h.strip() for h in rows[0]]
    data = []
    for r in rows[1:]:
        if not r or not r[0].strip():
            continue
        first = r[0].strip()
        if first in ("Units", "[0]") or first.startswith("["):
            continue
        data.append({header[i]: (r[i].strip() if i < len(r) else "") for i in range(len(header))})
    return data, path, header


def _is_thin_film(tech: str) -> bool:
    t = (tech or "").strip().lower()
    return any(k in t for k in config.THIN_FILM_TECH)


def modules():
    with _lock:
        if "modules" not in _cache:
            raw, path, header = _read(config.MODULE_LIB_FILE)
            out = {}
            for r in raw:
                isc = _f(r.get("I_sc_ref"))
                if isc is None:
                    continue
                m = {
                    "name": r["Name"], "manufacturer": r.get("Manufacturer", ""),
                    "technology": r.get("Technology", ""),
                    "bifacial": int(_f(r.get("Bifacial"), 0) or 0),
                    "stc": _f(r.get("STC")), "area": _f(r.get("A_c")),
                    "length": _f(r.get("Length")), "width": _f(r.get("Width")),     # metres
                    "n_s": _f(r.get("N_s")), "i_sc_ref": isc,
                    "v_oc_ref": _f(r.get("V_oc_ref")), "i_mp_ref": _f(r.get("I_mp_ref")),
                    "v_mp_ref": _f(r.get("V_mp_ref")), "alpha_sc": _f(r.get("alpha_sc")),
                    "beta_oc": _f(r.get("beta_oc")),
                    "gamma_r": _first(r, GAMMA_PMP_COLUMNS),   # Pmp temperature coefficient (%/C)
                    "t_noct": _f(r.get("T_NOCT")), "a_ref": _f(r.get("a_ref")),
                    "i_l_ref": _f(r.get("I_L_ref")), "i_o_ref": _f(r.get("I_o_ref")),
                    "r_s": _f(r.get("R_s")), "r_sh_ref": _f(r.get("R_sh_ref")),
                    "adjust": _f(r.get("Adjust"), 0.0),
                }
                m["thin_film"] = _is_thin_film(m["technology"])
                out[m["name"]] = m
            _cache["modules"] = out
            _cache["modules_path"] = str(path)
            _cache["gamma_column"] = next((c for c in GAMMA_PMP_COLUMNS if c in header), None)
        return _cache["modules"]


def inverters():
    with _lock:
        if "inverters" not in _cache:
            raw, path, _header = _read(config.INVERTER_LIB_FILE)
            out = {}
            for r in raw:
                paco = _f(r.get("Paco"))
                if paco is None:
                    continue
                out[r["Name"]] = {
                    "name": r["Name"], "vac": _f(r.get("Vac")), "paco": paco,
                    "pdco": _f(r.get("Pdco")), "vdco": _f(r.get("Vdco")),
                    "pso": _f(r.get("Pso")), "pnt": _f(r.get("Pnt")),
                    "c0": _f(r.get("C0"), 0.0), "c1": _f(r.get("C1"), 0.0),
                    "c2": _f(r.get("C2"), 0.0), "c3": _f(r.get("C3"), 0.0),
                    "vdcmax": _f(r.get("Vdcmax")), "idcmax": _f(r.get("Idcmax")),
                    "mppt_low": _f(r.get("Mppt_low")), "mppt_high": _f(r.get("Mppt_high")),
                }
            _cache["inverters"] = out
            _cache["inverters_path"] = str(path)
        return _cache["inverters"]


def library_info():
    modules(); inverters()
    return {"modules_file": _cache.get("modules_path"), "inverters_file": _cache.get("inverters_path"),
            "module_count": len(_cache["modules"]), "inverter_count": len(_cache["inverters"]),
            "gamma_pmp_column": _cache.get("gamma_column"), "commit": config.SAM_LIB_COMMIT}


def exact(kind: str, name: str):
    """[record] for this exact library name, else [] (used to reselect equipment from a saved inputs file)."""
    rec = (modules() if kind == "modules" else inverters()).get(name or "")
    return [rec] if rec else []


def search(kind: str, query: str, limit: int = 40):
    lib = modules() if kind == "modules" else inverters()
    terms = [t for t in (query or "").lower().split() if t]
    hits = []
    for name, rec in lib.items():
        if all(t in name.lower() for t in terms):
            hits.append(rec)
            if len(hits) >= limit:
                break
    return hits
