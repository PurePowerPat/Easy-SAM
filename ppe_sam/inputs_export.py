"""SAM inputs browser export (Results > Downloads > "SAM inputs browser (.csv)"), for checking a run against SAM.

Matches the variable list of a SAM Inputs Browser export.

Rows 1..356: every variable from the PPE sample SAM Inputs Browser export (data/inputs_browser_vars.csv).
Then: CEC database / simulation-core values the run uses that SAM's Inputs Browser does not list.
For custom modules, the six single-diode parameters SAM calculates are listed too.

Columns: Variable, Label, Source, Used in run, Note, then one value column per year.
"""
import csv
import io
from pathlib import Path

from . import config, libraries, report
from . import model as model_mod

_LOCAL = Path(__file__).resolve().parent / "data" / "inputs_browser_vars.csv"
_BUNDLED = config.bundle_dir() / "ppe_sam" / "data" / "inputs_browser_vars.csv"
VARS_FILE = _BUNDLED if _BUNDLED.exists() else _LOCAL

U, PD, PC, SC, SD, ER = ("User input", "PPE default", "PPE calculated",
                         "SAM calculated", "SAM default", "Error")

STANDOFF_TEXT = {0: "Building integrated", 1: "Greater than 3.5 in", 2: "2.5 to 3.5 in", 3: "1.5 to 2.5 in",
                 4: "0.5 to 1.5 in", 5: "Less than 0.5 in", 6: "Ground or rack mounted"}
HEIGHT_TEXT = {0: "One story building height or lower", 1: "Two story building height or higher"}

TEXT_MAPS = {
    "cec_standoff": STANDOFF_TEXT, "cec_height": HEIGHT_TEXT,
    "sixpar_standoff": STANDOFF_TEXT, "sixpar_mounting": HEIGHT_TEXT,
    "sixpar_celltech": libraries.CELLTECH_TEXT,
    "sd11par_standoff": STANDOFF_TEXT, "sd11par_mounting": HEIGHT_TEXT,
    "sd11par_glass": {0: "Standard glass", 1: "Anti-reflective glass"},
    "snl_module_structure": {0: "Use Database Values", 1: "Glass/Cell/Polymer Sheet - Open Rack",
                             2: "Glass/Cell/Glass - Open Rack", 3: "Polymer/Thin Film/Steel - Open Rack",
                             4: "Insulated Back (BIPV)", 5: "Close Roof Mount", 6: "User Defined"},
    "spe_module_structure": {0: "Glass/Cell/Polymer Sheet - Open Rack", 1: "Glass/Cell/Glass - Open Rack",
                             2: "Polymer/Thin Film/Steel - Open Rack", 3: "Insulated Back (BIPV)",
                             4: "Close Roof Mount", 5: "User Defined"},
    "cec_heat_transfer": {0: "Module Dimensions", 1: "Array Dimensions"},
    "cec_mounting_config": {0: "Rack", 1: "Flush", 2: "Integrated", 3: "Gap"},
    "cec_mounting_orientation": {0: "Structures do not impede flow under module", 1: "Vertical supports",
                                 2: "Horizontal supports"},
    "subarray1_shade_mode": {0: "None", 1: "Standard (non-linear)", 2: "Thin film (linear)"},
}

INACTIVE_PREFIXES = {
    "6par_": "CEC User Entered Specifications module model (not used; this run uses the CEC module database)",
    "sd11par_": "IEC 61853 single-diode module model (not used)",
    "iec61853": "IEC 61853 module model (not used)",
    "snl_": "Sandia module model (not used)",
    "spe_": "Simple efficiency module model (not used)",
    "inv_cec_cg_": "Inverter CEC Coefficient Generator model (not used; this run uses the CEC inverter database)",
    "inv_ds_": "Inverter datasheet model (not used)",
    "inv_pd_": "Inverter part-load curve model (not used)",
    "inv_tdc_cec_cg": "Inverter CEC Coefficient Generator model (not used)",
    "inv_tdc_ds": "Inverter datasheet model (not used)",
    "inv_tdc_plc": "Inverter part-load curve model (not used)",
    "subarray2_": "Subarray 2 is disabled", "subarray3_": "Subarray 3 is disabled",
    "subarray4_": "Subarray 4 is disabled",
    "albedo_": "Spatial albedo is OFF (weather-file albedo is used)",
}
INACTIVE_EXACT = {
    "albedo": "Monthly albedo: used only where the weather-file albedo is missing or invalid",
    "albedo_spatial_monthly": "Spatial albedo is OFF",
    "cec_array_cols": "Heat-transfer temperature model only (this run uses NOCT)",
    "cec_array_rows": "Heat-transfer temperature model only (this run uses NOCT)",
    "cec_backside_temp": "Heat-transfer temperature model only (this run uses NOCT)",
    "cec_heat_transfer": "Heat-transfer temperature model only (this run uses NOCT)",
    "cec_mounting_config": "Heat-transfer temperature model only (this run uses NOCT)",
    "cec_mounting_orientation": "Heat-transfer temperature model only (this run uses NOCT)",
    "cec_gap_spacing": "Heat-transfer temperature model only (this run uses NOCT)",
    "subarray1_monthly_tilt": "Seasonal tilt is not used",
    "cec_transient_thermal_model_unit_mass": "Transient thermal model only (not used)",
    "grid_curtailment": "Interconnection limit is OFF",
    "grid_interconnection_limit_kwac": "Interconnection limit is OFF",
    "snow_array": "Snow model is OFF",
}
ENABLE_FLAGS = {"subarray2_enable", "subarray3_enable", "subarray4_enable"}
UI_ONLY_NOTE = "SAM interface only"

EXTRA_VARS = [
    ("module_model", "Module model (1 = CEC Performance Model with Module Database)"),
    ("cec_area", "CEC module: area (m2)"), ("cec_n_s", "CEC module: cells in series"),
    ("cec_i_sc_ref", "CEC module: Isc at STC (A)"), ("cec_v_oc_ref", "CEC module: Voc at STC (V)"),
    ("cec_i_mp_ref", "CEC module: Imp at STC (A)"), ("cec_v_mp_ref", "CEC module: Vmp at STC (V)"),
    ("cec_alpha_sc", "CEC module: Isc temperature coefficient (A/C)"),
    ("cec_beta_oc", "CEC module: Voc temperature coefficient (V/C)"),
    ("cec_a_ref", "CEC module: a_ref"), ("cec_i_l_ref", "CEC module: I_L_ref"),
    ("cec_i_o_ref", "CEC module: I_o_ref"), ("cec_r_s", "CEC module: R_s"),
    ("cec_r_sh_ref", "CEC module: R_sh_ref"), ("cec_adjust", "CEC module: Adjust"),
    ("cec_t_noct", "CEC module: NOCT (C)"),
    ("cec_module_length", "Module length (m)"), ("cec_module_width", "Module width (m)"),
    ("inverter_model", "Inverter model (0 = CEC Database)"),
    ("inv_snl_paco", "CEC inverter: Paco (W)"), ("inv_snl_pdco", "CEC inverter: Pdco (W)"),
    ("inv_snl_vdco", "CEC inverter: Vdco (V)"), ("inv_snl_pso", "CEC inverter: Pso (W)"),
    ("inv_snl_pnt", "CEC inverter: Pnt (W)"), ("inv_snl_c0", "CEC inverter: C0"),
    ("inv_snl_c1", "CEC inverter: C1"), ("inv_snl_c2", "CEC inverter: C2"),
    ("inv_snl_c3", "CEC inverter: C3"), ("inv_snl_vdcmax", "Inverter Vdcmax used (V)"),
    ("module_aspect_ratio", "Module aspect ratio used by the simulation"),
    ("system_capacity", "System capacity (kWdc)"),
    ("solar_resource_file", "Weather file used"),
]
CUSTOM_EXTRA_VARS = [
    ("sixpar_aisc", "Custom module: Isc temperature coefficient used by SAM (A/°C)"),
    ("sixpar_bvoc", "Custom module: Voc temperature coefficient used by SAM (V/°C)"),
]
MODULE_LIB_COLS = {
    "cec_area": "A_c", "cec_n_s": "N_s", "cec_i_sc_ref": "I_sc_ref", "cec_v_oc_ref": "V_oc_ref",
    "cec_i_mp_ref": "I_mp_ref", "cec_v_mp_ref": "V_mp_ref", "cec_alpha_sc": "alpha_sc",
    "cec_beta_oc": "beta_oc", "cec_a_ref": "a_ref", "cec_i_l_ref": "I_L_ref", "cec_i_o_ref": "I_o_ref",
    "cec_r_s": "R_s", "cec_r_sh_ref": "R_sh_ref", "cec_adjust": "Adjust", "cec_t_noct": "T_NOCT",
}
INVERTER_LIB_COLS = {
    "inv_snl_paco": "Paco", "inv_snl_pdco": "Pdco", "inv_snl_vdco": "Vdco", "inv_snl_pso": "Pso",
    "inv_snl_pnt": "Pnt", "inv_snl_c0": "C0", "inv_snl_c1": "C1", "inv_snl_c2": "C2", "inv_snl_c3": "C3",
}


def load_vars():
    with open(VARS_FILE, newline="", encoding="utf-8") as fh:
        rdr = csv.reader(fh)
        next(rdr)
        return [(r[0], r[1]) for r in rdr if r]


def _fmt(v):
    if v is None:
        return "Error"
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return str(int(v))
    if isinstance(v, (int, float)):
        f = float(v)
        return str(int(f)) if f.is_integer() and abs(f) < 1e15 else f"{f:.10g}"
    if isinstance(v, (list, tuple)):
        if v and isinstance(v[0], (list, tuple)):
            return "".join("[" + ";".join(_fmt(x) for x in row) + "]" for row in v)
        return ";".join(_fmt(x) for x in v)
    return str(v)


def _ssc(m, name):
    cands = [name] + {"adjust": ["adjust_constant"], "dc_adjust": ["dc_adjust_constant"],
                      "ui_aspect_ratio": ["module_aspect_ratio"],
                      "vdcmax_inverter": ["inv_snl_vdcmax"]}.get(name, [])
    if name.startswith("6par_"):
        base = "sixpar_" + name[5:]
        cands += [base, base.replace("_display", "")]
    for c in cands:
        try:
            return True, c, m.value(c)
        except Exception:  # noqa: BLE001
            continue
    return False, None, None


def _text(ssc_name, v):
    tm = TEXT_MAPS.get(ssc_name)
    if tm is None:
        return v
    try:
        return tm.get(int(v), v)
    except (TypeError, ValueError):
        return v


CUSTOM_CEC_NOTE = "CEC Performance Model with Module Database (not used; this run uses a custom module)"


def _inactive(var, custom=False):
    if var in ENABLE_FLAGS:
        return None
    if custom:
        if var.startswith("cec_"):
            return CUSTOM_CEC_NOTE
        if var.startswith("6par_"):
            return "Module unit mass (transient thermal model, not used)" if "transient" in var else None
    if var in INACTIVE_EXACT:
        return INACTIVE_EXACT[var]
    if var.startswith("subarray1_shading") and not var.startswith("subarray1_shading_en"):
        return "Shading inputs are OFF"
    for p, why in INACTIVE_PREFIXES.items():
        if var.startswith(p):
            return why
    return None


UNIT_TEXT = {"bvoc": {"pct": "%/°C", "abs": "V/°C"}, "aisc": {"pct": "%/°C", "abs": "A/°C"}}


def _custom_ui_value(d, var):
    m, cu = d["module"], d["custom"]
    aisc_unit, bvoc_unit = UNIT_TEXT["aisc"][cu["aisc_units"]], UNIT_TEXT["bvoc"][cu["bvoc_units"]]
    return {
        "module_name": (m["name"], U, "Custom module name"),
        "6par_module_name": (m["name"], U, "Custom module name"),
        "6par_celltech": (m["technology"], U, "Cell type selected"),
        "6par_aspect_ratio": (d["aspect_ratio"], PC, "Module length / width"),
        "6par_aisc_display": (cu["aisc_entered"], U, f"Entered as {cu['aisc_entered']:g} {aisc_unit}"),
        "6par_aisc_units": (aisc_unit, U, "Units selected for the Isc temperature coefficient"),
        "6par_bvoc_display": (cu["bvoc_entered"], U, f"Entered as {cu['bvoc_entered']:g} {bvoc_unit}"),
        "6par_bvoc_units": (bvoc_unit, U, "Units selected for the Voc temperature coefficient"),
    }.get(var)


def _ui_value(d, var, path):
    if d.get("module_source") == "custom":
        cv = _custom_ui_value(d, var)
        if cv is not None:
            return cv
    pitch_note = (f"Row pitch ({d['pitch_entered']:g} in entered x 0.0254)" if d.get("pitch_units") == "in"
                  else "Row pitch (m)")
    coords = f"{d['lat']},{d['lon']}"
    loc = ((d["address"], U, f"Address; coordinates from {d.get('geocode_source') or 'geocoder'}: {coords}")
           if d.get("location_mode") == "address" else (coords, U, "Latitude, longitude"))
    return {
        "module_name": (d["module"]["name"], U, "Selected from the CEC module library"),
        "inv_cec_name": (d["inverter"]["name"], U, "Selected from the CEC inverter library"),
        "in_location": loc,
        "in_time_step": (0 if d["interval"] == 60 else 1, U if "interval" in d["_entered"] else PD,
                         f"Weather interval {d['interval']} min"),
        "in_nsrdb_options": ("Download files for all years", PD, "Every available NSRDB PSM v4 year"),
        "in_location_options": (0, PD, "Single location"),
        "use_specific_weather_file": (1, PD, "Each year runs on its own downloaded NSRDB file"),
        "user_specified_weather_file": (str(path), PD, "Downloaded NSRDB PSM v4 file for this year"),
        "solar_resource": (Path(path).name, PD, "Downloaded NSRDB PSM v4 file for this year"),
        "ui_chkbox_nmodx_eq_mod_per_string": (0, PD, f"{UI_ONLY_NOTE} - not a simulation input. "
                                                     "subarray1_nmodx is set directly from Modules Across"),
        "is_advanced": (0, PD, "Standard NSRDB download"),
        "subarray1_ui_row_spacing": {
            "pitch": (d["pitch"], U, pitch_note),
            "gcr": (d["pitch"], PC, "Equivalent row pitch = Modules High x module dimension along slope / GCR"),
            "carport": (None, ER, "Carport: no row pitch (GCR fixed at 0.01)"),
        }[d["gcr_mode"]],
    }.get(var)


def classify(var, d, assigned):
    e = set(d["_entered"])
    rk = d["racking"]
    m = d["module"]
    racking_txt = config.RACKING_LABELS[rk]
    gc_note = (f"Ground clearance height ({d['ground_clearance_entered']:g} in entered x 0.0254)"
               if d.get("ground_clearance_units") == "in" else "Ground clearance height")
    bif_note = f"(base {d.get('bifaciality_base')}% + tolerance {d.get('bifaciality_tol')}%) / 100"
    mism = ((U, "Bifacial electrical mismatch: Include (Advanced Settings)") if d.get("bifacial_mismatch")
            else (PD, "Exclude (PPE default)") if d["bifacial"] else (PD, "Monofacial: off"))

    def limit(key):
        label, default = config.INVERTER_LIMITS[key]
        if d[key] == default:
            return PD, f"{label} = {default:g} V (PPE default: the inverter never limits Vmp or clips)"
        return U, f"{label} entered on Advanced Settings (PPE default {default:g} V)"
    if var == "subarray1_shade_mode":
        src = PD if d["self_shading"] == d["self_shading_ppe"] else U
        return src, f"Self-shading selected: {report.shading_text(d)}"

    if d.get("module_source") == "custom":
        if var.startswith("cec_"):
            return SD, ""
        cu = d["custom"]
        custom_rules = {
            "module_model": (U, "Custom module selected (2 = CEC Performance Model with User Entered Specifications)"),
            "sixpar_nser": (U, "Cells in series"), "sixpar_voc": (U, "Voc"), "sixpar_isc": (U, "Isc"),
            "sixpar_vmp": (U, "Vmp"), "sixpar_imp": (U, "Imp"),
            "sixpar_gpmp": (U, "Pmp temperature coefficient (%/°C)"), "sixpar_tnoct": (U, "NOCT"),
            "sixpar_celltech": (U, "Cell type selected"),
            "sixpar_aisc": (U, "Isc temperature coefficient entered in A/°C") if cu["aisc_units"] == "abs"
                           else (PC, f"{cu['aisc_entered']:g} %/°C entered x Isc / 100 = A/°C"),
            "sixpar_bvoc": (U, "Voc temperature coefficient entered in V/°C") if cu["bvoc_units"] == "abs"
                           else (PC, f"{cu['bvoc_entered']:g} %/°C entered x Voc / 100 = V/°C"),
            "sixpar_area": (PC, "Module length x width"),
            "sixpar_is_bifacial": (U, "'Module is bifacial' checkbox"),
            "sixpar_bifaciality": (PC, bif_note) if d["bifacial"] else (PD, "Monofacial module: 0"),
            "sixpar_bifacial_ground_clearance_height": (U, gc_note) if "ground_clearance" in e
                                                      else (PD, "Monofacial: not used by SAM"),
            "sixpar_bifacial_transmission_factor": (PD, "SAM default kept per PPE guide"),
            "sixpar_standoff": (PD, "Mounting configuration: ground or rack mounted"),
            "sixpar_mounting": (PD, "Mounting configuration: one story or lower"),
            "system_capacity": (PC, "Strings x modules per string x Vmp x Imp (custom) / 1000"),
        }
        if var in custom_rules:
            return custom_rules[var]
        if var.startswith("sixpar_"):
            return SD, ""

    if var in MODULE_LIB_COLS:
        return SC, f"CEC module database: {m['name']} [{MODULE_LIB_COLS[var]}]"
    if var in INVERTER_LIB_COLS:
        return SC, f"CEC inverter database: {d['inverter']['name']} [{INVERTER_LIB_COLS[var]}]"

    rules = {
        "subarray1_modules_per_string": (U, "Modules per string"),
        "subarray1_nmody": (U, "Modules High"), "subarray1_nmodx": (U, "Modules Across of full subarray"),
        "subarray1_mod_orient": (U, f"Module orientation: {d['orientation']} (0 = portrait, 1 = landscape)"),
        "subarray1_track_mode": (U, f"Racking: {racking_txt} (0 = fixed, 1 = single-axis)"),
        "subarray1_backtrack": (PD, "Backtracking ON for trackers, OFF otherwise"),
        "mppt_low_inverter": limit("vmppt_low"), "mppt_hi_inverter": limit("vmppt_high"),
        "vdcmax_inverter": limit("vdc_max"), "inv_snl_vdcmax": limit("vdc_max"),
        "inv_tdc_cec_db": (PC, "Temperature-derate table with first value = Vdc max (Advanced Settings)"),
        "cec_module_length": (U if "module_length" in e else SC,
                              f"{d['module_length_mm']:g} mm entered / 1000" if "module_length" in e
                              else f"CEC module database [Length] ({d['module_length_mm']:g} mm)"),
        "cec_module_width": (U if "module_width" in e else SC,
                             f"{d['module_width_mm']:g} mm entered / 1000" if "module_width" in e
                             else f"CEC module database [Width] ({d['module_width_mm']:g} mm)"),
        "module_aspect_ratio": (PC, "Module length / width"), "ui_aspect_ratio": (PC, "Module length / width"),
        "inverter_count": (PD, f"One inverter for all {d['nstrings']} string(s)"),
        "subarray1_nstrings": (PC, f"Fewest strings that fill {d['rows']} row(s) of Modules High x Modules Across"),
        "system_capacity": (PC, "Strings x modules per string x Vmp x Imp (CEC) / 1000"),
        "cec_bifaciality": (PC, bif_note) if d["bifacial"] else (PD, "Monofacial module: 0"),
        "cec_is_bifacial": (U, "Bifacial override checked") if d["bifacial_source"] == "user override"
                           else (SC, f"CEC module database [Bifacial] ({1 if d['bifacial'] else 0})"),
        "cec_bifacial_ground_clearance_height": (U, gc_note) if "ground_clearance" in e
                                                else (PD, "Monofacial: not used by SAM"),
        "cec_bifacial_transmission_factor": (PD, "SAM default kept per PPE guide"),
        "cec_standoff": (PD, "NOCT temperature model: ground or rack mounted"),
        "cec_height": (PD, "NOCT temperature model: one story or lower"),
        "cec_temp_corr_mode": (PD, "NOCT temperature model"),
    }
    if var == "calculate_bifacial_electrical_mismatch":
        return mism
    if var in rules:
        return rules[var]
    if var == "subarray1_tilt":
        return (PD, "Tracker: tilt 0") if rk == "tracker" else (U, "Tilt")
    if var == "subarray1_azimuth":
        return U, "Azimuth"
    if var == "subarray1_rotlim":
        return (PD, "Not used (fixed-tilt / carport)") if rk != "tracker" else (U, "Rotation limit")
    if var == "subarray1_gcr":
        return {"carport": (PD, "Carport GCR = 0.01"), "gcr": (U, "GCR entered directly"),
                "pitch": (PC, "(Modules High x module dimension along slope + spacing x (High - 1)) / row pitch"),
                }[d["gcr_mode"]]
    if var in assigned:
        return PD, "Fixed PPE setting"
    return SD, ""


def _celltech(d):
    tech = d["module"]["technology"]
    code = libraries.celltech_code(tech)
    if code is None:
        return None, ER, f"CEC module database [Technology] = '{tech}' has no matching SAM cell type"
    return (libraries.CELLTECH_TEXT[code], SC,
            f"CEC module database [Technology] = '{tech}' -> SAM cell type {libraries.CELLTECH_TEXT[code]}")


def _sixpar_rows(d, n_years):
    params = (d.get("custom") or {}).get("sixpar") or {}
    title = ("--- Custom module: single-diode parameters calculated by SAM from the datasheet values "
             "(compare with the a_ref ... Adjust columns of a CEC library module) ---")
    rows = [[title, "", "", "", ""] + [""] * n_years]
    for key, lib_col, label in model_mod.SIXPAR_OUTPUTS:
        v = params.get(key)
        rows.append([f"sixpar_calc_{key}", f"{label} [CEC Modules.csv column: {lib_col}]",
                     SC if v is not None else ER, "Yes" if v is not None else "-",
                     "Calculated by SAM (SixParsolve) from Voc, Isc, Vmp, Imp, temperature coefficients, "
                     "cells in series and cell type"] + [_fmt(v)] * n_years)
    return rows


def build_rows(design, inputs, files):
    d = design
    custom = d.get("module_source") == "custom"
    assigned = {"solar_resource_file"}
    for values in inputs.values():
        assigned.update(values.keys())
    models = {y: model_mod.make_model(inputs, p) for y, p in files}
    header = ["Variable", "Label", "Source", "Used in run", "Note"] + [str(y) for y, _ in files]
    rows = []

    def row_for(var, label):
        vals, source, note = [], None, ""
        why_inactive = _inactive(var, custom)
        for y, p in files:
            m = models[y]
            ui = _ui_value(d, var, p)
            if var == "6par_celltech" and not custom:
                v, src, nt = _celltech(d)
            elif ui is not None:
                v, src, nt = ui
            else:
                found, ssc_name, v = _ssc(m, var)
                if not found:
                    v, src, nt = None, ER, "Not set by the app and not a simulation-core value"
                else:
                    src, nt = classify(ssc_name, d, assigned)
                    v = _text(ssc_name, v)
            vals.append(_fmt(v))
            source = source or src
            note = note or nt
        used = ("No" if (why_inactive or note.startswith("Not used") or note.startswith(UI_ONLY_NOTE)
                         or note.startswith("Monofacial: not used"))
                else ("-" if source == ER else "Yes"))
        if why_inactive:
            note = why_inactive + (f". {note}" if note else "")
        return [var, label, source, used, note] + vals

    for var, label in load_vars():
        rows.append(row_for(var, label))
    listed = {r[0] for r in rows}
    rows.append(["--- Additional values used by the simulation (not in the SAM Inputs Browser list) ---",
                 "", "", "", ""] + [""] * len(files))
    for var, label in EXTRA_VARS + (CUSTOM_EXTRA_VARS if custom else []):
        if var not in listed:
            r = row_for(var, label)
            if var == "solar_resource_file":
                r[2], r[4] = PD, "Downloaded NSRDB PSM v4 file for this year"
                r[5:] = [str(p) for _, p in files]
            rows.append(r)
    if custom:
        rows.extend(_sixpar_rows(d, len(files)))
    return header, rows


def to_csv(header, rows) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    w.writerow(header)
    w.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")
