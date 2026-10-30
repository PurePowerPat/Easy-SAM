"""Post-processing that replaces the Excel workbook (v5).

Workbook logic reproduced (ISC sheet row 8764):
    BYCOL(year, MAX((x[i] + x[i+1] + x[i+2]) / 3))   -> per-year max consecutive 3-hr average
    Summary "Max Current" = MAX across all years
  - zeros are treated as zeros; windows never cross from one year into the next.
The same rolling-window method is applied to Vmp. Voc is the maximum single time-step value (no averaging).
For minimum Vmp, a window only counts if every step in it is non-zero (inverter operating).
"""

# (variable, max/min, non-zero windows only, 3-hour window: False = single time step)
SPECS = [("isc", "max", False, True), ("voc", "max", False, False), ("vmp", "max", False, True),
         ("vmp", "min", True, True)]


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

    def stamp(year, i, steps):
        ts = timestamps[year]
        return {"year": year, "start": ts[i].strftime("%Y-%m-%d %H:%M"),
                "end_step": ts[min(i + steps - 1, len(ts) - 1)].strftime("%Y-%m-%d %H:%M"), "step_minutes": interval,
                "window_steps": steps}

    results, yearly = {}, []
    for year in sorted(per_year):
        row = {"year": year}
        for var, mode, nz, windowed in SPECS:
            steps = n if windowed else 1
            b = best_window(per_year[year][var], steps, mode, nz)
            key = f"{var}_{mode}"
            row[key] = None if b is None else round(b[1], 4)
            if b is None:
                continue
            cur = results.get(key)
            if cur is None or (b[1] > cur["value"] if mode == "max" else b[1] < cur["value"]):
                results[key] = {"value": b[1], **stamp(year, b[0], steps)}
        yearly.append(row)
    return {"window_steps": n, "worst": results, "yearly": yearly}


def nec_baseline(isc_stc_module: float) -> float:
    """NEC Baseline per 2023 NEC 690.8(A)(1)(a)(1): 1.25 x Isc_STC (one string)."""
    return 1.25 * isc_stc_module


def nec_check(isc_stc_module, bifacial: bool, bifacial_gain_pct: float, simulated: float) -> dict:
    """PV Maximum Circuit Current. NEC Baseline = 1.25 x Isc (datasheet); for bifacial modules also
    NEC Baseline + Bifacial Gain = 1.25 x Isc x (1 + gain), for reference. Use the larger of the SAM simulated Isc
    and 70% of the NEC Baseline (no bifacial gain). Baseline values are None until the datasheet Isc is known."""
    if isc_stc_module is None:
        return {"isc_stc_module": None, "bifacial_gain_pct": bifacial_gain_pct if bifacial else None,
                "simulated_3hr": simulated, "baseline": None, "baseline_bifacial": None, "baseline_70pct": None,
                "pct_of_baseline": None, "use": None, "use_value": None}
    base = nec_baseline(isc_stc_module)
    floor = 0.70 * base
    return {"isc_stc_module": isc_stc_module, "bifacial_gain_pct": bifacial_gain_pct if bifacial else None,
            "simulated_3hr": simulated, "baseline": base,
            "baseline_bifacial": base * (1.0 + bifacial_gain_pct / 100.0) if bifacial else None,
            "baseline_70pct": floor, "pct_of_baseline": simulated / base * 100.0,
            "use": "simulated" if simulated >= floor else "baseline_70pct", "use_value": max(simulated, floor)}
