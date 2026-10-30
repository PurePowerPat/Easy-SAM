"""Exports: hourly (or 30-minute) string results, the Inputs used table, and the project (.esam) file."""
import csv
import datetime as dt
import io
import json
import re

from . import __version__, model

INPUTS_FORMAT = "PPE SAM inputs"     # same file as the page's "Save inputs" (.esam); "Load inputs" reads it

KINDS = {"isc": ("Isc", "A"), "voc": ("Voc", "V"), "vmp": ("Vmp", "V")}


def safe_name(text):
    t = re.sub(r"[^A-Za-z0-9._-]+", "_", (text or "").strip()).strip("_")
    return t or "PPE_SAM"


def series_csv(kind, per_year, timestamps) -> bytes:
    """Rows = time steps (Month, Day, Hour, Minute), columns = years. Same layout as the v5 workbook."""
    label, unit = KINDS[kind]
    years = sorted(per_year)
    ref = timestamps[years[0]]
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["Month", "Day", "Hour", "Minute"] + [f"{y} {label} ({unit})" for y in years])
    cols = [per_year[y][kind] for y in years]
    for i, t in enumerate(ref):
        w.writerow([t.month, t.day, t.hour, t.minute] + [f"{c[i]:.6g}" for c in cols])
    return buf.getvalue().encode("utf-8-sig")


def inputs_json(raw_inputs: dict, started: float) -> bytes:
    """The inputs exactly as the page sent them for this run: an .esam project file (see esam.py)."""
    saved = dt.datetime.fromtimestamp(started, dt.UTC).isoformat(timespec="seconds")
    return json.dumps({"format": INPUTS_FORMAT, "version": 1, "app_version": __version__, "saved": saved,
                       "inputs": raw_inputs}, indent=2).encode("utf-8")


# SAM "Generate code > JSON for inputs" (SAM 2026.7.3): every pvsamv1 input by its SSC name, plus these
# entries. PySAM renames the 6par_* inputs to sixpar_* (Python names cannot start with a digit).
SAM_JSON_HEADER = {"compute_module_0": "pvsamv1", "compute_module_1": "grid", "number_compute_modules": 2}
SAM_JSON_METRICS = [("annual_energy", "Annual AC energy in Year 1"),
                    ("capacity_factor", "DC capacity factor in Year 1"),
                    ("kwh_per_kw", "Energy yield in Year 1"),
                    ("performance_ratio", "Performance ratio in Year 1")]


def sam_name(pysam_name: str) -> str:
    return "6par_" + pysam_name[len("sixpar_"):] if pysam_name.startswith("sixpar_") else pysam_name


def sam_case_json(inputs: dict, weather_path) -> dict:
    """Every SAM input of the run (one weather year) in SAM's own "JSON for inputs" layout."""
    m = model.make_model(inputs, weather_path)
    out = {}
    for group in m.export().values():
        if isinstance(group, dict):
            for k, v in group.items():
                out[sam_name(k)] = v
    for g, values in inputs.items():          # app settings PySAM does not list in export(), e.g. use_snow_weather_file
        for k in values:
            if sam_name(k) not in out and hasattr(getattr(m, g, None), k):
                out[sam_name(k)] = getattr(getattr(m, g), k)
    out["solar_resource_file"] = str(weather_path).replace("\\", "/")
    out.update(SAM_JSON_HEADER)
    for i, (name, label) in enumerate(SAM_JSON_METRICS):
        out[f"metric_{i}"], out[f"metric_{i}_label"] = name, label
    out["number_metrics"] = len(SAM_JSON_METRICS)
    return out


def inputs_used_csv(rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["Section", "Input", "Value", "Units", "Method", "Key item to check", "Non-PPE standard"])
    for r in rows:
        w.writerow([r["section"], r["input"], r["value"], r["units"], r["method"],
                    "Yes" if r.get("key") else "", "Yes" if r.get("nonstd") else ""])
    return buf.getvalue().encode("utf-8-sig")
