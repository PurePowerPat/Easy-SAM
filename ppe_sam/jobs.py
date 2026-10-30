"""Background jobs.

Job         : weather retrieval -> multi-year simulation -> analysis (3-hr averages, max Voc; progress per stage).
WeatherJob  : weather retrieval only, started early from the Configure page ("Retrieve weather").
              It fills the local cache; a later Job for the same site reads the cached files.
              If a Job starts while a WeatherJob for the same site is still running, the Job waits
              for it (showing its progress) instead of downloading the same files twice.
"""
import concurrent.futures as cf
import io
import json
import multiprocessing
import os
import threading
import time
import traceback
import uuid
import zipfile
from concurrent.futures.process import BrokenProcessPool

from . import analysis, config, exports, inputs_export, model, report, weather

JOBS = {}          # id -> Job | WeatherJob
PREFETCH = {}      # weather.site_key -> latest WeatherJob for that site
_jobs_lock = threading.Lock()   # JOBS / PREFETCH are used by request threads and job threads
ACTIVE = ("queued", "downloading", "confirm", "simulating", "analyzing")
DOWNLOADING = ("queued", "downloading")
MAX_KEPT_JOBS = 5


def get(job_id):
    with _jobs_lock:
        return JOBS.get(job_id)


def any_active():
    with _jobs_lock:
        return any(j.status in ACTIVE for j in JOBS.values())


def _prune():
    with _jobs_lock:
        for kind in ("run", "weather"):
            done = [j for j in JOBS.values() if j.kind == kind and j.status not in ACTIVE]
            for j in sorted(done, key=lambda j: j.started)[:-MAX_KEPT_JOBS]:
                del JOBS[j.id]
                if PREFETCH.get(getattr(j, "key", None)) is j:
                    del PREFETCH[j.key]


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
            if not isinstance(e, weather.NsrdbAccessError):    # an access error is fully explained by its message
                self.log(traceback.format_exc())
        finally:
            _prune()


def start_weather(lat, lon, interval):
    """Start a weather retrieval for this site, or return the one already running for it.

    A finished retrieval is not reused: a new one reads the cache in moments, and also notices
    cache files deleted since."""
    key = weather.site_key(lat, lon, interval)
    with _jobs_lock:
        cur = PREFETCH.get(key)
        if cur and cur.status in DOWNLOADING:
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
        self.design = self.inputs = self.files = self.per_year = self.stamps = self.wx = self.isc_sim = None

    def _nec(self):
        d = self.design
        return analysis.nec_check(d["isc_datasheet"], d["bifacial"], d["bifacial_gain"],
                                  self.isc_sim)

    def set_isc_datasheet(self, value):
        """Module Isc at STC (datasheet) entered on the Results page (CEC library modules): recompute the PV
        Maximum Circuit Current and Inputs used, and keep it in the Inputs (.json) download."""
        if self.status != "done" or not self.result:
            raise LookupError("Results are not available for this run.")
        if self.design["module_source"] != "cec":
            raise LookupError("A custom module uses the Isc entered with its specs on the Configure page.")
        v = model.isc_datasheet(value)
        self.design["isc_datasheet"] = v
        self.design["_entered"] = sorted(set(self.design.get("_entered", [])) | {"isc_datasheet"})
        self.raw = {**self.raw, "isc_datasheet": "" if v is None else f"{v:g}"}
        self.result = {**self.result, "nec": self._nec(), "inputs_used": report.build(self.design, self.wx)}

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
        if kind == "sam_json":
            year = self.result["sam_json_year"]
            data = exports.sam_case_json(self.inputs, dict(self.files)[year])
            return f"{base}_SAM_case_inputs_{year}.json", json.dumps(data, indent=1).encode("utf-8"), "application/json"
        if kind == "inputs_json":
            return f"{base}_inputs.json", exports.inputs_json(self.raw, self.started), "application/json"
        if kind == "inputs":
            h, rows = inputs_export.build_rows(self.design, self.inputs, self.files)
            return f"{base}_SAM_inputs.csv", inputs_export.to_csv(h, rows), "text/csv"
        if kind == "all":
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
                for k in list(exports.KINDS) + ["inputs_used", "inputs_json", "sam_json", "inputs"]:
                    name, data, _ = self.export(k)
                    z.writestr(name, data)
            return f"{base}_exports.zip", buf.getvalue(), "application/zip"
        raise LookupError(f"Unknown export '{kind}'.")

    def _wait_for_prefetch(self, lat, lon, interval):
        """If a weather retrieval for this site is already running, wait for it and mirror its progress."""
        with _jobs_lock:
            pre = PREFETCH.get(weather.site_key(lat, lon, interval))
        if not pre or pre.status not in DOWNLOADING:
            return
        self.log("Weather retrieval for this site is already in progress (started from the Configure page); "
                 "waiting for it to finish.")
        while pre.status in DOWNLOADING:
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
                # "spawn" everywhere (the Windows default): forking a multi-threaded server is unsafe.
                spawn = multiprocessing.get_context("spawn")
                with cf.ProcessPoolExecutor(max_workers=workers, mp_context=spawn) as ex:
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
                        raise InterruptedError("Cancelled") from None
                    _done(*model.run_year(t))

            stage = "analysis"
            self.status, self.message = "analyzing", "Calculating 3-hour averages and max Voc"
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
            self.log("3-hour averages and max Voc calculated.")

            self.isc_sim = summary["worst"]["isc_max"]["value"]
            site = weather.nsrdb_site_info(files[0][1])
            self.design, self.inputs, self.files = design, inputs, files
            self.per_year, self.stamps = per_year, stamps
            years_run = [y for y, _ in files]
            wx = {"years": years_run, "count": n_files, "first": years_run[0], "last": years_run[-1],
                  "unavailable_years": self.weather["unavailable_years"], "dataset": config.NSRDB_DATASET,
                  "nsrdb_lat": site.get("Latitude"), "nsrdb_lon": site.get("Longitude"),
                  "location_id": site.get("Location ID"), "interval": interval}
            self.wx = wx
            self.result = {
                "summary": summary,
                "nec": self._nec(),
                "project": design["project"],
                "module_source": design["module_source"],
                "isc_cec": None if design["module_source"] == "custom" else design["module"]["i_sc_ref"],
                "inputs_used": report.build(design, wx),
                "cec_tip": report.CEC_SPECS_TIP,
                "weather": wx,
                "sam_json_year": summary["worst"]["isc_max"]["year"],   # SAM case export uses the worst-case Isc year
                "elapsed_s": round(time.time() - self.started, 1),
            }
            self.status, self.message = "done", "Complete"
            self.log(f"Done in {self.result['elapsed_s']} s.")
        except InterruptedError:
            self.status, self.message = "cancelled", "Cancelled. Weather years already retrieved are cached."
        except model.DesignError as e:
            self.failed_stage = stage
            self.status, self.error, self.message = "error", str(e), str(e)
        except weather.NsrdbAccessError as e:
            self.failed_stage = stage
            self.status, self.error, self.message = "error", f"{e}", "Run failed"
        except Exception as e:  # noqa: BLE001
            self.failed_stage = stage
            self.status, self.error, self.message = "error", f"{e}", "Run failed"
            self.log(traceback.format_exc())
        finally:
            _prune()


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
    mount = [config.RACKING_LABELS[rk]]
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
        bif = f"Yes · bifaciality {d['bifaciality']:g} · gain {d['bifacial_gain']:g} %"
    mismatch = ("not applicable (monofacial)" if not d["bifacial"]
                else "Include ⚠ PPE default is Exclude" if d["bifacial_mismatch"] else "Exclude")
    site = f"{d['lat']}, {d['lon']}"
    if d["location_mode"] == "address":
        site = f"{d['address']} → {site}"
    if d["project"]:
        site += f" · {d['project']}"
    rows_txt = f"{d['rows']}" + ("" if d["rows"] == config.PPE_STANDARD_ROWS else " ⚠ PPE standard is 1 row")
    sel, ppe = (config.SELF_SHADING[d["self_shading"]][1], config.SELF_SHADING[d["self_shading_ppe"]][1])
    shade_txt = sel + ("" if sel == ppe else f" ⚠ PPE standard is {ppe}")
    limits_txt = " · ".join(f"{label} {d[k]:g} V" for k, (label, _dflt) in config.INVERTER_LIMITS.items())
    if not d["inverter_limits_default"]:
        defaults = " · ".join(f"{dflt:g}" for _l, dflt in config.INVERTER_LIMITS.values())
        limits_txt += f" ⚠ PPE default is {defaults} V"
    groups = [
        ["Site and weather", [
            ["Site", site],
            ["Weather", f"{config.NSRDB_DATASET}, {years[0]}-{years[-1]}, {d['interval']}-minute"]]],
        ["Module", [
            ["Module", f"{m['name']} ({'custom' if d['module_source'] == 'custom' else 'CEC library'})"],
            ["Dimensions", f"{d['module_length_mm']:g} × {d['module_width_mm']:g} mm"],
            [model.ISC_DATASHEET_LABEL, "Enter it on the Results page" if d["isc_datasheet"] is None
             else f"{d['isc_datasheet']:g} A"],
            ["Bifacial", bif]]],
        ["Inverter", [["Inverter", inv["name"]]]],
        ["System design", [
            ["Circuit", f"{d['modules_per_string']} modules per string"],
            ["Mounting", " · ".join(mount)],
            ["Subarray", f"{d['modules_high']} high × {d['modules_across']} across · {spacing}"],
            ["Modeled", f"{d['nstrings']} string(s) on 1 inverter"]]],
        ["Advanced settings", [
            ["Bifacial electrical mismatch", mismatch],
            ["Self-shading", shade_txt],
            ["Inverter voltage limits", limits_txt],
            ["Number of rows", rows_txt]]],
    ]
    return {"groups": groups}


def start(raw_design):
    job = Job(raw_design)
    with _jobs_lock:
        JOBS[job.id] = job
    threading.Thread(target=job.run, daemon=True).start()
    return job
