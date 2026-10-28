"""Inputs used: every input the simulation used, in the same order as the configuration page.

Columns: Section | Input | Value | Units | Method.
Method is one of: Database, User entered, Calculated, Default.
Row flags used by the Results page:
  key   True  -> highlighted as a check-worthy item
  sub   "cec" -> CEC database module specs, shown in a collapsible sub-section under "Module model"
               (CEC library modules only; never highlighted)
  tip   "cec" -> "Module model" row gets the CEC-database tooltip
"""
from . import config, model as model_mod

DB, USER, CALC, DEF = "Database", "User entered", "Calculated", "Default"
RACK_TEXT = {"tracker": "Single-axis tracker", "fixed": "Fixed-tilt", "carport": "Carport"}

KEY_INPUTS = {
    "Project name", "Latitude", "Longitude", "Weather time step", "Albedo",
    "Module", "Power at STC", "Isc", "Voc", "Imp", "Vmp",
    "Isc temperature coefficient", "Voc temperature coefficient", "Pmp temperature coefficient", "NOCT",
    "Bifacial", "Calculate bifacial electrical mismatch", "Module length", "Module width",
    "Bifaciality", "Bifaciality tolerance", "Bifacial gain for NEC 70% check", "Self-shading",
    "Isc (datasheet) for NEC 70% check",
    "Inverter", "Mounting type", "Modules per string", "System max voltage", "Tilt", "Azimuth",
    "Module orientation", "Ground clearance", "Modules High", "Modules Across", "Strings modeled",
    "Rows modeled", "GCR", "Equivalent row pitch",
    "Losses (soiling, mismatch, wiring, diodes, nameplate, tracking, rack shading)",
}

CEC_SPECS_TIP = ("Module specs shown below are pulled directly from the CEC database. These values will likely "
                 "differ from values shown on the module datasheet. These differences are NOT errors. If your "
                 "module name is correct, you do not need to rerun your analysis with custom settings.")


def shading_text(d):
    """'Standard' or, when it differs from the PPE standard, 'None (PPE standard: Standard)'."""
    sel = config.SELF_SHADING[d["self_shading"]][1]
    ppe = config.SELF_SHADING[d["self_shading_ppe"]][1]
    return sel if sel == ppe else f"{sel} (PPE standard: {ppe})"


def _n(v, nd=None):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    f = float(v)
    if nd is not None:
        return f"{f:,.{nd}f}"
    if f.is_integer() and abs(f) < 1e12:
        return f"{int(f):,}"
    return f"{f:.6g}"


def build(d: dict, weather: dict | None = None) -> list:
    rows = []
    e, dbf = set(d.get("_entered", [])), set(d.get("_db_fields", []))
    m, inv = d["module"], d["inverter"]
    custom = d.get("module_source") == "custom"
    bif = d["bifacial"]
    sv = d["system_voltage"]

    def add(section, name, value, units="", method=USER, sub=None, tip=None):
        rows.append({"section": section, "input": name, "value": _n(value) if not isinstance(value, str) else value,
                     "units": units, "method": method, "key": (name in KEY_INPUTS) and not sub,
                     "sub": sub, "tip": tip})

    def entered_or_db(field):
        return DB if field in dbf or (field not in e) else USER

    def length(section, name, metres, entered, units):
        if units == "in":
            add(section, name, entered, "in")
            add(section, f"{name} (converted)", round(metres, 4), "m", CALC)
        else:
            add(section, name, metres, "m")

    # ---------------- Site and weather ----------------
    S = "Site and weather"
    addr = d.get("location_mode") == "address"
    add(S, "Project name", d["project"] or "(not named)")
    add(S, "Location input", "Address" if addr else "Coordinates")
    if addr:
        add(S, "Address", d["address"])
        if d.get("geocode_match"):
            add(S, "Address matched", d["geocode_match"], "", CALC)
        if d.get("geocode_source"):
            add(S, "Geocoder", d["geocode_source"], "", DEF)
    add(S, "Latitude", d["lat"], "°", CALC if addr else USER)
    add(S, "Longitude", d["lon"], "°", CALC if addr else USER)
    add(S, "Weather time step", d["interval"], "min", DEF if d["interval"] == 60 else USER)
    add(S, "Weather dataset", config.NSRDB_DATASET, "", DEF)
    if weather:
        add(S, "Weather years used", f"{weather['first']}-{weather['last']} ({weather['count']} years)", "", DB)
        if weather.get("unavailable_years"):
            add(S, "Weather years not available", ", ".join(map(str, weather["unavailable_years"])), "", DB)
        add(S, "NSRDB grid point", f"{weather.get('nsrdb_lat')}, {weather.get('nsrdb_lon')}", "°", DB)
    else:
        add(S, "Weather years requested", f"{config.NSRDB_FIRST_YEAR}-{config.nsrdb_last_year()}", "", DEF)
    add(S, "Albedo", "From weather file, every time step", "", DEF)
    add(S, "Albedo if missing or invalid in weather file", config.ALBEDO_FALLBACK, "", DEF)
    add(S, "Irradiance input", "DNI and DHI", "", DEF)
    add(S, "Sky diffuse model", "Perez", "", DEF)

    # ---------------- Module ----------------
    S = "Module"
    add(S, "Module source", "Custom module" if custom else "CEC library")
    add(S, "Module", m["name"])
    add(S, "Module model", "CEC Performance Model with " + ("User Entered Specifications" if custom else "Module Database"),
        "", DEF, tip=None if custom else "cec")
    if custom:
        mc = lambda f: DB if f in dbf else USER  # noqa: E731
        cu = d["custom"]
        add(S, "Cell type", m["technology"], "", mc("custom_celltech"))
        add(S, "Cells in series", m["n_s"], "cells", mc("custom_nser"))
        add(S, "Pmp at STC", round(m["stc"], 2), "W", CALC)
        add(S, "Isc", m["i_sc_ref"], "A", mc("custom_isc"))
        add(S, "Voc", m["v_oc_ref"], "V", mc("custom_voc"))
        add(S, "Imp", m["i_mp_ref"], "A", mc("custom_imp"))
        add(S, "Vmp", m["v_mp_ref"], "V", mc("custom_vmp"))
        add(S, "Isc temperature coefficient", m["alpha_sc"], "A/°C",
            CALC if cu["aisc_units"] == "pct" else mc("custom_aisc"))
        add(S, "Voc temperature coefficient", m["beta_oc"], "V/°C",
            CALC if cu["bvoc_units"] == "pct" else mc("custom_bvoc"))
        add(S, "Pmp temperature coefficient", m["gamma_r"], "%/°C", mc("custom_gpmp"))
        add(S, "NOCT", m["t_noct"], "°C", mc("custom_tnoct"))
        sp = cu.get("sixpar") or {}
        for key, lib_col, label in model_mod.SIXPAR_OUTPUTS:
            add(S, f"Single-diode parameter {lib_col}", sp.get(key), "", CALC)
    else:
        G = "cec"   # collapsible sub-section under "Module model"; unhighlighted
        add(S, "Technology", m["technology"], "", DB, sub=G)
        add(S, "Cells in series", m["n_s"], "cells", DB, sub=G)
        add(S, "Power at STC", m["stc"], "W", DB, sub=G)
        add(S, "Isc", m["i_sc_ref"], "A", DB, sub=G)
        add(S, "Voc", m["v_oc_ref"], "V", DB, sub=G)
        add(S, "Imp", m["i_mp_ref"], "A", DB, sub=G)
        add(S, "Vmp", m["v_mp_ref"], "V", DB, sub=G)
        add(S, "Isc temperature coefficient", m["alpha_sc"], "A/°C", DB, sub=G)
        add(S, "Voc temperature coefficient", m["beta_oc"], "V/°C", DB, sub=G)
        add(S, "Pmp temperature coefficient", m["gamma_r"], "%/°C", DB, sub=G)
        add(S, "NOCT", m["t_noct"], "°C", DB, sub=G)
        for key, label in (("a_ref", "a_ref"), ("i_l_ref", "I_L_ref"), ("i_o_ref", "I_o_ref"),
                           ("r_s", "R_s"), ("r_sh_ref", "R_sh_ref"), ("adjust", "Adjust")):
            add(S, f"Single-diode parameter {label}", m.get(key), "", DB, sub=G)
    if not custom:
        add(S, "Isc (datasheet) for NEC 70% check", d["isc_datasheet"], "A")
    add(S, "Bifacial", "Yes" if bif else "No", "",
        USER if (custom or d["bifacial_source"] == "user override") else DB)
    if bif:
        add(S, "Calculate bifacial electrical mismatch", "On" if d.get("bifacial_mismatch") else "Off")
    add(S, "Module length", d["module_length_mm"], "mm", entered_or_db("module_length"))
    add(S, "Module width", d["module_width_mm"], "mm", entered_or_db("module_width"))
    add(S, "Aspect ratio", round(d["aspect_ratio"], 4), "", CALC)
    add(S, "Module area", round(m["area"], 4) if m.get("area") else None, "m²", CALC if custom else DB)
    if bif:
        add(S, "Bifaciality", d["bifaciality_base"], "%")
        add(S, "Bifaciality tolerance", d["bifaciality_tol"], "%")
        add(S, "Bifaciality used (base + tolerance)", round(d["bifaciality"], 4), "", CALC)
        add(S, "Bifacial gain for NEC 70% check", d["bifacial_gain"], "%")
        add(S, "Bifacial transmission fraction", config.BIFACIAL_TRANSMISSION_DEFAULT, "", DEF)
    add(S, "Temperature model", "NOCT, ground or rack mounted, one story", "", DEF)

    # ---------------- Inverter ----------------
    S = "Inverter"
    add(S, "Inverter", inv["name"])
    for key, label, unit in (("paco", "AC power (Paco)", "W"), ("pdco", "DC power (Pdco)", "W"),
                             ("vdco", "Nominal DC voltage (Vdco)", "V"), ("pso", "Self-consumption (Pso)", "W"),
                             ("pnt", "Night consumption (Pnt)", "W"), ("c0", "C0", "1/W"), ("c1", "C1", "1/V"),
                             ("c2", "C2", "1/V"), ("c3", "C3", "1/V")):
        add(S, label, inv.get(key), unit, DB)
    add(S, "Library MPPT range", f"{_n(inv.get('mppt_low'))}-{_n(inv.get('mppt_high'))}", "V", DB)
    add(S, "Library max DC voltage", inv.get("vdcmax"), "V", DB)
    add(S, "Modeled MPPT low", 0, "V", DEF)
    add(S, "Modeled MPPT high (= system max voltage)", sv, "V", CALC)
    add(S, "Modeled max DC voltage (= system max voltage)", sv, "V", CALC)
    add(S, "Temperature derate", "SAM CEC database derate curve", "", DEF)

    # ---------------- System design ----------------
    S = "System design"
    rk = d["racking"]
    add(S, "Mounting type", RACK_TEXT[rk])
    add(S, "Modules per string", d["modules_per_string"], "modules")
    add(S, "System max voltage", sv, "V")
    if rk == "tracker":
        add(S, "Tilt", 0, "°", DEF)
        add(S, "Rotation limit", d["rotlim"], "°")
        add(S, "Backtracking", "On", "", DEF)
    else:
        add(S, "Tilt", d["tilt"], "°")
    add(S, "Azimuth", d["azimuth"], "°")
    add(S, "Module orientation", d["orientation"].capitalize())
    if bif:
        length(S, "Ground clearance", d["ground_clearance"], d.get("ground_clearance_entered"),
               d.get("ground_clearance_units", "m"))
    add(S, "Modules High", d["modules_high"], "modules")
    add(S, "Modules Across", d["modules_across"], "modules")
    add(S, "Strings modeled", d["nstrings"], "strings", CALC)
    add(S, "Rows modeled", d["rows"], "rows")
    add(S, "Self-shading", shading_text(d))
    if d["gcr_mode"] == "carport":
        add(S, "GCR", d["gcr"], "", DEF)
    elif d["gcr_mode"] == "gcr":
        add(S, "GCR", d["gcr"])
        add(S, "Equivalent row pitch", round(d["pitch"], 3) if d["pitch"] else None, "m", CALC)
    else:
        length(S, "Row pitch", d["pitch"], d.get("pitch_entered"), d.get("pitch_units", "m"))
        if d["modules_high"] >= 2:
            length(S, "Module spacing", d["gap"], d.get("gap_in"), "in")
        add(S, "GCR", round(d["gcr"], 4), "", CALC)
    add(S, "Inverters modeled", d.get("ninverters", 1), "inverters", DEF)
    add(S, "System capacity modeled", round(d["nstrings"] * d["modules_per_string"]
                                            * (m["v_mp_ref"] or 0) * (m["i_mp_ref"] or 0) / 1000, 3), "kWdc", CALC)
    add(S, "Losses (soiling, mismatch, wiring, diodes, nameplate, tracking, rack shading)", 0, "%", DEF)
    add(S, "External shading", "None", "", DEF)
    add(S, "Snow model", "Off", "", DEF)
    add(S, "Grid limits", "None", "", DEF)
    return rows
