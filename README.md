# PPE SAM Multi-Year Simulation — v0.3.1

Pure Power Engineering Inc. Downloads every NSRDB PSM v4 year, runs SAM (NLR-PySAM 8.0.0) once per year, and reports the worst-case consecutive 3-hour averages of string Isc, Voc and Vmp, plus the NEC 70% floor check.

## Run

1. Python 3.14 must be installed.
2. On GitHub, pick the branch (`main` is the live version), click **Code > Download ZIP**, unzip to a new folder and double-click `run_from_source.bat` (first run sets itself up).
3. The browser opens at `http://127.0.0.1:8765`. Keep the console window open.

Tip: after entering the location, click **Retrieve weather** to download the weather in the background while you fill out the rest of the page.

Weather cache folder: `%LOCALAPPDATA%\PPE_SAM_MultiYear\weather` (delete it to force fresh downloads). Files are stored per NSRDB grid cell, so nearby sites share them.

| Script | Purpose |
|---|---|
| `run_from_source.bat` | Runs the app |
| `run_tests.bat` | Automated tests + real CEC library check |
| `build_exe.bat` | Optional .exe (may be blocked by company policy) |

Version history: [CHANGELOG.md](CHANGELOG.md).
