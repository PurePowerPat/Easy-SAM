"""Post-processing that replaces the Excel workbook (v5).

Workbook logic reproduced (ISC sheet row 8764):
    BYCOL(year, MAX((x[i] + x[i+1] + x[i+2]) / 3))   -> per-year max consecutive 3-hr average
    Summary "Max Current" = MAX across all years
  - zeros are treated as zeros; windows never cross from one year into the next.
The same rolling-window method is applied to Voc and Vmp.
For minimum Vmp, a window only counts if every step in it is non-zero (inverter operating).
"""

SPECS = [("isc", "max", False), ("voc", "max", False), ("vmp", "max", False), ("vmp", "min", True)]


def window_steps(interval_min: int) -> int:
    return 3 * 60 // interval_min  # 3 (hourly) or 6 (30-minute)


def _rolling(x, n):
    if len(x) < n:
        return
    s = sum(x[:n])
    yield 0, s / n
    for i in range(1, len(x) - n + 1):
        s += x[i + n - 1] - x[i - 1]
        yield i, s / n


def best_window(x, n, mode="max", nonzero=False):
    best = None
    for i, avg in _rolling(x, n):
        if nonzero and min(x[i:i + n]) <= 0:
            continue
        if best is None or (avg > best[1] if mode == "max" else avg < best[1]):
            best = (i, avg)
    return best


def summarize(per_year: dict, timestamps: dict, interval: int):
    n = window_steps(interval)

    def stamp(year, i):
        ts = timestamps[year]
        return {"year": year, "start": ts[i].strftime("%Y-%m-%d %H:%M"),
                "end_step": ts[min(i + n - 1, len(ts) - 1)].strftime("%Y-%m-%d %H:%M"), "step_minutes": interval}

    results, yearly = {}, []
    for year in sorted(per_year):
        row = {"year": year}
        for var, mode, nz in SPECS:
            b = best_window(per_year[year][var], n, mode, nz)
            key = f"{var}_{mode}"
            row[key] = None if b is None else round(b[1], 4)
            if b is None:
                continue
            cur = results.get(key)
            if cur is None or (b[1] > cur["value"] if mode == "max" else b[1] < cur["value"]):
                results[key] = {"value": b[1], **stamp(year, b[0])}
        yearly.append(row)
    return {"window_steps": n, "worst": results, "yearly": yearly}


def nec_floor(isc_stc_module: float, bifacial: bool, bifacial_gain_pct: float) -> float:
    """0.70 x 1.25 x Isc_STC (one string), x (1 + gain) for bifacial modules."""
    mult = 1.0 + (bifacial_gain_pct / 100.0 if bifacial else 0.0)
    return 0.70 * 1.25 * isc_stc_module * mult
