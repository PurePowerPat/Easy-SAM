"""Start the PPE SAM Multi-Year app: local server + opens the browser.

run_app.py                 start the app
run_app.py file.esam       open a project file (starts the app, or uses the one already running)
run_app.py --register      double-clicking an .esam file opens it here (this Windows user); --unregister undoes it
"""
import multiprocessing
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()   # required for the parallel SAM runs inside a packaged .exe
    from ppe_sam.server import main
    sys.exit(main(sys.argv[1:]))
