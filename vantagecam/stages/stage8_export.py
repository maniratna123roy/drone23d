"""Stage 8: Export — Package final artifacts and create manifest.

Real-world analogy: Like a factory's final packaging station where all products
are boxed, labeled, and prepared for shipping to customers.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Any, Optional
import shutil


class ExportError(Exception):
    """Raised when export fails."""
    pass


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file.
    
    Args:
        file_path: Path to file
        
    Returns:
        SHA256 hash as hex string
    """
    sha256 = hashlib.sha256()
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    
    return sha256.hexdigest()


def collect_artifacts(
    work_dir: Path,
    out_dir: Path,
) -> List[Dict[str, Any]]:
    """Collect all artifacts from work directory and move to out directory.
    
    Args:
        work_dir: Work directory containing intermediate files
        out_dir: Output directory for final artifacts
        
    Returns:
        List of artifact metadata dicts
    """
    artifacts = []
    
    # Define artifact patterns to collect
    artifact_patterns = [
        ("*.obj", "mesh", "Model (Wavefront OBJ)"),
        ("*.glb", "glb", "Model (glTF Binary)"),
        ("*.splat", "splat", "Gaussian Splats (binary)"),
        ("*.ply", "ply", "Point Cloud (PLY)"),
        ("*.laz", "laz", "Point Cloud (LAZ)"),
        ("*.tif", "geotiff", "Georeferenced Image"),
        ("*result.json", "metadata", "Stage Result Metadata"),
    ]
    
    for pattern, kind, description in artifact_patterns:
        for file_path in work_dir.glob(pattern):
            try:
                # Move file to out directory
                out_path = out_dir / file_path.name
                shutil.copy2(file_path, out_path)
                
                # Compute hash
                sha256 = compute_file_sha256(out_path)
                file_size = out_path.stat().st_size
                
                # Create artifact record
                artifact = {
                    "id": f"art_{len(artifacts):06d}",
                    "filename": out_path.name,
                    "kind": kind,
                    "description": description,
                    "size_bytes": file_size,
                    "sha256": sha256,
                    "mime_type": get_mime_type(out_path.suffix),
                }
                
                artifacts.append(artifact)
            
            except Exception as e:
                print(f"    ⚠ Failed to collect {file_path.name}: {e}")
    
    return artifacts


def get_mime_type(file_extension: str) -> str:
    """Get MIME type for file extension.
    
    Args:
        file_extension: File extension (e.g., '.obj', '.glb')
        
    Returns:
        MIME type string
    """
    mime_map = {
        ".obj": "model/obj",
        ".glb": "model/gltf-binary",
        ".splat": "application/octet-stream",
        ".ply": "model/ply",
        ".laz": "application/octet-stream",
        ".tif": "image/tiff",
        ".json": "application/json",
        ".png": "image/png",
    }
    
    return mime_map.get(file_extension.lower(), "application/octet-stream")


def create_manifest(
    capture_data: Dict[str, Any],
    artifacts: List[Dict[str, Any]],
    quality_report: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Create a comprehensive manifest for the capture.
    
    Args:
        capture_data: Capture metadata (id, tier, source, etc.)
        artifacts: List of artifact records
        quality_report: Quality gate report (if available)
        
    Returns:
        Manifest dictionary
    """
    manifest = {
        "schema_version": "1.0.0",
        "capture": {
            "id": capture_data.get("id"),
            "source_system": capture_data.get("source_system", "vantage_spatial_twin"),
            "source_id": capture_data.get("source_id"),
            "tier": capture_data.get("tier"),
            "crs": capture_data.get("crs", "EPSG:4326"),
            "created_at": capture_data.get("created_at"),
        },
        "artifacts": artifacts,
        "quality_gate": quality_report,
        "metadata": {
            "total_artifacts": len(artifacts),
            "total_size_bytes": sum(a.get("size_bytes", 0) for a in artifacts),
        }
    }
    
    return manifest


def create_web_manifest(
    manifest: Dict[str, Any],
    out_dir: Path,
) -> None:
    """Create a web-viewer-friendly manifest.
    
    Args:
        manifest: Full manifest dictionary
        out_dir: Output directory
    """
    # Extract key assets for web viewer
    web_manifest = {
        "capture_id": manifest["capture"]["id"],
        "tier": manifest["capture"]["tier"],
        "assets": {
            "mesh": None,
            "splats": None,
            "pointcloud": None,
            "orthomosaic": None,
            "dsm": None,
        }
    }
    
    # Map artifacts to web assets
    for artifact in manifest["artifacts"]:
        kind = artifact.get("kind")
        if kind == "glb" or kind == "mesh":
            web_manifest["assets"]["mesh"] = artifact["filename"]
        elif kind == "splat":
            web_manifest["assets"]["splats"] = artifact["filename"]
        elif kind == "laz" or kind == "ply":
            web_manifest["assets"]["pointcloud"] = artifact["filename"]
        elif kind == "geotiff":
            if "orthomosaic" in artifact["filename"].lower():
                web_manifest["assets"]["orthomosaic"] = artifact["filename"]
            elif "dsm" in artifact["filename"].lower():
                web_manifest["assets"]["dsm"] = artifact["filename"]
    
    web_path = out_dir / "manifest_web.json"
    with open(web_path, "w") as f:
        json.dump(web_manifest, f, indent=2)


def run_stage8_export(
    capture_id: str,
    capture_data: Dict[str, Any],
    work_dir: Path,
    out_dir: Path,
    quality_report: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run Stage 8: Export artifacts and create manifest.
    
    Args:
        capture_id: Capture job identifier
        capture_data: Capture metadata
        work_dir: Work directory with intermediate files
        out_dir: Output directory for final artifacts
        quality_report: Quality gate report (optional)
        
    Returns:
        Dict with export results:
        - manifest: complete manifest
        - artifact_count: number of exported artifacts
        - total_size_bytes: total size of all artifacts
        - stage8_complete: whether stage passed
    """
    print(f"[{capture_id}] Stage 8: Export Artifacts")
    
    out_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Step 1: Collect artifacts
        print(f"  Step 1: Collecting artifacts...")
        
        artifacts = collect_artifacts(work_dir, out_dir)
        
        print(f"    ✓ Collected {len(artifacts)} artifacts")
        for art in artifacts:
            size_mb = art["size_bytes"] / 1_000_000
            print(f"      - {art['filename']} ({size_mb:.1f} MB) [{art['kind']}]")
        
        # Step 2: Create manifest
        print(f"  Step 2: Creating manifest...")
        
        manifest = create_manifest(capture_data, artifacts, quality_report)
        
        # Step 3: Export manifest
        manifest_path = out_dir / "manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2, default=str)
        
        print(f"    ✓ Manifest: {manifest_path.name}")
        
        # Step 4: Create web manifest
        print(f"  Step 3: Creating web manifest...")
        
        create_web_manifest(manifest, out_dir)
        print(f"    ✓ Web manifest created")
        
        # Step 5: Create summary file
        total_size = sum(a.get("size_bytes", 0) for a in artifacts)
        summary_path = out_dir / "EXPORT_SUMMARY.txt"
        with open(summary_path, "w") as f:
            f.write(f"VantageCam v1 Export Summary\n")
            f.write(f"===========================\n\n")
            f.write(f"Capture ID: {capture_id}\n")
            f.write(f"Tier: {capture_data.get('tier')}\n")
            f.write(f"CRS: {capture_data.get('crs', 'EPSG:4326')}\n\n")
            f.write(f"Artifacts ({len(artifacts)}):\n")
            for art in artifacts:
                f.write(f"  - {art['filename']} ({art['size_bytes']/1_000_000:.1f} MB)\n")
            f.write(f"\nTotal Size: {total_size/1_000_000:.1f} MB\n")
            if quality_report:
                f.write(f"Quality Verdict: {quality_report.get('verdict', 'unknown')}\n")
        
        print(f"    ✓ Summary: {summary_path.name}")
        
        print(f"  ✓ Stage 8 complete: {len(artifacts)} artifacts exported")
        
        return {
            "stage8_complete": True,
            "artifact_count": len(artifacts),
            "total_size_bytes": total_size,
            "manifest_file": "manifest.json",
            "artifacts": [
                {
                    "filename": a["filename"],
                    "kind": a["kind"],
                    "size_mb": a["size_bytes"] / 1_000_000,
                }
                for a in artifacts
            ]
        }
    
    except Exception as e:
        print(f"  ❌ Export error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "stage8_complete": False,
            "error": str(e),
        }


if __name__ == "__main__":
    import sys
    
    capture = {
        "id": "test_capture",
        "tier": "standard",
        "source_system": "vantage_spatial_twin",
    }
    
    work = Path("output/vantagecam/test_stage8/work")
    out = Path("output/vantagecam/test_stage8/out")
    
    result = run_stage8_export("test_capture", capture, work, out)
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2, default=str))
