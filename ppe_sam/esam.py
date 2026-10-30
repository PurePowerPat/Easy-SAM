"""Easy-SAM project files (.esam): the saved inputs, opened by double-clicking them.

An .esam file is the "Save inputs" JSON ({format, version, app_version, saved, inputs}) under its own
extension. Opening one (`run_app.py <file>.esam`, which is what a double-click runs once the extension is
registered) starts the app, or hands the file to the app when it is already running, and opens the browser
with those inputs loaded on the Configure page.

The extension is registered for the current Windows user only (HKCU, no admin rights) with
`run_app.py --register` (register_esam.bat); `--unregister` removes it.
"""
import json
import os
import secrets
import sys
import threading
import urllib.request
from pathlib import Path

from . import exports

EXT = ".esam"
PROG_ID = "EasySAM.Project"
TYPE_NAME = "Easy-SAM project"
MAX_BYTES = 5 * 1024 * 1024
HANDED_OFF = 3                  # exit code of run_app.py when the file went to an app that was already running
MAX_PENDING = 20

_pending = {}                   # token -> {"name", "project"}: opened files waiting for the page to fetch them
_lock = threading.Lock()


class ProjectError(ValueError):
    pass


def check(project) -> dict:
    """The project file contents (a dict) if they are a saved-inputs file, else ProjectError."""
    if not isinstance(project, dict) or project.get("format") != exports.INPUTS_FORMAT \
            or not isinstance(project.get("inputs"), dict):
        raise ProjectError("not an Easy-SAM project file")
    return project


def read(path) -> dict:
    """{"name": file name, "project": contents} of an .esam (or saved inputs .json) file."""
    p = Path(path)
    try:
        if p.stat().st_size > MAX_BYTES:
            raise ProjectError("the file is too large")
        project = json.loads(p.read_bytes())
    except OSError as e:
        raise ProjectError(e.strerror or str(e)) from e
    except ValueError as e:
        raise ProjectError(f"not valid JSON ({e})") from e
    return {"name": p.name, "project": check(project)}


def hold(opened) -> str:
    """Keep an opened file until the page asks for it; returns the token for the page URL (?open=token)."""
    token = secrets.token_urlsafe(12)
    with _lock:
        while len(_pending) >= MAX_PENDING:
            _pending.pop(next(iter(_pending)))
        _pending[token] = opened
    return token


def take(token):
    with _lock:
        return _pending.pop(token, None)


def find_running(ports, version):
    """Port of an app of this version already running on this computer, or None."""
    for port in ports:
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/info", timeout=1) as r:
                if r.headers.get("Server", "").startswith("PPE-SAM/") and json.load(r).get("version") == version:
                    return port
        except (OSError, ValueError):
            continue
    return None


def hand_off(port, opened) -> str:
    """Give an opened file to the app running on `port`; returns its token."""
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/open", method="POST",
                                 data=json.dumps(opened).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)["token"]


# ---------------- Windows file association ----------------
def open_command() -> str:
    """What Windows runs for a double-clicked .esam: the .exe, or run_from_source.bat (sets up .venv first)."""
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable).resolve()}" "%1"'
    return f'"{Path(__file__).resolve().parent.parent / "run_from_source.bat"}" "%1"'


def register() -> str:
    import winreg
    root = r"Software\Classes"
    values = {rf"{root}\{EXT}": PROG_ID, rf"{root}\{PROG_ID}": TYPE_NAME,
              rf"{root}\{PROG_ID}\shell\open\command": open_command()}
    if getattr(sys, "frozen", False):
        values[rf"{root}\{PROG_ID}\DefaultIcon"] = f'"{Path(sys.executable).resolve()}",0'
    for key, value in values.items():
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, value)
    _notify_explorer()
    return f"{EXT} files now open with: {open_command()}"


def unregister() -> str:
    import winreg

    def delete(key):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                for sub in [winreg.EnumKey(k, i) for i in range(winreg.QueryInfoKey(k)[0])]:
                    delete(rf"{key}\{sub}")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key)
        except FileNotFoundError:
            pass

    delete(rf"Software\Classes\{PROG_ID}")
    delete(rf"Software\Classes\{EXT}")
    _notify_explorer()
    return f"{EXT} files are no longer opened with {TYPE_NAME}."


def _notify_explorer():
    if os.name == "nt":
        import ctypes
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)   # SHCNE_ASSOCCHANGED: refresh icons
