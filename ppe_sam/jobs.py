"""Background jobs.

Job         : weather retrieval -> multi-year simulation -> 3-hr analysis (progress per stage).
WeatherJob  : weather retrieval only, started early from the Configure page ("Retrieve weather").
              It fills the local cache; a later Job for the same site reads the cached files.
              If a Job starts while a WeatherJob for the same site is still running, the Job waits
              for it (showing its progress) instead of downloading the same files twice.
"""
import concurrent.futures as cf
from concurrent.futures.process import BrokenProcessPool
import io
import os
import threading
import time
import traceback
import uuid
import zipfile

from . import analysis, config, exports, inputs_export, model, report, weather

JOBS = {}          # id -> Job | WeatherJob
PREFETCH = {}      # weather.site_key -> latest WeatherJob for that site
ACTIVE = ("queued", "downloading", "confirm", "simulating", "analyzing")
MAX_KEPT_JOBS = 5


def any_active():
    return any(j.status in ACTIVE for j in JOBS.values())


def _prune():
    for kind in ("run", "weather"):
        done = [j for j in JOBS.values() if j.kind == kind and j.status not in ACTIVE]
        for j in sorted(done, key=lambda j: j.started)[:-MAX_KEPT_JOBS]:
            JOBS.pop(j.id, None)


def _new_weather():
    years = weather.requested_years()
    return {"requested": len(years), "first": years[0], "last": years[-1], "processed": 0,
            "cached": 0, "downloaded": 0, "unavailable": 0, "failed": 0,
            "current": None, "failed_years": [], "unavailable_years": []}


class _Base:
    kind = "run"

    def __init__(self):
        self.id = uuid.uuid4().hex[:12]
        self.status = "queued"
        self.message = ""
        self.log_lines = []
        self.result = None
        self.error = None
        self.failed_stage = None
        self.weather = _new_weather()
        self.sim = {"total": 0, "done": 0, "failed_years": []}
        self.ana = {"total": 0, "done": 0}
        self._cancel = False
        self.started = time.time()

    def log(self, msg):
        self.log_lines.append(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def cancelled(self):
        return self._cancel

    def _on_year(self, year, status):
        w = self.weather
        w["processed"] += 1
        w[status] += 1
        w["current"] = year
        if status == "failed":
            w["failed_years"].append(year)
        if status == "unavailable":
            w["unavailable_years"].append(year)

    def snapshot(self):
        return {"id": self.id, "kind": self.kind, "status": self.status, "message": self.message,
                "log": self.log_lines[-400:], "weather": self.weather, "sim": self.sim, "analysis": self.ana,
                "failed_stage": self.failed_stage, "result": self.result, "error": self.error}


class WeatherJob(_Base):
    kind = "weather"

    def __init__(self, lat, lon, interval):
        super().__init__()
        self.lat, self.lon, self.interval = lat, lon, interval
        self.key = weather.site_key(lat, lon, interval)

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            self.status, self.message = "downloading", "Retrieving weather"
            self.log(f"Weather retrieval started from the Configure page: site {self.lat}, {self.lon}; "
                     f"{self.interval}-minute data; years {self.weather['first']}-{self.weather['last']}")
            files, failed = weather.download_all(self.lat, self.lon, self.interval, self.log, self.cancelled,
                                                 on_year=self._on_year)
            if not files:
                raise RuntimeError("No weather files could be retrieved for this location.")
            if failed:
                raise RuntimeError(f"{len(failed)} year(s) failed to download (connection problem): "
                                   f"{', '.join(map(str, failed))}. Retry: the {len(files)} year(s) "
                                   "already retrieved are cached.")
            self.result = {"years": len(files)}
            self.status, self.message = "done", f"Weather retrieved ({len(files)} years). Run simulation when ready."
            self.log(f"Weather retrieval complete: {len(files)} years cached.")
        except InterruptedError:
            self.status, self.message = "cancelled", "Weather retrieval cancelled."
        except Exception as e:  # noqa: BLE001
            self.failed_stage = "weather"
            self.status, self.error, self.message = "error", f"{e}", "Weather retrieval failed"
            self.log(traceback.format_exc())
        finally:
            _prune()


def start_weather(lat, lon, interval):
    """Start (or reuse) a weather retrieval for this site. Reuses a running or completed one."""
    key = weather.site_key(lat, lon, interval)
    cur = PREFETCH.get(key)
    if cur and cur.status in ("queued", "downloading", "done") and cur.id in JOBS:
        return cur
    job = WeatherJob(lat, lon, interval)
    JOBS[job.id] = job
    PREFETCH[key] = job
    threading.Thread(target=job.run, daemon=True).start()
    return job


class Job(_Base):
    kind = "run"

    def __init__(self, raw_design):
        super().__init__()
        self.raw = raw_design
        self._confirm = threading.Event()
        self._proceed = False
        self.design = self.inputs = self.files = self.per_year = self.stamps = None

    def answer(self, proceed: bool):
        self._proceed = proceed
        self._confirm.set()

    def cancel(self):
        self._cancel = True
        self._confirm.set()

    def _base(self):
        yrs = sorted(self.per_year)
        return f"{exports.safe_name(self.design['project'])}_{yrs[0]}-{yrs[-1]}"

    def export(self, kind):
        if self.status != "done" or not self.per_year:
            raise LookupError("Results are not available for this run.")
        base = self._base()
        if kind in exports.KINDS:
            return (f"{base}_{exports.KINDS[kind][0]}.csv",
                    exports.series_csv(kind, self.per_year, self.stamps), "text/csv")
        if kind == "inputs_used":
            return f"{base}_inputs_used.csv", exports.inputs_used_csv(self.result["inputs_used"]), "text/csv"
        if kind == "inputs":
            h, rows = inputs_export.build_rows(self.design, self.inputs, self.files)
            return f"{base}_SAM_inputs.csv", inputs_export.to_csv(h, rows), "text/csv"
        if kind == "all":
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for k in list(exports.KINDS) + ["inputs_used", "inputs"]:
                    name, data, _ = self.export(k)
                    z.writestr(name, data)
            return f"{base}_exports.zip", buf.getvalue(), "application/zip"
        raise LookupError(f"Unknown export '{kind}'.")

    def _wait_for_prefetch(self, lat, lon, interval):
        """If a weather retrieval for this site is already running, wait for it and mirror its progress."""
        pre = PREFETCH.get(weather.site_key(lat, lon, interval))
        if not pre or pre.status not in ("queued", "downloading"):
            return
        self.log("Weather retrieval for this site is already in progress (started from the Configure page); "
                 "waiting for it to finish.")
        while pre.status in ("queued", "downloading"):
            if self._cancel:
                raise InterruptedError("Cancelled")
            w = pre.weather
            self.weather = {k: (list(v) if isinstance(v, list) else v) for k, v in w.items()}
            time.sleep(0.5)
        self.log(f"Earlier weather retrieval finished ({pre.status}); reading the cached files.")
        self.weather = _new_weather()

    def run(self):
        stage = "validation"
        try:
            design = model.validate_design(self.raw)
            inputs = model.build_inputs(design)
            lat, lon, interval = design["lat"], design["lon"], design["interval"]

            stage = "weather"
            self.status, self.message = "downloading", "Retrieving weather"
            self.log(f"Site {lat}, {lon}; {interval}-minute data; years {self.weather['first']}-{self.weather['last']}")
            self._wait_for_prefetch(lat, lon, interval)
            files, failed = weather.download_all(lat, lon, interval, self.log, self.cancelled, on_year=self._on_year)
            if not files:
                raise RuntimeError("No weather files could be retrieved for this location.")
            if failed:
                raise RuntimeError(f"{len(failed)} year(s) failed to download (connection problem): "
                                   f"{', '.join(map(str, failed))}. Run again: the {len(files)} year(s) "
                                   "already retrieved are cached.")
            n_files = len(files)
            if n_files < config.RECOMMENDED_MIN_YEARS:
                self.status = "confirm"
                self.message = (f"Only {n_files} weather years are available (fewer than the recommended "
                                f"{config.RECOMMENDED_MIN_YEARS}). Continue?")
                self._confirm.wait()
                if self._cancel or not self._proceed:
                    self.status, self.message = "cancelled", "Cancelled by user."
                    return

            stage = "simulation"
            self.status, self.message = "simulating", f"Running SAM for {n_files} years"
            self.sim["total"] = n_files
            per_year, stamps = {}, {}
            tasks = [(y, str(p), inputs) for y, p in files]
            workers = max(1, min(len(tasks), (os.cpu_count() or 2) - 1))

            def _done(y, out):
                per_year[y] = out
                self.sim["done"] += 1
                self.log(f"{y}: simulated")

            try:
                with cf.ProcessPoolExecutor(max_workers=workers) as ex:
                    futs = {ex.submit(model.run_year, t): t[0] for t in tasks}
                    for f in cf.as_completed(futs):
                        if self._cancel:
                            ex.shutdown(cancel_futures=True)
                            raise InterruptedError("Cancelled")
                        try:
                            y, out = f.result()
                        except (BrokenProcessPool, OSError):
                            raise
                        except Exception as e:  # noqa: BLE001
                            self.sim["failed_years"].append(futs[f])
                            raise RuntimeError(f"SAM failed for {futs[f]}: {e}") from e
                        _done(y, out)
            except (BrokenProcessPool, OSError) as e:
                self.log(f"Parallel run unavailable ({e}); running sequentially.")
                for t in tasks:
                    if t[0] in per_year:
                        continue
                    if self._cancel:
                        raise InterruptedError("Cancelled")
                    _done(*model.run_year(t))

            stage = "analysis"
            self.status, self.message = "analyzing", "Calculating 3-hour averages"
            self.ana["total"] = n_files + 1
            expected = weather.expected_rows(interval)
            for y, p in files:
                stamps[y] = weather.read_timestamps(p)
                for var, series in per_year[y].items():
                    if len(series) != expected:
                        raise RuntimeError(f"{y}: SAM returned {len(series)} {var} values, expected {expected}.")
                self.ana["done"] += 1
            summary = analysis.summarize(per_year, stamps, interval)
            self.ana["done"] += 1
            self.log("3-hour averages calculated.")

            mod = design["module"]
            floor = analysis.nec_floor(mod["i_sc_ref"], design["bifacial"], design["bifacial_gain"])
            isc = summary["worst"]["isc_max"]["value"]
            site = weather.nsrdb_site_info(files[0][1])
            self.design, self.inputs, self.files = design, inputs, files
            self.per_year, self.stamps = per_year, stamps
            years_run = [y for y, _ in files]
            wx = {"years": years_run, "count": n_files, "first": years_run[0], "last": years_run[-1],
                  "unavailable_years": self.weather["unavailable_years"], "dataset": config.NSRDB_DATASET,
                  "nsrdb_lat": site.get("Latitude"), "nsrdb_lon": site.get("Longitude"),
                  "location_id": site.get("Location ID"), "interval": interval}
            self.result = {
                "summary": summary,
                "nec": {"isc_stc_module": mod["i_sc_ref"],
                        "bifacial_gain_pct": design["bifacial_gain"] if design["bifacial"] else None,
                        "floor_70pct": floor, "simulated_3hr": isc,
                        "governing": max(isc, floor), "floor_governs": isc < floor},
                "project": design["project"],
                "inputs_used": report.build(design, wx),
                "cec_tip": report.CEC_SPECS_TIP,
                "weather": wx,
                "elapsed_s": round(time.time() - self.started, 1),
            }
            self.status, self.message = "done", "Complete"
            self.log(f"Done in {self.result['elapsed_s']} s.")
        except InterruptedError:
            self.status, self.message = "cancelled", "Cancelled. Weather years already retrieved are cached."
        except model.DesignError as e:
            self.failed_stage = stage
            self.status, self.error, self.message = "error", str(e), str(e)
        except Exception as e:  # noqa: BLE001
            self.failed_stage = stage
            self.status, self.error, self.message = "error", f"{e}", "Run failed"
            self.log(traceback.format_exc())
        finally:
            _prune()


RACK_TEXT = {"tracker": "Single-axis tracker", "fixed": "Fixed-tilt", "carport": "Carport"}


def _r(v, n=4):
    return None if v is None else round(v, n)


def _len_txt(metres, entered, units):
    return f"{entered:g} in ({metres:.3f} m)" if units == "in" else f"{metres:g} m"


def review(raw):
    """Validate and summarize the configuration for the pre-run review, grouped like the config page."""
    d = model.validate_design(raw)
    m, inv = d["module"], d["inverter"]
    years = weather.requested_years()
    rk = d["racking"]
    mount = [RACK_TEXT[rk]]
    mount.append(f"rotation limit {d['rotlim']:g}°" if rk == "tracker" else f"tilt {d['tilt']:g}°")
    mount.append(f"azimuth {d['azimuth']:g}°")
    mount.append(d["orientation"])
    if d["bifacial"]:
        mount.append("ground clearance " + _len_txt(d["ground_clearance"], d["ground_clearance_entered"],
                                                    d["ground_clearance_units"]))
    if d["gcr_mode"] == "carport":
        spacing = "GCR 0.01 (carport)"
    elif d["gcr_mode"] == "gcr":
        spacing = f"GCR {d['gcr']:g}"
    else:
        spacing = f"row pitch {_len_txt(d['pitch'], d['pitch_entered'], d['pitch_units'])}, GCR {_r(d['gcr'], 3)}"
    bif = "No"
    if d["bifacial"]:
        bif = (f"Yes · bifaciality {d['bifaciality']:g} · gain {d['bifacial_gain']:g} % · "
               f"electrical mismatch {'on ⚠ PPE standard is off' if d['bifacial_mismatch'] else 'off'}")
    site = f"{d['lat']}, {d['lon']}"
    if d["location_mode"] == "address":
        site = f"{d['address']} → {site}"
    if d["project"]:
        site += f" · {d['project']}"
    rows_txt = f"{d['rows']} row(s)" + ("" if d["rows"] == config.PPE_STANDARD_ROWS else " ⚠ PPE standard is 1 row")
    sel, ppe = (config.SELF_SHADING[d["self_shading"]][1], config.SELF_SHADING[d["self_shading_ppe"]][1])
    shade_txt = f"self-shading {sel}" + ("" if sel == ppe else f" ⚠ PPE standard is {ppe}")
    groups = [
        ["Site and weather", [
            ["Site", site],
            ["Weather", f"{config.NSRDB_DATASET}, {years[0]}-{years[-1]}, {d['interval']}-minute"]]],
        ["Module", [
            ["Module", f"{m['name']} ({'custom' if d['module_source'] == 'custom' else 'CEC library'})"],
            ["Dimensions", f"{d['module_length_mm']:g} × {d['module_width_mm']:g} mm"],
            ["Bifacial", bif]]],
        ["Inverter", [["Inverter", inv["name"]]]],
        ["System design", [
            ["Circuit", f"{d['modules_per_string']} modules per string · {d['system_voltage']} V max"],
            ["Mounting", " · ".join(mount)],
            ["Subarray", f"{d['modules_high']} high × {d['modules_across']} across · {spacing}"],
            ["Modeled", f"{rows_txt} · {d['nstrings']} string(s) on 1 inverter · {shade_txt}"]]],
    ]
    return {"groups": groups}


def start(raw_design):
    job = Job(raw_design)
    JOBS[job.id] = job
    threading.Thread(target=job.run, daemon=True).start()
    return job
