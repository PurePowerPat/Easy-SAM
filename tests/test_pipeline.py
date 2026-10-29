"""Offline end-to-end: fixture libraries + synthetic NSRDB-format weather -> PySAM -> analysis.

The locked results are the v0.1.6 values; a change to them means the calculation changed.
Exception: since v0.3.5, Voc is the maximum single time-step value (was the max 3-hour average).
"""
from pathlib import Path

import pytest

from ppe_sam import analysis, inputs_export, jobs, libraries, model, report, weather

BASE = dict(lat=39.18886, lon=-76.600953, interval=60, inverter_name="TEST Central 2500kW",
            modules_per_string=28, modules_high=1, modules_across=28,
            orientation="portrait", azimuth=180, rows=1, isc_datasheet=13.9)
TRK = dict(racking="tracker", rotlim=60, ground_clearance=2.5)
BIF = dict(module_name="TEST Bifacial 530W", bifaciality_base=70, bifaciality_tol=5, bifacial_gain=10)
TRACKER_BIFACIAL = {**BASE, **TRK, **BIF, "pitch": 6}


def errs(design):
    try:
        model.validate_design(design)
    except model.DesignError as e:
        return [x["field"] for x in e.errors]
    return []


def run(design, tmp_path, years=(2001, 2002), interval=60):
    d = model.validate_design(design)
    inputs = model.build_inputs(d)
    per, stamps, files = {}, {}, []
    for y in years:
        p = tmp_path / f"{y}.csv"
        p.write_text(weather._selftest_csv(y, d["lat"], d["lon"], interval))
        yy, out = model.run_year((y, str(p), inputs))
        per[yy] = out
        stamps[yy] = weather.read_timestamps(p)
        files.append((y, p))
    return d, analysis.summarize(per, stamps, interval), inputs, files


def rounded(s):
    return {k: round(v["value"], 2) for k, v in s["worst"].items()}


def test_basics():
    assert analysis.best_window([0, 0, 1, 5, 9, 4, 0, 0], 3)[1] == 6.0
    assert libraries.modules()["TEST Bifacial 530W"]["gamma_r"] == -0.35
    assert libraries.modules()["TEST Bifacial 530W"]["celltech"] == 0
    assert (Path(model.__file__).parent / "static" / "logo.png").is_file()


def test_self_shading_input():
    d = model.validate_design(TRACKER_BIFACIAL)                     # not given: PPE standard for the module
    assert d["self_shading"] == "standard" and "self_shading" not in d["_entered"]
    assert {r["input"]: r for r in report.build(d)}["Self-shading"]["method"] == "Default"
    assert errs({**TRACKER_BIFACIAL, "self_shading": "bogus"}) == ["self_shading"]
    for key, code in (("none", 0), ("standard", 1), ("thin_film", 2)):
        d = model.validate_design({**TRACKER_BIFACIAL, "self_shading": key})
        assert model.build_inputs(d)["Shading"]["subarray1_shade_mode"] == code
        assert d["self_shading_ppe"] == "standard"
    d = model.validate_design({**TRACKER_BIFACIAL, "self_shading": "none"})
    by = {r["input"]: r for r in report.build(d)}
    s = by["Self-shading"]
    assert s["value"] == "None (PPE standard: Standard)" and s["method"] == "User entered" and s["key"]
    assert by["Calculate bifacial electrical mismatch"]["method"] == "Default"            # off = PPE standard
    assert s["section"] == "Advanced settings"
    group, settings = jobs.review({**TRACKER_BIFACIAL, "self_shading": "none"})["groups"][4]
    settings = dict(settings)
    assert group == "Advanced settings"
    assert settings["Self-shading"] == "None ⚠ PPE standard is Standard" and settings["Number of rows"] == "1"
    assert settings["Bifacial electrical mismatch"] == "Exclude"
    assert settings["Inverter voltage limits"] == "Vmppt low 0 V · Vmppt high 1500 V · Vdc max 1500 V"
    assert [r["input"] for r in report.build(d) if r["section"] == "Advanced settings"] == [
        "Calculate bifacial electrical mismatch", "Self-shading", "Vmppt low", "Vmppt high", "Vdc max",
        "Number of rows"]                                                       # Advanced Settings page order
    assert by["Number of rows"]["method"] == "Default"
    mono = model.validate_design({**BASE, **TRK, "module_name": "TEST Mono 400W", "pitch": 6, "self_shading": "none"})
    assert mono["self_shading_ppe"] == "none"
    assert {r["input"]: r for r in report.build(mono)}["Self-shading"]["value"] == "None"


def test_nec_floor_uses_datasheet_isc():
    base = {**TRACKER_BIFACIAL, "self_shading": "standard"}
    assert errs({k: v for k, v in base.items() if k != "isc_datasheet"}) == ["isc_datasheet"]   # required
    assert errs({**base, "isc_datasheet": 500}) == ["isc_datasheet"]
    d = model.validate_design(base)
    assert d["isc_datasheet"] == 13.9 and d["module"]["i_sc_ref"] == 13.71   # library value is not used
    assert round(analysis.nec_floor(d["isc_datasheet"], d["bifacial"], d["bifacial_gain"]), 4) == 13.3788
    row = {r["input"]: r for r in report.build(d)}["Isc (datasheet) for NEC 70% check"]
    assert row["value"] == "13.9" and row["method"] == "User entered" and row["key"]
    assert dict(jobs.review(base)["groups"][1][1])["NEC 70% check"] == "Isc (datasheet) 13.9 A"


@pytest.mark.parametrize("field", ["lat", "azimuth", "isc_datasheet", "bifacial_gain", "pitch", "modules_across"])
@pytest.mark.parametrize("text", ["nan", "NaN", "inf", "-inf"])
def test_non_finite_numbers_are_rejected(field, text):
    # float() accepts these; NaN passes every range check and would make the NEC floor NaN.
    assert errs({**TRACKER_BIFACIAL, field: text}) == [field]


@pytest.mark.parametrize(("field", "value"), [("interval", "30.5"), ("interval", "15")])
def test_select_values_must_match_exactly(field, value):
    assert errs({**TRACKER_BIFACIAL, field: value}) == [field]


def test_make_model_rejects_unknown_inputs():
    inputs = model.build_inputs(model.validate_design(TRACKER_BIFACIAL))
    model.make_model(inputs)                                       # every app setting is a real SAM input
    with pytest.raises(KeyError, match="subarray1_tilt_typo"):
        model.make_model({**inputs, "SystemDesign": {**inputs["SystemDesign"], "subarray1_tilt_typo": 5}})
    with pytest.raises(KeyError, match="NoSuchGroup"):
        model.make_model({**inputs, "NoSuchGroup": {}})


def test_locked_results_with_ppe_standard_shading(tmp_path):
    d, s, inputs, files = run({**TRACKER_BIFACIAL, "pitch": 6.0, "self_shading": "standard",
                               "module_length": "2277.2", "module_width": "1132.9"}, tmp_path)
    assert rounded(s) == {"isc_max": 15.19, "voc_max": 1403.34, "vmp_max": 1218.93, "vmp_min": 1034.2}
    exp = {r[0]: r for r in inputs_export.build_rows(d, inputs, files)[1]}
    assert exp["subarray1_shade_mode"][2] == "PPE default" and exp["subarray1_shade_mode"][5].startswith("Standard")
    _, s, *_ = run({**BASE, **BIF, "racking": "carport", "tilt": 7, "ground_clearance": 5.0, "self_shading": "standard",
                    "modules_per_string": 26, "modules_high": 14, "modules_across": 7, "orientation": "landscape"},
                   tmp_path, years=(2003,))
    assert rounded(s) == {"isc_max": 14.39, "voc_max": 1302.14, "vmp_max": 1131.82, "vmp_min": 968.69}
    _, s, *_ = run({**BASE, "module_name": "TEST Mono 400W", "racking": "fixed", "tilt": 25, "self_shading": "none",
                    "gcr_mode": "gcr", "gcr": 0.45, "modules_high": 2, "modules_across": 14,
                    "inverter_name": "TEST String 125kW", "interval": 30}, tmp_path, years=(2003,), interval=30)
    assert rounded(s) == {"isc_max": 10.28, "voc_max": 1331.42, "vmp_max": 1156.14, "vmp_min": 984.94}


def test_shading_choice_changes_results(tmp_path):
    common = {**BASE, **BIF, "racking": "fixed", "tilt": 20, "ground_clearance": 1.0, "modules_per_string": 26,
              "modules_high": 2, "modules_across": 13, "gap": 0.7874, "pitch": 5.0, "rows": 1}
    out = {k: rounded(run({**common, "self_shading": k}, tmp_path, years=(2003,))[1])
           for k in ("none", "standard", "thin_film")}
    assert len({v["isc_max"] for v in out.values()}) >= 2     # the choice reaches SAM


def test_voc_is_the_max_single_time_step():
    per = {2001: {"isc": [0, 1, 1, 1, 0], "voc": [0, 10, 40, 10, 0], "vmp": [0, 5, 5, 5, 0]},
           2002: {"isc": [0, 2, 2, 2, 0], "voc": [0, 30, 30, 30, 0], "vmp": [0, 6, 6, 6, 0]}}
    import datetime as dt
    ts = [dt.datetime(2001, 1, 1, h) for h in range(5)]
    s = analysis.summarize(per, {2001: ts, 2002: ts}, 60)["worst"]
    assert s["voc_max"]["value"] == 40 and s["voc_max"]["year"] == 2001 and s["voc_max"]["window_steps"] == 1
    assert s["isc_max"]["value"] == 2 and s["isc_max"]["window_steps"] == 3          # still the 3-hour average


def test_inverter_voltage_limits():
    d = model.validate_design(TRACKER_BIFACIAL)                                   # not sent: PPE defaults
    assert (d["vmppt_low"], d["vmppt_high"], d["vdc_max"]) == (0, 1500, 1500) and d["inverter_limits_default"]
    inv = model.build_inputs(d)
    assert inv["Inverter"]["mppt_low_inverter"] == 0 and inv["Inverter"]["mppt_hi_inverter"] == 1500
    assert inv["InverterCECDatabase"]["inv_snl_vdcmax"] == 1500
    by = {r["input"]: r for r in report.build(d)}
    assert all(by[k]["method"] == "Default" for k in ("Vmppt low", "Vmppt high", "Vdc max"))

    d = model.validate_design({**TRACKER_BIFACIAL, "vmppt_low": "500", "vmppt_high": "1300", "vdc_max": "1400"})
    inv = model.build_inputs(d)
    assert inv["Inverter"]["mppt_low_inverter"] == 500 and inv["Inverter"]["mppt_hi_inverter"] == 1300
    assert inv["InverterCECDatabase"]["inv_snl_vdcmax"] == 1400
    assert inv["InverterCECDatabase"]["inv_tdc_cec_db"][0][0] == 1400
    assert not d["inverter_limits_default"]
    by = {r["input"]: r for r in report.build(d)}
    assert by["Vmppt low"]["method"] == "User entered" and by["Vdc max"]["value"] == "1,400"
    review = dict(jobs.review({**TRACKER_BIFACIAL, "vmppt_low": "500"})["groups"][4][1])
    assert review["Inverter voltage limits"].endswith("⚠ PPE default is 0 · 1500 · 1500 V")

    assert errs({**TRACKER_BIFACIAL, "vmppt_low": "1500"}) == ["vmppt_high"]       # low must be below high
    assert errs({**TRACKER_BIFACIAL, "vmppt_high": "0"}) == ["vmppt_high"]
    assert errs({**TRACKER_BIFACIAL, "vdc_max": "nan"}) == ["vdc_max"]
    assert errs({**TRACKER_BIFACIAL, "vdc_max": "2500"}) == ["vdc_max"]
    assert errs({**TRACKER_BIFACIAL, "vmppt_low": "-1"}) == ["vmppt_low"]


def test_inverter_limits_reach_sam(tmp_path):
    common = {**TRACKER_BIFACIAL, "self_shading": "standard"}
    _, s, *_ = run(common, tmp_path, years=(2003,))
    _, low, *_ = run({**common, "vmppt_low": "1250"}, tmp_path, years=(2003,))
    assert rounded(s)["vmp_min"] < 1250 and rounded(low)["vmp_min"] == 1250       # SAM holds Vmp at Vmppt low
    assert rounded(low)["voc_max"] == rounded(s)["voc_max"]                        # Voc is not limited
