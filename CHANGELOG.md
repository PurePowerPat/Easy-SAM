# Changelog — PPE SAM Multi-Year Simulation

Every version, newest first. Entries up to v0.2.8 are the release notes written with each version
(VERSION.txt at the time), reformatted only.

Not yet recorded here: v0.1.0–v0.1.2, v0.1.7, v0.1.9–v0.2.7.

## v0.3.0 — 2026-10-28

- **NEC 70% check now uses the module's datasheet Isc** (previously the CEC library Isc).
  - CEC library modules: new required field Module > "Isc (datasheet)". It is cleared when a different
    module is selected, and the CEC library value is shown under it for comparison (with a "check the
    datasheet value" note when they differ by more than 10%).
  - Custom modules: the Isc entered on the custom module (from the datasheet) is used, as before.
  - Shown on the review screen, in Inputs used (highlighted) and in the NEC table on the Results page.
  - The simulation itself still uses the CEC library values (unchanged).
- **Weather download errors are clearer:**
  - NSRDB refusing the API key (HTTP 401/403) stops the download at once with "NSRDB refused the
    app's API key" instead of marking every year "not available".
  - NSRDB request limit (HTTP 429) still retries, but then stops with "NSRDB request limit reached.
    Wait an hour, then run again." instead of grinding through every remaining year.
  - A weather retrieval and a run downloading at the same time now share the 1-request-per-second
    limit correctly.
  - Downloads are written to a temporary file first, so an interrupted download never leaves a
    damaged weather file in the cache.
- **Weather cache is organised by NSRDB grid cell** (the file's "Location ID") instead of the exact
  coordinates. A new site in the same grid cell as a cached site needs only one download instead of
  every year. Existing cached weather is moved into the new layout automatically (no re-download).
- The app only accepts requests from its own page (blocks other websites open in the browser from
  starting runs or clearing the weather cache).
- Housekeeping: added .gitignore; Python cache files (`__pycache__`) removed from the repository;
  this changelog added.

Calculations unchanged: the locked test results (v0.1.6 values) still match.

## v0.2.8 — 2026-10-27

- System design > Subarray: new required "Self-shading" selector: None / Standard / Thin film
  (SAM subarray1_shade_mode 0 / 1 / 2). No pre-selected value.
  Under the field: "PPE standard for this module: X" (bifacial -> Standard, Thin film for thin-film
  cells; monofacial -> None). A warning appears when the selection differs from the PPE standard.
- Previously the app set self-shading automatically from the module; now the selection is used.
- Review screen, sidebar summary, modeling assumptions, Inputs used ("Self-shading", System design,
  User entered, highlighted) and the SAM inputs browser export all show the selection, with the PPE
  standard noted when it differs.

Calculations unchanged when the PPE-standard option is selected (tests locked to the v0.1.6 values).

## v0.1.8 — 2026-10-26

1. Racking type switch keeps inputs. Tilt, azimuth, orientation, Modules High/Across, row pitch or
   GCR, module spacing and ground clearance keep their values when switching between Single-axis
   tracker, Fixed-tilt and Carport. Rotation limit is tracker-only.
   Ground clearance: a value the user typed is kept. If the field still holds the PPE default the app
   filled in, it follows the racking type (tracker 2.5 m, fixed-tilt 1 m, carport 5 m).
2. Tooltip on System maximum voltage: "Select 1000V for rooftops, and 1500V otherwise."
3. Custom modules (SAM "CEC Performance Model with User Entered Specifications", module_model = 2):
   - General information: module name, cell type, cells in series.
   - Electrical specifications: Voc, Isc, Vmp, Imp, temperature coefficients of Voc (%/C or V/C),
     Isc (%/C or A/C) and Pmp (%/C), NOCT. The equivalent value in the other unit is shown live.
   - Bifacial specifications: "Module is bifacial" checkbox (then the usual bifaciality, gain and
     ground clearance inputs).
   - Mounting configuration: ground or rack mounted, one story (PPE default, same as CEC modules).
   - Nominal ratings at STC: Pmp, area (length x width) and efficiency shown live.
   - Save module (.json) / Load module (.json) to reuse or share a custom module.
   - Checks: Vmp < Voc, Imp < Isc, coefficient signs and ranges (catches unit mistakes), NOCT 30-70 C,
     and SAM's own 6-parameter fit is run before any weather is downloaded. If SAM cannot fit the
     datasheet values, the electrical section is highlighted with SAM's message.
   - Self-shading for bifacial custom modules: Standard, or Thin film for CdTe/CIS/CIGS/Amorphous.
   - Inputs export: 6par_* rows become User input / PPE calculated (Used in run = Yes); CEC-database
     cec_* rows are marked not used.
4. "Copy specs from currently selected module?" button appears in Custom module when a CEC module is
   selected. Copies name (+ " (from CEC database)", SAM's convention), cell type, cells in series,
   Voc, Isc, Vmp, Imp, coefficients (in the library's V/C and A/C units), Pmp coefficient, NOCT,
   bifacial flag and length/width.

Verified: a custom module with the same specs as the CEC test module gives Isc / Voc / Vmp max within
0.1 % of the CEC-database run (SAM fits the model from datasheet values). CEC-database results are
unchanged from v0.1.7 (automated tests are locked to those values).

## v0.1.6 — 2026-10-23

- SAM inputs browser export (testing only) now labels every value with one of six sources:

  | Source | Meaning |
  |---|---|
  | User input | typed or selected in the app (e.g. module length in mm) |
  | PPE default | fixed PPE rule, always the same (e.g. weather-file albedo ON, soiling 0) |
  | PPE calculated | calculated by the app from user inputs, no lookup (e.g. aspect ratio, GCR) |
  | SAM calculated | from the CEC module or inverter database (e.g. Isc, Voc, inverter coefficients) |
  | SAM default | not set by PPE; SAM's standard value left as-is (e.g. grid_curtailment) |
  | Error | not accounted for by the app |

- New columns: "Used in run" (Yes / No) and "Note" (where the value came from, or why it is unused).
  Example: 6par_* rows are SAM default + Used in run = No, because they belong to the
  "CEC User Entered Specifications" module model, which this run does not use.
- New section at the bottom of the export: the CEC module and inverter database values the run
  actually uses (cec_i_sc_ref, cec_v_oc_ref, inv_snl_paco, C0-C3, ...). SAM's Inputs Browser does not
  list these, so they were missing from v0.1.5.
- The export now records whether an optional input was typed or filled by a PPE default
  (e.g. ground clearance, azimuth, rotation limit, module length/width).
- The legend for the six sources is shown above the export button.

Unchanged: all calculations and results (verified identical to v0.1.5 in the automated tests).

## v0.1.5 — 2026-10-23

Changes from Patrick's feedback:

1. Racking: "Fixed-tilt ground" and "Rooftop" combined into "Fixed-tilt" (2nd position).
   Section 4 notes rewritten for Tracker / Fixed-tilt / Carport.
2. "Modules stacked along side of row" renamed "Modules High".
3. New Subarray size inputs for every racking type: Modules High and Modules Across of full
   subarray (both required, whole numbers). Sent to SAM as nmody / nmodx.
   - Modules High tooltip changes with racking type (tracker/fixed-tilt vs carport text).
   - Modules Across tooltip shows the small Modules Across / Modules High diagram.
   - Collapsible "Subarray layout illustration": black-and-white outline of every module,
     using orientation and module dimensions. Trackers are drawn vertically on the page.
   - SAM requires the modeled modules to fill at least one full subarray (otherwise
     "Number of rows calculated ... was zero"). The app now models
     ceil(Modules High x Modules Across / modules per string) identical strings, each on its
     own identical inverter, so per-string Isc/Voc/Vmp are unchanged. The calculated string
     and row count are shown live and in "Inputs used".
4. Print button (inputs + results; collapsible sections are expanded on paper).
5. CSV downloads after a run: Isc, Voc, Vmp (rows = time steps, one column per year),
   or all files in one .zip.
6. TESTING ONLY: "SAM inputs browser (.csv)" - every variable from the PPE sample Inputs
   Browser export, one column per year (each year = one SAM run), plus a Source column:
   PPE setting / PySAM default / App (UI-only) / Error (value not available).

Unchanged calculations: 3-hour averaging, NEC 70% floor, temperature model, losses.

## v0.1.4 — 2026-10-23

Changes from Patrick's feedback:

1. Bifacial override: if the CEC library lists a module as Bifacial = 0, a checkbox
   "Module is bifacial (override library)" appears. Checking it enables the bifacial
   inputs and models the module as bifacial. Results show "user override" as the source.
2. Module length and width are entered in mm (datasheet units). Library values are shown
   in mm. Converted to metres internally for SAM.
3. Tooltip (?) added to "Ground clearance height" with the SAM definition.
4. Row spacing can be entered as Row pitch (m) OR GCR directly (toggle). Pitch mode shows
   the calculated GCR live; GCR mode shows the equivalent row pitch. Carport stays 0.01.
5. "Reset inputs" button (clears all inputs and results) and "Clear weather cache" button
   (deletes all downloaded NSRDB files after a confirmation that shows the cache size;
   blocked while a simulation is running).
6. Pressing Run with missing or invalid inputs highlights EVERY problem field in red, with
   a message under each field and a list above the Run button. Highlights clear as you edit.
7. System maximum voltage no longer has a default ("Select..." must be changed).
8. Styling: unselected buttons have a light blue-gray fill with a hover color change;
   inputs are light blue-gray with a stronger border; more space between sections.
9. Racking and layout: Rotation limit and Azimuth swapped (Rotation limit first).
10. run_from_source.bat now sets up its own Python environment on first use, so a new
    version folder works without running build_exe.bat first. New run_tests.bat.

Unchanged calculations: 3-hour averaging, NEC 70% floor, SAM settings, temperature model.

## v0.1.3 — 2026-10-23

- Build script now always uses the project's own Python environment (.venv) by full path.
  It never falls back to the system default Python (which was 3.15 and has no PySAM).
- Build script finds Python 3.14 (or 3.13 / 3.12) automatically and recreates .venv if it was
  made with an unsupported Python version.
- Build script prints which Python it is using and pauses at the end (success or failure).
- Tests always use their own small test libraries; a separate check verifies the real CEC files.
- Complete code base included (no partial patches).
