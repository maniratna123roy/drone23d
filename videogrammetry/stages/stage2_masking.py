"""Stage 2: Dynamic-object masking.
Implements Section 5 Stage 2:
- Identify and mask transient or moving objects (cars, pedestrians, dynamic motion).
- Generate binary masks per keyframe so moving objects do not produce false correspondences.
- Output mask files to `frames/masks/`.
"""

import json
from pathlib import Path
from typing import Dict, Any, List
import cv2
import numpy as np

class Stage2Masking:
    def __init__(self, frames_dir: Path, work_dir: Path):
        self.frames_dir = Path(frames_dir)
        self.work_dir = Path(work_dir)
        self.masks_dir = self.frames_dir / "masks"
        self.masks_dir.mkdir(parents=True, exist_ok=True)

    def execute(self, enabled: bool = True, progress_cb=None) -> Dict[str, Any]:
        manifest_file = self.frames_dir / "frames_manifest.json"
        if not manifest_file.exists():
            return {"enabled": False, "masked_frames_count": 0, "status": "skipped"}

        with open(manifest_file, "r") as f:
            manifest = json.load(f)

        keyframes = manifest.get("keyframes", [])
        if not enabled:
            return {
                "enabled": False,
                "masked_frames_count": 0,
                "status": "skipped_by_tier_profile",
                "note": "Dynamic object masking is disabled in Lite and Standard tiers."
            }

        masked_count = 0
        total_dynamic_regions = 0

        # Background subtractor for inter-frame motion detection
        fgbg = cv2.createBackgroundSubtractorMOG2(history=10, varThreshold=50, detectShadows=False)

        for i, kf in enumerate(keyframes):
            img_path = self.frames_dir / kf["filename"]
            if not img_path.exists():
                continue

            img = cv2.imread(str(img_path))
            if img is None:
                continue

            h, w = img.shape[:2]
            fgmask = fgbg.apply(img)

            # Filter small noise blobs with morphological operations
            kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            fgmask = cv2.morphologyEx(fgmask, cv2.MORPH_OPEN, kernel)
            fgmask = cv2.dilate(fgmask, kernel, iterations=2)

            # Count dynamic pixels
            dynamic_pixels = cv2.countNonZero(fgmask)
            coverage_pct = (dynamic_pixels / (w * h)) * 100.0

            mask_filename = f"mask_{kf['filename'].replace('.jpg', '.png')}"
            mask_path = self.masks_dir / mask_filename
            cv2.imwrite(str(mask_path), fgmask)

            if coverage_pct > 0.5:
                masked_count += 1
                total_dynamic_regions += 1

            if progress_cb:
                progress_cb((i + 1) / len(keyframes))

        report = {
            "enabled": True,
            "total_frames_processed": len(keyframes),
            "masked_frames_count": masked_count,
            "total_dynamic_regions_isolated": total_dynamic_regions,
            "masks_dir": str(self.masks_dir.name),
        }

        with open(self.work_dir / "masking_report.json", "w") as f:
            json.dump(report, f, indent=2)

        return report
