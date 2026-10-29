# PPE SAM Multi-Year Simulation

Pure Power Engineering Inc. Downloads every NSRDB PSM v4 year for a site, runs SAM (NLR-PySAM 8.0.0)
once per year, and reports the worst-case consecutive 3-hour averages of string Isc, Voc and Vmp, plus
the NEC 70% floor check. Current version: see [VERSION.txt](VERSION.txt); history:
[CHANGELOG.md](CHANGELOG.md).

## Run

1. Python 3.12–3.14 must be installed (3.14 recommended: `py install 3.14`).
2. On GitHub, pick the branch (`main` is the live version), click **Code > Download ZIP**, unzip to a
   new folder and double-click `run_from_source.bat` (first run sets itself up).
3. The browser opens at `http://127.0.0.1:8765`. Keep the console window open.

Tip: after entering the location, click **Retrieve weather** to download the weather in the background
while you fill out the rest of the page.

Weather cache folder: `%LOCALAPPDATA%\PPE_SAM_MultiYear\weather` (delete it to force fresh downloads).
Files are stored per NSRDB grid cell, so nearby sites share them.

| Script | Purpose |
|---|---|
| `run_from_source.bat` | Runs the app |
| `run_tests.bat` | Automated tests (pytest) + real CEC library check |
| `build_exe.bat` | Optional .exe (may be blocked by company policy) |

## Developer notes

A local web app: `run_app.py` starts a standard-library HTTP server on 127.0.0.1 that serves one
page and a small JSON API. No third-party dependencies besides PySAM.

| Module (`ppe_sam/`) | Responsibility |
|---|---|
| `server.py` | HTTP server and JSON API; accepts requests only from the app's own page |
| `jobs.py` | Background jobs: weather retrieval, then one SAM run per year (process pool), then analysis |
| `model.py` | Input validation (`validate_design`) and the SAM model settings (`build_inputs`) |
| `weather.py` | NSRDB download, throttling, and the per-grid-cell weather cache |
| `analysis.py` | Rolling 3-hour windows and the NEC 70% floor |
| `report.py` | The "Inputs used" table |
| `exports.py`, `inputs_export.py` | CSV / JSON downloads (incl. SAM's "JSON for inputs" format) |
| `libraries.py` | CEC module and inverter libraries (`libraries/*.csv`) |
| `config.py` | Fixed settings (NSRDB, PPE standards, folders) |
| `static/` | The page: `index.html`, `app.css`, `app.js` |

Tests run offline (fixture libraries in `tests/fixtures`, synthetic NSRDB weather, a temporary data
folder). The locked results in `tests/test_pipeline.py` are the v0.1.6 values: if they change, the
calculation changed.

Outside Windows, or without the .bat files (on Windows use `.venv\Scripts\` instead of `.venv/bin/`):

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
.venv/bin/ruff check .
.venv/bin/python run_app.py
```

The version number lives only in `ppe_sam/__init__.py`; for a release also update `VERSION.txt` and
`CHANGELOG.md`.
