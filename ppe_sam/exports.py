"""Exports: hourly (or 30-minute) string results, the Inputs used table, and the inputs (.json) file."""
import csv
import datetime as dt
import io
import json
import re

from . import __version__

INPUTS_FORMAT = "PPE SAM inputs"     # same file as the page's "Save inputs (.json)"; "Load inputs" reads it

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
    """The inputs exactly as the page sent them for this run, loadable with "Load inputs (.json)"."""
    saved = dt.datetime.fromtimestamp(started, dt.timezone.utc).isoformat(timespec="seconds")
    return json.dumps({"format": INPUTS_FORMAT, "version": 1, "app_version": __version__, "saved": saved,
                       "inputs": raw_inputs}, indent=2).encode("utf-8")


def inputs_used_csv(rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(["Section", "Input", "Value", "Units", "Method"])
    for r in rows:
        w.writerow([r["section"], r["input"], r["value"], r["units"], r["method"]])
    return buf.getvalue().encode("utf-8-sig")
