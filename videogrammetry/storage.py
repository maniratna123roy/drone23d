"""Storage Manager for Videogrammetry Sidecar.
Implements the artifact directory layout defined in Section 4 & 7:
`captures/{capture_id}/` with subdirectories:
  - `raw/`: uploaded raw video and optional GPS/telemetry logs
  - `frames/`: extracted & sharpness-scored keyframes
  - `work/`: intermediate SfM matching, dense depth maps, untextured meshes
  - `out/`: final published products (GLB, OBJ, USDZ, LAZ, GeoTIFF, manifest.json)
"""

import os
from pathlib import Path
from typing import Dict, Any

class StorageManager:
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir).resolve()
        self.captures_dir = self.base_dir / "captures"
        self.captures_dir.mkdir(parents=True, exist_ok=True)

    def get_capture_dir(self, capture_id: str) -> Path:
        cap_dir = self.captures_dir / capture_id
        cap_dir.mkdir(parents=True, exist_ok=True)
        return cap_dir

    def get_subdirs(self, capture_id: str) -> Dict[str, Path]:
        cap_dir = self.get_capture_dir(capture_id)
        subdirs = {
            "raw": cap_dir / "raw",
            "frames": cap_dir / "frames",
            "work": cap_dir / "work",
            "out": cap_dir / "out",
        }
        for path in subdirs.values():
            path.mkdir(parents=True, exist_ok=True)
        return subdirs

    def get_raw_dir(self, capture_id: str) -> Path:
        return self.get_subdirs(capture_id)["raw"]

    def get_frames_dir(self, capture_id: str) -> Path:
        return self.get_subdirs(capture_id)["frames"]

    def get_work_dir(self, capture_id: str) -> Path:
        return self.get_subdirs(capture_id)["work"]

    def get_out_dir(self, capture_id: str) -> Path:
        return self.get_subdirs(capture_id)["out"]
