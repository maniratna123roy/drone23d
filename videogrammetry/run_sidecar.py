"""Standalone runner for the Videogrammetry Sidecar service.
Runs independently on port 8001 without interfering with the host backend on port 8000.
"""

import sys
from pathlib import Path

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import uvicorn
from videogrammetry.api import sidecar_app

if __name__ == "__main__":
    print("\n=======================================================")
    print("  VIDEOGRAMMETRY SIDECAR SERVICE (Skyebrowse Model)")
    print("  Running on: http://127.0.0.1:8001")
    print("  Swagger UI: http://127.0.0.1:8001/docs")
    print("=======================================================\n")
    uvicorn.run("videogrammetry.api:sidecar_app", host="127.0.0.1", port=8001, reload=True)

