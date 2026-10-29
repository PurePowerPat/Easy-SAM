"""SAM case inputs (.json): same layout as SAM 2026.7.3 "Generate code > JSON for inputs", and complete
enough that loading the file into a fresh model reproduces the app's run exactly."""
import json, os, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp()
os.environ["PPE_SAM_LIB_DIR"] = str(ROOT / "tests" / "fixtures")
import PySAM.Pvsamv1 as pvsam  # noqa: E402
from ppe_sam import exports, model, weather  # noqa: E402

SAM_FILE = json.loads((ROOT / "tests" / "fixtures" / "SAM 2026.7.3 JSON for inputs.json").read_text())
BASE = dict(lat=33.4, lon=-112.0, interval=60, inverter_name="TEST Central 2500kW", modules_per_string=28,
            system_voltage=1500, racking="tracker", rotlim=60, azimuth=180, orientation="portrait", modules_high=1,
            modules_across=28, rows=1, self_shading="standard", pitch=6, pitch_units="m")
CEC = dict(module_name="TEST Bifacial 530W", isc_datasheet=13.9, ground_clearance=2.5, ground_clearance_units="m",
           bifaciality_base=70, bifaciality_tol=5, bifacial_gain=10)
CUSTOM = dict(module_source="custom", custom_name="Custom 530W", custom_celltech="0", custom_nser=72, custom_voc=49.2,
              custom_isc=13.71, custom_vmp=41.4, custom_imp=12.82, custom_bvoc=-0.140712, custom_bvoc_units="abs",
              custom_aisc=0.005484, custom_aisc_units="abs", custom_gpmp=-0.35, custom_tnoct=43.1,
              module_length=2277.2, module_width=1132.9, self_shading="none")       # TEST Bifacial 530W specs


def kind(v):
    if isinstance(v, str):
        return "text"
    if isinstance(v, (list, tuple)):
        return "table" if v and isinstance(v[0], (list, tuple)) else "list"
    return "number"


def check(design):
    inputs = model.build_inputs(model.validate_design(design))
    path = Path(tempfile.mkdtemp()) / "2003.csv"
    path.write_text(weather._selftest_csv(2003, 33.4, -112.0))
    data = json.loads(json.dumps(exports.sam_case_json(inputs, path)))       # through JSON, as the file is
    assert set(data) == set(SAM_FILE), (sorted(set(SAM_FILE) - set(data)), sorted(set(data) - set(SAM_FILE)))
    wrong = [k for k in data if kind(data[k]) != kind(SAM_FILE[k])]
    assert not wrong, wrong
    assert data["solar_resource_file"] == str(path).replace("\\", "/")
    m = pvsam.new()                                   # load the file the way the PySAM docs show
    for k, v in data.items():
        if k in exports.SAM_JSON_HEADER or k.startswith(("metric_", "number_metrics")):
            continue
        m.value("sixpar_" + k[5:] if k.startswith("6par_") else k, v)
    m.execute(0)
    _, app = model.run_year((2003, str(path), inputs))
    for key, var in model.OUTPUT_VARS.items():
        assert list(getattr(m.Outputs, var)) == app[key], key
    return data


if __name__ == "__main__":
    d = check({**BASE, **CEC})
    assert d["module_model"] == 1 and d["cec_i_sc_ref"] == 13.71 and d["subarray1_shade_mode"] == 1
    d = check({**BASE, **CUSTOM})
    assert d["module_model"] == 2 and d["6par_isc"] == 13.71 and d["6par_celltech"] == 0
    print("SAM JSON TEST PASSED")
