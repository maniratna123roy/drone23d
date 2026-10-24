"""Storage Manager for VantageCam v1 Sidecar.
Implements the artifact directory layout:
  captures/{capture_id}/
    - raw/: uploaded video and GPS/telemetry logs
    - frames/: extracted & scored keyframes (stage 1)
    - work/: intermediate files (SfM, dense depth, untextured mesh)
    - out/: final published products (GLB, LAZ, GeoTIFF, splats, manifest)

Real-world analogy: Like a job site office — raw materials come in one door,
finished products go out another, and the work happens in between.
"""

from pathlib import Path
from typing import Dict, Optional
import json


class StorageManager:
    """Manages directory structure and artifact storage for VantageCam captures."""
    
    def __init__(self, base_dir: Path = Path("output/vantagecam")):
        """Initialize storage manager.
        
        Args:
            base_dir: Root directory for all vantagecam captures (default: output/vantagecam)
        """
        self.base_dir = Path(base_dir).resolve()
        self.captures_dir = self.base_dir / "captures"
        self.captures_dir.mkdir(parents=True, exist_ok=True)
    
    def get_capture_dir(self, capture_id: str) -> Path:
        """Get or create the root directory for a capture.
        
        Args:
            capture_id: Unique capture identifier
            
        Returns:
            Path to captures/{capture_id}/
        """
        cap_dir = self.captures_dir / capture_id
        cap_dir.mkdir(parents=True, exist_ok=True)
        return cap_dir
    
    def get_subdirs(self, capture_id: str) -> Dict[str, Path]:
        """Get or create all four subdirectories for a capture.
        
        Args:
            capture_id: Unique capture identifier
            
        Returns:
            Dict with keys: raw, frames, work, out
        """
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
        """Get raw/ directory (uploaded video, GPS logs)."""
        return self.get_subdirs(capture_id)["raw"]
    
    def get_frames_dir(self, capture_id: str) -> Path:
        """Get frames/ directory (keyframe images)."""
        return self.get_subdirs(capture_id)["frames"]
    
    def get_work_dir(self, capture_id: str) -> Path:
        """Get work/ directory (intermediate SfM, depth, untextured mesh)."""
        return self.get_subdirs(capture_id)["work"]
    
    def get_out_dir(self, capture_id: str) -> Path:
        """Get out/ directory (final products: GLB, LAZ, GeoTIFF, splats, manifest)."""
        return self.get_subdirs(capture_id)["out"]
    
    def artifact_path(self, capture_id: str, artifact_kind: str, filename: str) -> Path:
        """Get full path for an artifact, choosing directory by kind.
        
        Args:
            capture_id: Capture identifier
            artifact_kind: File type (glb, obj, laz, cog_geotiff, orthomosaic_png, dsm_tif, splat_ply, manifest_json, etc.)
            filename: Filename
            
        Returns:
            Full Path to artifact
        """
        out_dir = self.get_out_dir(capture_id)
        return out_dir / filename
    
    def save_manifest(self, capture_id: str, manifest_data: dict) -> Path:
        """Save capture manifest.json to out/ directory.
        
        Args:
            capture_id: Capture identifier
            manifest_data: Manifest dictionary
            
        Returns:
            Path to saved manifest.json
        """
        manifest_path = self.get_out_dir(capture_id) / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f, indent=2)
        return manifest_path
    
    def load_manifest(self, capture_id: str) -> Optional[dict]:
        """Load capture manifest.json from out/ directory.
        
        Args:
            capture_id: Capture identifier
            
        Returns:
            Manifest dict, or None if not found
        """
        manifest_path = self.get_out_dir(capture_id) / "manifest.json"
        if not manifest_path.exists():
            return None
        with open(manifest_path, "r") as f:
            return json.load(f)
    
    def cleanup_capture(self, capture_id: str, keep_artifacts: bool = False) -> None:
        """Delete a capture directory (optionally keeping only out/ artifacts).
        
        Args:
            capture_id: Capture identifier
            keep_artifacts: If True, only delete raw/, frames/, work/ and keep out/
        """
        cap_dir = self.get_capture_dir(capture_id)
        if keep_artifacts:
            # Delete intermediate directories, keep out/
            for subdir_name in ["raw", "frames", "work"]:
                subdir = cap_dir / subdir_name
                if subdir.exists():
                    import shutil
                    shutil.rmtree(subdir)
        else:
            # Delete entire capture
            import shutil
            if cap_dir.exists():
                shutil.rmtree(cap_dir)
