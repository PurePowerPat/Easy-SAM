"""Build the single-string Detailed PV / No Financial model and run it for one weather file.

Every setting below mirrors the PPE guide (sections 2-9). The engineer supplies only the design
inputs validated in `validate_design`; every design input must be entered (no hidden defaults).

`design["_entered"]` records which optional inputs the engineer typed; `design["_db_fields"]` lists
the inputs the UI filled from the CEC database (used to label the Inputs used table).
"""
import math

from . import config, libraries
from .libraries import CELLTECH_TEXT, celltech_code

OUTPUT_VARS = {"isc": "subarray1_isc", "voc": "subarray1_voc", "vmp": "subarray1_dc_voltage"}
LENGTH_UNITS = ("m", "in")


def ppe_self_shading(bifacial: bool, thin_film: bool) -> str:
    """PPE standard (guide 7.3): bifacial -> Standard (Thin film for thin-film cells); monofacial -> None."""
    if not bifacial:
        return "none"
    return "thin_film" if thin_film else "standard"


def _truthy(v):
    return str(v or "").lower() in ("1", "true", "on", "yes")


def sam_rows(nstrings, modules_per_string, per_subarray):
    """Rows SAM builds for self-shading: floor(strings x modules per string / modules per subarray)."""
    return (nstrings * modules_per_string) // per_subarray


def strings_for_rows(rows, modules_per_string, per_subarray):
    """Fewest strings that fill `rows` subarrays (SAM row count >= rows)."""
    return max(1, -(-rows * per_subarray // modules_per_string))


class DesignError(ValueError):
    """Carries a list of {"field": <input name>, "message": <text>} so the UI can highlight them all."""

    def __init__(self, errors):
        if isinstance(errors, str):
            errors = [{"field": None, "message": errors}]
        self.errors = errors
        super().__init__("; ".join(e["message"] for e in errors))


class _Checker:
    def __init__(self, d):
        self.d, self.errors, self.entered = d, [], set()

    def fail(self, field, msg):
        self.errors.append({"field": field, "message": msg})
        return None

    def num(self, key, label, lo=None, hi=None, required=True, default=None, integer=False):
        v = self.d.get(key, None)
        if v in (None, ""):
            return self.fail(key, f"{label} is required. Enter a value.") if required else default
        try:
            v = float(v)
        except (TypeError, ValueError):
            return self.fail(key, f"{label}: enter a number.")
        if not math.isfinite(v):                  # float() accepts "nan" and "inf"; no range check catches NaN
            return self.fail(key, f"{label}: enter a number.")
        if integer and v != int(v):
            return self.fail(key, f"{label}: enter a whole number.")
        if (lo is not None and v < lo) or (hi is not None and v > hi):
            return self.fail(key, f"{label}: enter a value from {lo:g} to {hi:g}.")
        self.entered.add(key)
        return int(v) if integer else v

    def length(self, key, label, lo_m, hi_m, units=None):
        """Length entered in metres or inches. Returns (metres, entered value, units)."""
        units = units or self.d.get(f"{key}_units") or "m"
        if units not in LENGTH_UNITS:
            units = "m"
        f = config.INCH_TO_M if units == "in" else 1.0
        lo, hi = (round(lo_m / f, 1), round(hi_m / f, 1)) if units == "in" else (lo_m, hi_m)
        raw = self.num(key, f"{label} ({units})", lo, hi)
        return (None if raw is None else raw * f), raw, units


def compute_gcr(racking, modules_high, along_slope_m, gap_m, pitch_m):
    """GCR per PPE: (modules high x module dim along slope + gap x (high-1)) / pitch.  Carport = 0.01."""
    if racking == "carport":
        return config.CARPORT_GCR
    if not pitch_m or pitch_m <= 0:
        return None
    n = max(1, int(modules_high))
    return (n * along_slope_m + (gap_m or 0.0) * (n - 1)) / pitch_m


_SOLVER_CELLTYPE = {0: "monoSi", 1: "multiSi", 2: "cdte", 3: "cis", 4: "cigs", 5: "amorphous"}
THIN_FILM_CODES = (2, 3, 4, 5)
SIXPAR_OUTPUTS = [("a", "a_ref", "Diode ideality factor x cells x thermal voltage (V)"),
                  ("Il", "I_L_ref", "Light current at STC (A)"),
                  ("Io", "I_o_ref", "Diode saturation current at STC (A)"),
                  ("Rs", "R_s", "Series resistance (ohm)"),
                  ("Rsh", "R_sh_ref", "Shunt resistance at STC (ohm)"),
                  ("Adj", "Adjust", "Adjust: correction to the Isc temperature coefficient (%)")]


def calculate_sixpar(celltech, voc, isc, vmp, imp, aisc, bvoc, gpmp, nser):
    """Run SAM's 6-parameter calculation (SixParsolve) on datasheet values."""
    import PySAM.SixParsolve as sixpar
    m = sixpar.new()
    s = m.SixParameterSolver
    s.celltype = _SOLVER_CELLTYPE[celltech]
    s.Vmp, s.Imp, s.Voc, s.Isc = vmp, imp, voc, isc
    s.alpha_isc, s.beta_voc, s.gamma_pmp = aisc, bvoc, gpmp
    s.Nser, s.Tref = nser, 25.0
    try:
        m.execute(0)
    except Exception as e:  # noqa: BLE001
        return None, " ".join(str(e).replace("6parsolve execution error.", "").split())
    o = m.Outputs
    return {k: getattr(o, k) for k, _, _ in SIXPAR_OUTPUTS}, None


def _custom_module(d, c, length, width):
    """Validate custom-module inputs (SAM 'CEC Performance Model with User Entered Specifications')."""
    n_err = len(c.errors)
    name = (d.get("custom_name") or "").strip()
    if not name:
        c.fail("custom_name", "Module name is required. Enter the manufacturer and model.")
    else:
        c.entered.add("custom_name")
    ct_raw = str(d.get("custom_celltech", "")).strip()
    celltech = int(ct_raw) if ct_raw in ("0", "1", "2", "3", "4", "5") else None
    if celltech is None:
        c.fail("custom_celltech", "Cell type: select one from the list.")
    nser = c.num("custom_nser", "Cells in series", 1, 500, integer=True)
    voc = c.num("custom_voc", "Voc", 1, 1000)
    isc = c.num("custom_isc", "Isc", 0.1, 50)
    vmp = c.num("custom_vmp", "Vmp", 0.5, 1000)
    imp = c.num("custom_imp", "Imp", 0.1, 50)
    if voc and vmp and vmp >= voc:
        c.fail("custom_vmp", "Vmp must be less than Voc. Check the datasheet values.")
    if isc and imp and imp >= isc:
        c.fail("custom_imp", "Imp must be less than Isc. Check the datasheet values.")

    def coef(key, label, ref, units_key, lo_pct, hi_pct, sign_txt, abs_unit):
        raw = c.num(key, label, -1000, 1000)
        units = d.get(units_key) or "pct"
        if units not in ("pct", "abs"):
            units = "pct"
        if raw is None or not ref:
            return None, None, units
        absval = raw / 100.0 * ref if units == "pct" else raw
        pct = absval / ref * 100.0
        if not lo_pct <= pct <= hi_pct:
            c.fail(key, f"{label} = {pct:.3f} %/°C, outside the expected {lo_pct:g} to {hi_pct:g} %/°C "
                        f"({sign_txt}). Check the value and the units (%/°C vs {abs_unit}).")
            return None, raw, units
        return absval, raw, units

    bvoc, bvoc_raw, bvoc_units = coef("custom_bvoc", "Voc temperature coefficient", voc, "custom_bvoc_units",
                                      -1.0, -0.01, "negative", "V/°C")
    aisc, aisc_raw, aisc_units = coef("custom_aisc", "Isc temperature coefficient", isc, "custom_aisc_units",
                                      0.0001, 0.2, "positive", "A/°C")
    gpmp = c.num("custom_gpmp", "Pmp temperature coefficient", -1, -0.01)
    tnoct = c.num("custom_tnoct", "NOCT", 30, 70)
    bif = _truthy(d.get("custom_bifacial"))

    if len(c.errors) > n_err:
        return None, None
    params, fit_err = calculate_sixpar(celltech, voc, isc, vmp, imp, aisc, bvoc, gpmp, nser)
    if fit_err:
        c.fail("custom_fit", "SAM could not calculate the module model from these datasheet values "
                             f"({fit_err}). Check Voc, Isc, Vmp, Imp, the temperature coefficients and cells "
                             "in series.")
        return None, None
    mod = {
        "source": "custom", "name": name, "manufacturer": "", "celltech": celltech,
        "technology": CELLTECH_TEXT[celltech], "thin_film": celltech in THIN_FILM_CODES,
        "bifacial": 1 if bif else 0, "stc": vmp * imp, "area": length * width if (length and width) else None,
        "length": length, "width": width, "n_s": nser,
        "i_sc_ref": isc, "v_oc_ref": voc, "i_mp_ref": imp, "v_mp_ref": vmp,
        "alpha_sc": aisc, "beta_oc": bvoc, "gamma_r": gpmp, "t_noct": tnoct,
    }
    return mod, {"bvoc_entered": bvoc_raw, "bvoc_units": bvoc_units,
                 "aisc_entered": aisc_raw, "aisc_units": aisc_units, "sixpar": params}


def validate_design(d: dict) -> dict:
    """Return a clean, fully-resolved design dict or raise DesignError listing EVERY problem."""
    c = _Checker(d)
    out = {"project": (d.get("project") or "").strip()}

    # ---- site: address or coordinates. The weather download always uses latitude / longitude.
    mode = d.get("location_mode", "coords")            # API callers without the field = coordinates
    if mode not in ("address", "coords"):
        c.fail("location_mode", "Location: choose Address or Coordinates.")
        mode = "coords"
    out["location_mode"] = mode
    out["address"] = (d.get("address") or "").strip() if out["location_mode"] == "address" else ""
    out["geocode_match"] = (d.get("geocode_match") or "").strip() if out["location_mode"] == "address" else ""
    out["geocode_source"] = (d.get("geocode_source") or "").strip() if out["location_mode"] == "address" else ""
    if out["location_mode"] == "address":
        if not out["address"]:
            c.fail("address", "Address is required. Enter an address, then click Run.")
        if d.get("lat") in (None, "") or d.get("lon") in (None, ""):
            if out["address"]:
                c.fail("address", "Address: click Run to look up the coordinates.")
            out["lat"] = out["lon"] = None
        else:
            out["lat"] = c.num("lat", "Latitude", -90, 90)
            out["lon"] = c.num("lon", "Longitude", -180, 180)
    else:
        out["lat"] = c.num("lat", "Latitude", -90, 90)
        out["lon"] = c.num("lon", "Longitude", -180, 180)
    out["interval"] = c.num("interval", "Weather time step", required=False, default=60, integer=True)
    if out["interval"] is not None and out["interval"] not in (30, 60):
        c.fail("interval", "Weather time step: select 60 or 30 minutes.")

    # ---- module ------------------------------------------------------------------------
    source = d.get("module_source", "cec")
    if source not in ("cec", "custom"):
        source = "cec"
    out["module_source"] = source
    mod = None
    if source == "cec":
        mods = libraries.modules()
        if d.get("module_name") not in mods:
            c.fail("module_name", "Module: search the CEC library and select a module from the list.")
        else:
            mod = dict(mods[d["module_name"]])
            mod["source"] = "cec"

    lib_len_mm = round(mod["length"] * 1000, 1) if mod and mod.get("length") else None
    lib_wid_mm = round(mod["width"] * 1000, 1) if mod and mod.get("width") else None
    if mod is not None or source == "custom":
        l_mm = c.num("module_length", "Module length", 300, 4000, required=lib_len_mm is None, default=lib_len_mm)
        w_mm = c.num("module_width", "Module width", 200, 3000, required=lib_wid_mm is None, default=lib_wid_mm)
    else:
        l_mm = w_mm = None
    out["module_length_mm"], out["module_width_mm"] = l_mm, w_mm
    length = l_mm / 1000 if l_mm else None
    width = w_mm / 1000 if w_mm else None
    out["module_length"], out["module_width"] = length, width
    out["aspect_ratio"] = (length / width) if (length and width) else None

    if source == "custom":
        mod, custom = _custom_module(d, c, length, width)
        out["custom"] = custom
        bif = bool(mod and mod["bifacial"])
        out["bifacial_source"] = "custom module (user)"
    else:
        lib_bif = bool(mod and mod["bifacial"])
        bif = lib_bif or (_truthy(d.get("bifacial_override")) and mod is not None)
        out["bifacial_source"] = "library" if lib_bif else ("user override" if bif else "library (monofacial)")
    out["module"] = mod
    # NEC 70% check uses the datasheet Isc. Custom modules are entered from the datasheet already;
    # CEC library modules need it entered (library values often differ from the datasheet).
    if source == "cec":
        out["isc_datasheet"] = c.num("isc_datasheet", "Isc (datasheet)", 0.1, 50) if mod is not None else None
    else:
        out["isc_datasheet"] = mod["i_sc_ref"] if mod else None
    out["bifacial"] = bif
    out["bifacial_mismatch"] = bool(bif and _truthy(d.get("bifacial_mismatch")))

    # ---- inverter ------------------------------------------------------------------------
    invs = libraries.inverters()
    if d.get("inverter_name") not in invs:
        c.fail("inverter_name", "Inverter: search the CEC library and select an inverter from the list.")
        out["inverter"] = None
    else:
        out["inverter"] = dict(invs[d["inverter_name"]])
    # Voltage limits (Advanced Settings); left empty or not sent = PPE default.
    for key, (label, default) in config.INVERTER_LIMITS.items():
        lo = 0.0 if key == "vmppt_low" else 1.0
        out[key] = c.num(key, label, lo, config.INVERTER_LIMIT_MAX_V, required=False, default=default)
    if out["vmppt_low"] is not None and out["vmppt_high"] is not None and out["vmppt_low"] >= out["vmppt_high"]:
        c.fail("vmppt_high", "Vmppt high must be greater than Vmppt low.")
    out["inverter_limits_default"] = all(out[k] == dflt for k, (_l, dflt) in config.INVERTER_LIMITS.items())

    # ---- system design: circuit -----------------------------------------------------------
    out["modules_per_string"] = c.num("modules_per_string", "Modules per string", 1, 100, integer=True)
    sv = c.num("system_voltage", "System maximum voltage")
    if sv is not None and sv not in config.SYSTEM_VOLTAGES:
        c.fail("system_voltage", "System maximum voltage: select 1000 V or 1500 V.")
        sv = None
    out["system_voltage"] = int(sv) if sv else None

    # ---- system design: racking ---------------------------------------------------------
    racking = d.get("racking")
    if racking == "rooftop":
        racking = "fixed"
    if racking not in config.RACKING_TYPES:
        c.fail("racking", "Mounting type: choose Single-axis tracker, Fixed-tilt or Carport.")
        racking = None
    out["racking"] = racking
    if racking == "tracker":
        out["track_mode"], out["tilt"], out["backtrack"] = 1, 0.0, 1
        out["azimuth"] = c.num("azimuth", "Azimuth", 0, 360)
        out["rotlim"] = c.num("rotlim", "Rotation limit", 0, 90)
    else:
        out["track_mode"], out["backtrack"], out["rotlim"] = 0, 0, 45.0
        out["tilt"] = c.num("tilt", "Tilt", 0, 90) if racking else None
        out["azimuth"] = c.num("azimuth", "Azimuth", 0, 360) if racking else None

    out["orientation"] = d.get("orientation") or None
    if racking:
        if out["orientation"] not in ("portrait", "landscape"):
            c.fail("orientation", "Module orientation: select portrait or landscape.")
            out["orientation"] = "portrait"
        else:
            c.entered.add("orientation")
    else:
        out["orientation"] = out["orientation"] or "portrait"

    if racking:
        out["modules_high"] = c.num("modules_high", "Modules High", 1, 50, integer=True)
        out["modules_across"] = c.num("modules_across", "Modules Across", 1, 1000, integer=True)
        out["rows_requested"] = c.num("rows", "Number of rows", 1, 50, integer=True)
    else:
        out["modules_high"] = out["modules_across"] = out["rows_requested"] = None
    high = out["modules_high"] or 1
    # Strings are added (all on ONE inverter) until SAM builds the requested number of rows.
    out["nstrings"] = out["rows"] = None
    mps, R = out["modules_per_string"], out["rows_requested"]
    if out["modules_high"] and out["modules_across"] and mps and R:
        per_sub = out["modules_high"] * out["modules_across"]
        n = strings_for_rows(R, mps, per_sub)
        actual = sam_rows(n, mps, per_sub)
        if actual != R:
            c.fail("rows", f"Number of rows: with {mps} modules per string and {per_sub} modules per subarray, "
                           f"SAM cannot model exactly {R} row(s); the nearest is {actual}. Enter {actual}, "
                           "or change Modules High / Modules Across.")
        out["nstrings"], out["rows"] = n, actual
    out["ninverters"] = 1

    # Self-shading: defaults to the PPE standard for the module; the engineer may choose another option.
    out["self_shading_ppe"] = ppe_self_shading(bif, bool(mod and mod.get("thin_film")))
    shade = d.get("self_shading") or ""
    if racking and shade:
        if shade not in config.SELF_SHADING:
            c.fail("self_shading", "Self-shading: select None, Standard or Thin film.")
            shade = out["self_shading_ppe"]
        else:
            c.entered.add("self_shading")
    out["self_shading"] = shade if shade in config.SELF_SHADING else out["self_shading_ppe"]
    along = length if out["orientation"] == "portrait" else width

    out["gcr_mode"] = d.get("gcr_mode") or "pitch"
    out["pitch"] = out["gap"] = out["gcr"] = None
    out["pitch_entered"], out["pitch_units"] = None, "m"
    out["gap_in"] = None
    if racking == "carport":
        out["gcr_mode"] = "carport"
        out["gcr"] = config.CARPORT_GCR
    elif racking:
        if out["gcr_mode"] == "gcr":
            out["gcr"] = c.num("gcr", "GCR", 0.01, 0.99)
            if out["gcr"] and along:
                out["pitch"] = high * along / out["gcr"]
        else:
            out["gcr_mode"] = "pitch"
            out["pitch"], out["pitch_entered"], out["pitch_units"] = c.length("pitch", "Row pitch", 0.1, 100)
            if high >= 2:
                gap_m, out["gap_in"], _u = c.length("gap", "Module spacing", 0, 1, units="in")
                out["gap"] = gap_m
            else:
                out["gap"] = 0.0
            if out["pitch"] and along and out["gap"] is not None:
                out["gcr"] = compute_gcr(racking, high, along, out["gap"], out["pitch"])
                if not 0.01 <= out["gcr"] <= 0.99:
                    c.fail("pitch", f"Calculated GCR {out['gcr']:.3f} is outside 0.01-0.99. Check the row pitch.")

    # ---- bifacial inputs -----------------------------------------------------------------
    out["ground_clearance_entered"], out["ground_clearance_units"] = None, "m"
    if bif:
        base = c.num("bifaciality_base", "Bifaciality base", 1, 100)
        tol = c.num("bifaciality_tol", "Bifaciality tolerance", 0, 50)
        out["bifaciality_base"], out["bifaciality_tol"] = base, tol
        out["bifaciality"] = (base + tol) / 100.0 if (base is not None and tol is not None) else None
        if out["bifaciality"] and out["bifaciality"] > 1:
            c.fail("bifaciality_tol", "Bifaciality base + tolerance cannot exceed 100%. Check both values.")
        if racking:
            (out["ground_clearance"], out["ground_clearance_entered"],
             out["ground_clearance_units"]) = c.length("ground_clearance", "Ground clearance height", 0.1, 30)
        else:
            out["ground_clearance"] = None
        out["bifacial_gain"] = c.num("bifacial_gain", "Bifacial gain", 0, 100)
    else:
        out["bifaciality"] = 0.0
        out["ground_clearance"] = (config.GROUND_CLEARANCE_DEFAULT_M.get(racking) if racking else None) or 1.0
        out["bifacial_gain"] = 0.0

    if c.errors:
        raise DesignError(c.errors)
    out["_entered"] = sorted(c.entered)
    dbf = d.get("db_fields") or []
    out["_db_fields"] = sorted(str(x) for x in dbf) if isinstance(dbf, (list, tuple)) else []
    return out


def build_inputs(design: dict) -> dict:
    """Return {group: {var: value}} assignments applied on top of the FlatPlatePVNone defaults."""
    m, inv, n = design["module"], design["inverter"], design["modules_per_string"]
    nstr = design["nstrings"]
    ninv = design.get("ninverters", 1)
    bif = design["bifacial"]
    vdcmax = float(design["vdc_max"])
    zeros12 = [0.0] * 12
    shade_mode = config.SELF_SHADING[design["self_shading"]][0]
    p_mod = (m["v_mp_ref"] or 0) * (m["i_mp_ref"] or 0)

    inputs = {
        "SolarResource": {"irrad_mode": 0, "sky_model": 2, "use_wf_albedo": 1, "use_spatial_albedos": 0},
        "Module": {"module_model": 1},
        "CECPerformanceModelWithModuleDatabase": {
            "cec_area": m["area"], "cec_n_s": m["n_s"],
            "cec_i_sc_ref": m["i_sc_ref"], "cec_v_oc_ref": m["v_oc_ref"],
            "cec_i_mp_ref": m["i_mp_ref"], "cec_v_mp_ref": m["v_mp_ref"],
            "cec_alpha_sc": m["alpha_sc"], "cec_beta_oc": m["beta_oc"],
            "cec_a_ref": m.get("a_ref"), "cec_i_l_ref": m.get("i_l_ref"), "cec_i_o_ref": m.get("i_o_ref"),
            "cec_r_s": m.get("r_s"), "cec_r_sh_ref": m.get("r_sh_ref"), "cec_adjust": m.get("adjust"),
            "cec_t_noct": m["t_noct"],
            "cec_module_length": design["module_length"], "cec_module_width": design["module_width"],
            "cec_is_bifacial": 1 if bif else 0,
            "cec_bifaciality": design["bifaciality"] if bif else 0.0,
            "cec_bifacial_transmission_factor": config.BIFACIAL_TRANSMISSION_DEFAULT,
            "cec_bifacial_ground_clearance_height": design["ground_clearance"],
            "cec_temp_corr_mode": 0, "cec_standoff": 6, "cec_height": 0,
        },
        "Inverter": {"inverter_model": 0, "inverter_count": ninv, "inv_num_mppt": 1,
                     "inv_snl_paco": inv["paco"], "mppt_low_inverter": float(design["vmppt_low"]),
                     "mppt_hi_inverter": float(design["vmppt_high"])},
        "InverterCECDatabase": {
            "inv_snl_c0": inv["c0"], "inv_snl_c1": inv["c1"], "inv_snl_c2": inv["c2"],
            "inv_snl_c3": inv["c3"], "inv_snl_paco": inv["paco"], "inv_snl_pdco": inv["pdco"],
            "inv_snl_pnt": inv["pnt"], "inv_snl_pso": inv["pso"], "inv_snl_vdco": inv["vdco"],
            "inv_snl_vdcmax": vdcmax, "inv_tdc_cec_db": [[vdcmax, 50.0, -0.02, 53.0, -0.47]],
        },
        "SystemDesign": {
            "inverter_count": ninv, "subarray1_modules_per_string": n, "subarray1_nstrings": nstr,
            "subarray1_mppt_input": 1, "subarray2_enable": 0, "subarray3_enable": 0, "subarray4_enable": 0,
            "system_capacity": nstr * n * p_mod / 1000.0,
            "subarray1_track_mode": design["track_mode"],
            "subarray1_tilt": design["tilt"], "subarray1_azimuth": design["azimuth"],
            "subarray1_backtrack": design["backtrack"], "subarray1_rotlim": design["rotlim"],
            "subarray1_gcr": design["gcr"], "subarray1_slope_tilt": 0.0, "subarray1_slope_azm": 0.0,
            "subarray1_tilt_eq_lat": 0, "enable_mismatch_vmax_calc": 0,
        },
        "Shading": {"subarray1_shade_mode": shade_mode, "subarray1_shading_en_azal": 0,
                    "subarray1_shading_en_diff": 0, "subarray1_shading_en_mxh": 0,
                    "subarray1_shading_en_string_option": 0, "subarray1_shading_en_timestep": 0},
        "Layout": {"module_aspect_ratio": design["aspect_ratio"],
                   "subarray1_mod_orient": 0 if design["orientation"] == "portrait" else 1,
                   "subarray1_nmody": design["modules_high"], "subarray1_nmodx": design["modules_across"]},
        "Losses": {
            "subarray1_soiling": zeros12, "subarray1_rear_soiling_loss": 0.0,
            "subarray1_rack_shading": 0.0, "calculate_rack_shading": 0,
            "subarray1_mismatch_loss": 0.0, "subarray1_diodeconn_loss": 0.0,
            "subarray1_dcwiring_loss": 0.0, "subarray1_tracking_loss": 0.0,
            "subarray1_nameplate_loss": 0.0, "subarray1_electrical_mismatch": 0.0,
            "calculate_bifacial_electrical_mismatch": 1 if design.get("bifacial_mismatch") else 0,
            "dcoptimizer_loss": 0.0, "acwiring_loss": 0.0, "transmission_loss": 0.0,
            "transformer_load_loss": 0.0, "transformer_no_load_loss": 0.0,
            "en_snow_model": 0, "use_snow_weather_file": 1,
        },
        "AdjustmentFactors": {"adjust_constant": 0.0, "dc_adjust_constant": 0.0},
        "GridLimits": {"enable_interconnection_limit": 0},
    }
    if m.get("source") == "custom":
        inputs["Module"] = {"module_model": 2}
        del inputs["CECPerformanceModelWithModuleDatabase"]
        inputs["CECPerformanceModelWithUserEnteredSpecifications"] = {
            "sixpar_celltech": m["celltech"], "sixpar_area": m["area"], "sixpar_nser": m["n_s"],
            "sixpar_voc": m["v_oc_ref"], "sixpar_isc": m["i_sc_ref"],
            "sixpar_vmp": m["v_mp_ref"], "sixpar_imp": m["i_mp_ref"],
            "sixpar_aisc": m["alpha_sc"], "sixpar_bvoc": m["beta_oc"], "sixpar_gpmp": m["gamma_r"],
            "sixpar_tnoct": m["t_noct"], "sixpar_standoff": 6, "sixpar_mounting": 0,
            "sixpar_is_bifacial": 1 if bif else 0,
            "sixpar_bifaciality": design["bifaciality"] if bif else 0.0,
            "sixpar_bifacial_transmission_factor": config.BIFACIAL_TRANSMISSION_DEFAULT,
            "sixpar_bifacial_ground_clearance_height": design["ground_clearance"],
        }
        return inputs
    code = celltech_code(m["technology"])
    if code is not None:
        inputs["CECPerformanceModelWithUserEnteredSpecifications"] = {"sixpar_celltech": code}
    return inputs


def make_model(inputs: dict, weather_path=None):
    """FlatPlatePVNone defaults + every PPE assignment. Used by the run AND by the inputs export.

    Raises KeyError for a group or input PySAM does not know, so a misspelled setting can never be
    skipped silently."""
    import PySAM.Pvsamv1 as pvsam
    model = pvsam.default("FlatPlatePVNone")
    for group, values in inputs.items():
        grp = getattr(model, group, None)
        if grp is None:
            raise KeyError(f"PySAM Pvsamv1 has no input group '{group}'")
        names = set(dir(grp))
        for k, v in values.items():
            if k not in names:
                raise KeyError(f"PySAM Pvsamv1.{group} has no input '{k}'")
            setattr(grp, k, v)
    if weather_path is not None:
        model.SolarResource.solar_resource_file = str(weather_path)
    return model


def run_year(args):
    """Worker: (year, weather_path, inputs) -> (year, {isc, voc, vmp}). Runs in a subprocess."""
    year, weather_path, inputs = args
    model = make_model(inputs, weather_path)
    model.execute(0)
    out = model.Outputs
    return year, {key: list(getattr(out, var)) for key, var in OUTPUT_VARS.items()}
