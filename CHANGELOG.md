# Changelog — PPE SAM Multi-Year Simulation

Every version, newest first. Entries up to v0.2.8 are the release notes written with each version
(VERSION.txt at the time), reformatted only.

Release notes for v0.1.0–v0.1.2 and v0.1.7 were not kept.

## v0.3.3 — 2026-10-29

- **Settings need no visit.** Every setting starts at the PPE standard:
  - Calculate bifacial electrical mismatch: unchecked (as before).
  - Self-shading: now filled in automatically with the PPE standard for the selected module
    (bifacial -> Standard, Thin film for thin-film cells; monofacial -> None) and follows the module
    when it changes. Marked Default. Choosing another option keeps that choice (marked User entered,
    with the warning as before); choosing "Select..." returns to the PPE standard.
    Previously (v0.2.8 - v0.3.2) it had to be selected for every run.
  - Number of rows: 1 (as before).
- Inputs used and the SAM inputs browser export mark settings left at the PPE standard as
  Default / PPE default, and changed settings as User entered / User input.
- A run (or the API) without a self-shading value uses the PPE standard for the module.

Calculations unchanged (tests locked to the v0.1.6 values).

## v0.3.2 — 2026-10-29

- **SAM case inputs (.json)** download on the Results page (also in All files .zip): every SAM input of
  the run for the worst-case Isc year, in SAM's own "Generate code > JSON for inputs" format, pointing
  at that year's cached weather file.
  - Checked against a file exported from SAM 2026.7.3: the same 386 entries with the same value types.
  - Loading the file into a fresh SAM model (the PySAM way) gives results identical to the app's run.
- Checked with the same SAM 2026.7.3 file: the 279 SAM inputs the app leaves at their defaults match
  SAM 2026.7.3 (4 differences: rounding, unused inverter models, and the inverter's displayed CEC
  efficiency, which was confirmed to have no effect on Isc, Voc or Vmp). Every setting the app makes
  reaches SAM (none silently skipped).
- New automated test (tests/test_sam_json.py, run by run_tests.bat).

Calculations unchanged (tests locked to the v0.1.6 values).

## v0.3.1 — 2026-10-29

- **Settings page** (new tab next to Configure; the summary panel and Run simulation stay beside it):
  1. Calculate bifacial electrical mismatch (moved from Module). Always shown; greyed out with a note
     for monofacial modules. Warning when checked, as before.
  2. Self-shading (moved from System design > Subarray). Still required with no pre-selected value;
     the PPE standard for the module and the warning are shown under it, as before.
  3. Number of rows (was "Rows modeled", moved from System design > Subarray). Defaults to 1 (the PPE
     standard), marked Default; the warning for more than 1 row is unchanged.
  - Readiness has a "Settings" item; error links and readiness links open the Settings page.
  - Review screen and Inputs used list the three settings in their own "Settings" group, in the same
    order. Printing from Configure or Settings prints both pages.
- **About is a page** (tab) instead of a pop-up. Adds "Developed using" (NLR-PySAM 8.0.0
  documentation, NatLabRockies/SAM on GitHub) and "For general information on SAM, inputs, outputs,
  etc." (SAM Help). Links open in a new browser tab.
- **System design:** Row spacing (row pitch / GCR) now sits above the Layout illustration.
- **Save / load inputs (.json):** "Save inputs (.json)" and "Load inputs (.json)" in the summary panel.
  The file holds every Configure and Settings input; loading it (after a confirmation) replaces all
  inputs, reselects the module and inverter from the CEC library, and flags anything it could not
  restore (e.g. a module no longer in the library). Results > Downloads has "Inputs (.json)" (the
  exact inputs of that run, also in All files .zip), which loads the same way.
- Fix: a Readiness link clicked right after typing in a field now works (it was redrawn mid-click).

Calculations unchanged (tests locked to the v0.1.6 values).

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

## v0.2.7 — 2026-10-27

**Results > Inputs used**
- CEC library module: the 17 database specs (Technology ... Single-diode parameter Adjust) sit in a
  collapsible "CEC database module specs (17 items)" sub-section directly under "Module model",
  collapsed by default and never highlighted. They print expanded.
- "Module model" has a tooltip: "Module specs shown below are pulled directly from the CEC database..."
- Custom module: unchanged (no sub-section, specs highlighted as before).

**Configure > Module**
- Same tooltip on the "CEC library" button (clicking the "?" does not select the button).

**Configure > Site and weather**
- "Retrieve weather" button next to "Verify location on map", shown once the latitude and longitude
  are valid. Click it to download the weather in the background and keep filling out the page.
  The button shows a loading icon, then "✓ Complete". The Results tab unlocks and shows the
  Weather retrieval stage in progress, then done (Simulation: "Waiting for Run simulation").
  Changing the location or time step resets the button for the new site.
- Run simulation reads the cached files. If the background retrieval for the same site is still
  running, the run waits for it (showing its progress) instead of downloading the same years twice.

**Sidebar**
- "Clear weather cache" button removed. (Cache folder: %LOCALAPPDATA%\PPE_SAM_MultiYear\weather)

**About**
- Rewritten: Version, Date updated, Engine, Modules, Inverters, Library, Weather, Address lookup,
  and a two-line Method.

Calculations unchanged (tests locked to the v0.1.6 values).

## v0.2.6 — 2026-10-27

- Pure Power Engineering logo added to the center of the header (ppe_sam\static\logo.png,
  trimmed and resized from "PPE Logo 2023 (High Res PNG) (Transparent).png"). Also prints.

Everything else is unchanged from v0.2.5 (mismatch warning, key-item highlights in Inputs used,
collapsed sections with auto-expand). Calculations unchanged (tests locked to the v0.1.6 values).

## v0.2.5 — 2026-10-27

*Original release notes not kept. Summary from the v0.2.6 notes:*

- Warning when "Calculate bifacial electrical mismatch" is checked.
- Key items highlighted in Inputs used.
- Sections start collapsed and expand automatically as the previous section is completed.

## v0.2.4 — 2026-10-27

**Site and weather**
- "Address" / "Coordinates" buttons after Project name (same size as CEC library / Custom module).
  Fields underneath: Address | Latitude | Longitude | Weather time step.
- Address: type the address, then click Run (white button at the end of the field) or press Enter.
  Latitude / Longitude are filled in, read-only and marked Calculated. Editing the address clears
  them until Run is clicked again. Lookup: US Census Geocoder (US street addresses), then
  OpenStreetMap Nominatim (any place); internet required.
- Coordinates: Latitude / Longitude are entered; Address is read-only, marked Default, not used.
- Verify location on map and the weather download always use the latitude / longitude.
- Inputs used lists the location input, address, matched address and geocoder.

**Module**
- Checkboxes now print (checked state shown).

**System design**
- Rows modeled is an input (required; PPE standard 1). Strings are added (all on one inverter)
  until SAM builds that many rows. Warning when more than 1 row: "Warning: PPE Standard is 1 row.
  More than one row will cause self-shading, resulting in a lower & more aggressive Isc value."
  If SAM cannot build exactly that many rows (a string longer than one subarray), the field says
  the nearest possible value.
- Layout illustration draws every row (up to 12) at the row pitch.
- Module spacing is entered in inches.
- Row pitch and ground clearance default to inches (m still selectable).

**All**
- Tab no longer stops on the "?" tooltips (still open on hover or click).

Unchanged: all calculations for 1 row (tests locked to the v0.1.6 values).

## v0.2.3 — 2026-10-27

1. Number of inverters = 1. All modeled strings sit on a single inverter (was one inverter per string).
   Verified: Isc / Voc / Vmp are identical, including with inverter clipping (SAM applies clipping on
   the AC side and keeps each string at its DC operating point).
2. Row pitch and ground clearance: units selector (m / in). Inches are converted to metres
   (x 0.0254) for SAM; the metre value is shown under the field. Inputs used lists the entered value
   in its units plus a "(converted)" metre row (Calculated).
3. Layout illustration is a plan view (north up) rotated by the azimuth, with a north arrow, a blue
   arrow for the direction the modules face (fixed-tilt / carport) or the axis direction (tracker),
   and the azimuth value. The drawing area resizes to fit the rotated array; labels stay readable.
4. Albedo: SAM uses the weather-file albedo where it is present and valid. Where the column is
   missing or a value is invalid (e.g. 0), SAM falls back to its monthly albedo, 0.2 every month
   (verified). Now stated in the Weather source dropdown, the modeling assumptions and Inputs used.
5. "Calculate bifacial electrical mismatch" checkbox under the "bifacial" checkbox (CEC override or
   custom "Module is bifacial"). Shown for every bifacial module; hidden for monofacial modules
   unless "bifacial" is checked. Unchecked = off (worst case, no loss).

Unchanged: all other calculations (tests locked to the v0.1.6 values).

## v0.2.2 — 2026-10-26

**All**
- Section tags read "Incomplete" / "Complete".
- Calculated and Default values use the same field layout as user inputs (label, box, unit), with a
  darker gray, read-only box and a green (Calculated) or amber (Default) left edge.
- Horizontal dividers between subsections removed (headings and spacing kept).
- Imp 3-hour average removed everywhere (calculation, KPI, tables, downloads).

**Module**
- CEC module card and search results show Power / Isc / Voc / Imp / Vmp only.
- New "Modeling assumptions" dropdown (module model, temperature model, self-shading, losses, bifacial).
- "Copy model name" removed.

**Inverter** (renamed from "Inverter and string")
- Only the inverter selection. "Copy model name" removed.

**System design** (renamed from "Racking and layout")
- New "Circuit" subsection (modules per string, system max voltage) after the mounting type.
- Carport button no longer shows "GCR 0.01". Carport GCR shows as a read-only Default field.
- Inverter / string assumptions moved to a "Modeling assumptions" dropdown here.
- Strings modeled and Rows modeled are separate read-only Calculated fields.

**Run simulation**
- Review shows only the configuration, grouped Site and weather / Module / Inverter / System design.

**Results**
- Three KPI cards: Isc (with "70% of Isc = x A" and a check / X mark vs the simulated value),
  Voc, Vmp (with operating minimum). Year/window text removed.
- Dropdowns: NEC 70% minimum, Inputs used, Downloads, Log.
- Inputs used: one table of every input, ordered like the configuration page:
  Input | Value | Units | Method (Database, User entered, Calculated, Default). It includes the
  modeling assumptions, replacing the separate assumptions table and file. Downloadable (.csv),
  also in All files (.zip).
- Per-year and single time-step tables removed.
- Run status is replaced by the Log once the run finishes.

Unchanged: Isc / Voc / Vmp calculations (tests locked to the v0.1.6 values).

## v0.2.1 — 2026-10-26

1. Source labels: badges under fields removed. Each field shows its source as a coloured left
   edge (Database blue, User entered gray, Calculated green, Default amber) with the full label on
   hover. Legend at the top of the page. "Overridden" and the reset links are removed: an edited
   database value simply becomes User entered.
2. No pre-filled values for user inputs. Rotation limit, azimuth (tracker), module orientation,
   ground clearance (bifacial) and module spacing must be entered; fields show "e.g." placeholders
   only. The app no longer fills hidden defaults for these. Weather time step stays 60-minute.
   CEC library values (module dimensions, copied custom specs) are still filled and marked Database.
3. Text trimmed: racking notes removed (guidance lives in the tooltips: rotation limit "use 60°
   if unknown", ground clearance typical values), shorter labels, messages and descriptions.
4. Field grid: fixed 4-column grid (2 / 1 columns on narrow screens), every unit in a fixed-width
   unit column, larger spacing between subgroups (General, Electrical, Dimensions, Bifacial,
   String, Orientation, Subarray, Row spacing) than between fields.
5. Results tab: the run opens the Results view. It starts with four KPI cards (Isc, Voc, Vmp with
   min, Imp), then collapsible NEC 70% check (open), Modeling assumptions, Per-year, Single
   time step, Inputs used, Downloads and Run status.
   NEW OUTPUT - Imp: SAM has no string Imp output, so Imp = SAM subarray DC power / (strings x Vmp)
   per time step, then the same max 3-hour average. Added to the per-year table, single-step table,
   downloads (Imp .csv) and the modeling assumptions.
6. Analysis stage has its own progress bar (green when done).

Unchanged: Isc / Voc / Vmp calculations (tests locked to the v0.1.6 values).

## v0.2.0 — 2026-10-26

GUI rework per PPE_SAM_GUI_Review.md. No calculation changes (automated tests are locked to the
v0.1.6 / v0.1.9 results).

1. Page structure: main configuration column + 330 px sticky summary panel (project, site,
   module, inverter, string, mounting, readiness, Run simulation). Single column below 1080 px.
   Card gaps 16 px. Each section can be collapsed and then shows a one-line summary
   (e.g. "Module: <model> · 530 W · Database") and a Complete / "n remaining" chip.
2. Input states: editable fields are white with a clear border; calculated values (aspect ratio,
   bifaciality used, GCR, strings modeled, Pmp / area / efficiency) are read-only blocks labelled
   "Calculated" that say what is needed until they can be calculated; invalid fields get a red
   border, "!" icon and specific text; strong keyboard focus outline.
3. Source labels next to values: Database, User entered, Default, Calculated, Overridden.
   Overridden values offer "Reset to <source> value (x)". A selected module with no library
   dimensions says "Not available from selected source. Enter datasheet dimensions."
   A Default (e.g. ground clearance) follows the mounting type unless the user changed it.
4. Equipment pickers: after selection a card shows manufacturer, full model name (selectable)
   and key specs, with Change, Clear and Copy model name. Search shows Searching / No matches /
   Search failed states; search text is separate from the confirmed selection (Change keeps the
   current selection until another is picked). Arrow keys move through the result list.
5. Modeling assumptions: always-visible statement in section 3 plus a "Modeling assumptions"
   table (selected equipment value vs simulation value and why). The same table is shown before
   every run and with the results, and exported as "<project>_modeling_assumptions.csv"
   (also included in All files .zip).
6. Selection states: module source, mounting type and row-spacing mode use one radio-card
   pattern with a checkmark and border (arrow keys supported). "Choose a mounting type." until
   one is chosen; mounting fields appear only after a choice.
7. Validation: "All fields are required unless marked optional." Units beside every numeric
   field. Placeholders lighter than values. Fields are checked when you leave them and again
   before running; messages say what to enter (e.g. "Modules per string: enter a whole number.").
   The error list at the top links to each field.
8. Site and weather: "Verify location on map" (Bing Maps, new tab) and formatted coordinates.
   "Weather source and assumptions" shows the years requested (1998-last year), albedo policy,
   time basis, minimum years and caching. After a run, the NSRDB grid point used and the years
   actually used / not available are shown.
9. Run: Run simulation in the sticky panel -> validation -> "Review before running"
   (configuration + equipment vs simulation values) -> run. Run status shows three stages
   (weather retrieval, simulation, analysis) with years checked / downloaded / cached /
   not available / failed, years simulated, and cancel. On failure the failed stage is marked,
   inputs are unchanged and cached weather years are kept.
10. Visual hierarchy: blue reserved for primary actions, selection and focus; neutral section
    badges and tooltips; shorter subtitle; library counts, version, weather dataset and the
    methodology moved to "About".

## v0.1.9 — 2026-10-26

Approved fixes 1 and 3 only:

1. Pmp temperature coefficient now copies from the CEC library.
   - The library column is "gamma_pmp" (confirmed); the app was reading the old name "gamma_r".
     It now reads gamma_pmp, with gamma_r as a fallback for older library files.
   - If a library module has no Pmp coefficient, "Copy specs" shows a warning and highlights the
     field instead of leaving it silently blank.
   - run_tests.bat now fails if the Pmp coefficient column is missing or most modules have no value,
     and prints the column it found and how many modules have a value.
3. Custom modules: the six single-diode parameters SAM calculates from the datasheet values
   (a, I_L, I_o, R_s, R_sh, Adjust) are listed at the bottom of the SAM inputs browser export
   (Source = SAM calculated), labelled with the matching CEC Modules.csv column
   (a_ref, I_L_ref, I_o_ref, R_s, R_sh_ref, Adjust) for direct comparison.

Wording: the custom-module error now says SAM "could not calculate the module model" (was "fit").

Not changed (per review): no automatic switch to the library parameters for copied modules,
no change to the unused-model rows, no new comparison tests.
Unchanged: all calculations and results (automated tests locked to v0.1.6 / v0.1.8 values).

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
