"""Start the PPE SAM Multi-Year app: local server + opens the browser."""
import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()   # required for the parallel SAM runs inside a packaged .exe
    from ppe_sam.server import serve
    serve()
