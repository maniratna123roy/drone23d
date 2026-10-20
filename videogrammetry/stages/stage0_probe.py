"""Stage 0: Validate and probe (CPU).
Implements Section 5 Stage 0:
- Probe codec, resolution, fps, duration, aspect ratio, frame count.
- Detect and extract embedded telemetry (DJI .SRT or companion GPS file).
- Build per-frame or timestamped timeline (lat, lon, alt, gimbal).
- Validate input requirements (minimum length warning, video stream check).
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
import cv2

class Stage0Probe:
    def __init__(self, raw_dir: Path):
        self.raw_dir = Path(raw_dir)

    def execute(self, video_path: Path, gps_path: Optional[Path] = None) -> Dict[str, Any]:
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found at: {video_path}")

        # Probe video using OpenCV
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Unable to open video stream from {video_path.name}")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration_s = frame_count / fps if fps > 0 else 0.0
        cap.release()

        file_size_bytes = video_path.stat().st_size

        # Check for companion DJI .SRT or GPS files in raw_dir
        telemetry = self._probe_telemetry(video_path, gps_path)

        warnings = []
        if duration_s < 10.0:
            warnings.append("Video duration is under 10 seconds; short clips may have insufficient parallax for 360 loop closure.")
        if width < 1280 or height < 720:
            warnings.append("Resolution is lower than 720p; reconstruction fidelity will be coarse.")

        probe_report = {
            "valid": True,
            "filename": video_path.name,
            "file_size_bytes": file_size_bytes,
            "width": width,
            "height": height,
            "resolution_str": f"{width}x{height}",
            "fps": round(fps, 2),
            "frame_count": frame_count,
            "duration_s": round(duration_s, 2),
            "has_gps": telemetry["has_gps"],
            "telemetry_points_count": len(telemetry["points"]),
            "telemetry_sample": telemetry["points"][:3] if telemetry["points"] else [],
            "warnings": warnings,
            "crs_hint": "EPSG:4326",
        }

        # Cache probe report
        report_file = self.raw_dir / "probe_report.json"
        with open(report_file, "w") as f:
            json.dump(probe_report, f, indent=2)

        return probe_report

    def _probe_telemetry(self, video_path: Path, gps_path: Optional[Path]) -> Dict[str, Any]:
        points: List[Dict[str, Any]] = []

        # 1. Check explicit GPS file
        target_gps = gps_path or (video_path.parent / f"{video_path.stem}.srt") or (video_path.parent / "gps.json")
        if target_gps and Path(target_gps).exists():
            srt_path = Path(target_gps)
            if srt_path.suffix.lower() == ".srt":
                points = self._parse_dji_srt(srt_path)
            elif srt_path.suffix.lower() == ".json":
                try:
                    with open(srt_path, "r") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            points = data
                except Exception:
                    pass

        has_gps = len(points) > 0
        return {
            "has_gps": has_gps,
            "points": points,
        }

    def _parse_dji_srt(self, srt_path: Path) -> List[Dict[str, Any]]:
        points = []
        try:
            content = srt_path.read_text(encoding="utf-8", errors="ignore")
            # DJI SRT format typically has:
            # [latitude: 26.1872] [longitude: 91.6914] [altitude: 124.5] ...
            pattern = re.compile(
                r"(?:latitude|lat)[:\s]+([+-]?\d+(?:\.\d+)?).*?(?:longitude|lon)[:\s]+([+-]?\d+(?:\.\d+)?).*?(?:rel_alt|altitude|alt)[:\s]+([+-]?\d+(?:\.\d+)?)",
                re.IGNORECASE
            )
            for match in pattern.finditer(content):
                lat, lon, alt = match.groups()
                points.append({
                    "lat": float(lat),
                    "lon": float(lon),
                    "alt_m": float(alt),
                })
        except Exception:
            pass
        return points
