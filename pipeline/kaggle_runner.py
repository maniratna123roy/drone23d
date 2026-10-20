"""
Spatial Twin: Kaggle Cloud GPU Automated Runner (pipeline/kaggle_runner.py)

Beginner Analogy:
The courier service to the cloud supercomputer:
Takes your drone footage, sends it to Kaggle's free 16GB GPU cluster, monitors
the 3D Gaussian Splatting training progress in the cloud, and downloads the finished
photorealistic 3D scene directly into your digital twin.
"""

import os
import sys
import time
import json
import shutil
import asyncio
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from dotenv import load_dotenv

load_dotenv()

# Keep temporary kernel & dataset files outside the workspace to prevent uvicorn WatchFiles from reloading on .py changes
KAGGLE_KERNEL_DIR = Path.home() / ".spatial_twin_cache" / "kaggle_kernel"
KAGGLE_KERNEL_DIR.mkdir(parents=True, exist_ok=True)

KAGGLE_DATASET_DIR = Path.home() / ".spatial_twin_cache" / "kaggle_dataset"
KAGGLE_DATASET_DIR.mkdir(parents=True, exist_ok=True)

def is_kaggle_configured() -> bool:
    """Checks if Kaggle credentials are set in environment or ~/.kaggle/kaggle.json."""
    username = os.environ.get("KAGGLE_USERNAME", "").strip()
    key = os.environ.get("KAGGLE_KEY", "").strip()
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    access_token = Path.home() / ".kaggle" / "access_token"
    return bool((username and key) or kaggle_json.exists() or access_token.exists())

def ensure_kaggle_auth() -> str:
    """
    Ensures Kaggle credentials from .env are written to ~/.kaggle/kaggle.json and access_token,
    and sets environment variables (including KAGGLE_API_TOKEN for modern KGAT_ tokens),
    then authenticates with Kaggle.
    Returns the active Kaggle username.
    """
    username = os.environ.get("KAGGLE_USERNAME", "").strip()
    key = os.environ.get("KAGGLE_KEY", "").strip()

    kaggle_dir = Path.home() / ".kaggle"
    kaggle_json = kaggle_dir / "kaggle.json"
    access_token_file = kaggle_dir / "access_token"

    if username and key:
        kaggle_dir.mkdir(parents=True, exist_ok=True)
        # Modern Kaggle access tokens (KGAT_...) require KAGGLE_API_TOKEN for Bearer auth
        if key.startswith("KGAT_") or not key.isalnum():
            os.environ["KAGGLE_API_TOKEN"] = key
            try:
                with open(access_token_file, "w", encoding="utf-8") as f:
                    f.write(key)
            except Exception:
                pass

        try:
            with open(kaggle_json, "w", encoding="utf-8") as f:
                json.dump({"username": username, "key": key}, f)
            try:
                kaggle_json.chmod(0o600)
            except Exception:
                pass
        except Exception as write_err:
            print(f"[KAGGLE WARN] Could not write ~/.kaggle/kaggle.json: {write_err}")

        os.environ["KAGGLE_USERNAME"] = username
        os.environ["KAGGLE_KEY"] = key
    elif kaggle_json.exists():
        try:
            with open(kaggle_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                username = data.get("username", "")
                k = data.get("key", "")
                if k:
                    os.environ["KAGGLE_KEY"] = k
                    if k.startswith("KGAT_"):
                        os.environ["KAGGLE_API_TOKEN"] = k
                if username:
                    os.environ["KAGGLE_USERNAME"] = username
        except Exception as read_err:
            print(f"[KAGGLE WARN] Could not read ~/.kaggle/kaggle.json: {read_err}")

    if not username:
        raise RuntimeError(
            "Kaggle username not found. Please set KAGGLE_USERNAME and KAGGLE_KEY in .env"
        )

    import kaggle
    kaggle.api.authenticate()
    return username

def prepare_kaggle_kernel_files(username: str, kernel_slug: str = "spatial-twin-3dgs-worker", dataset_id: Optional[str] = None, request: Optional[dict] = None):
    """Prepares metadata and script for Kaggle 16GB GPU execution."""
    meta = {
        "id": f"{username}/{kernel_slug}",
        "title": kernel_slug.replace("-", " ").title(),
        "code_file": "train_splat.py",
        "language": "python",
        "kernel_type": "script",
        "is_private": "true",
        "enable_gpu": "true",
        "enable_internet": "true",
        "dataset_sources": [dataset_id] if dataset_id else []
    }
    
    meta_path = KAGGLE_KERNEL_DIR / "kernel-metadata.json"
    meta_json = json.dumps(meta, indent=2)
    if not meta_path.exists() or meta_path.read_text(encoding="utf-8") != meta_json:
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(meta_json)

    from pipeline.kaggle_worker_script import build_worker_script

    if request is None:
        raise ValueError("Kaggle kernel requires an upload-bound reconstruction request")

    script_path = KAGGLE_KERNEL_DIR / "train_splat.py"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(build_worker_script(request))
    return script_path

async def upload_drone_video_to_kaggle_dataset(
    video_path: Path,
    username: str,
    dataset_slug: str = "spatial-twin-drone-data"
) -> Optional[str]:
    """
    Uploads or updates the drone video as a Kaggle Dataset so the Kaggle GPU
    worker can access it under /kaggle/input/spatial-twin-drone-data/.
    """
    import kaggle

    dataset_id = f"{username}/{dataset_slug}"
    KAGGLE_DATASET_DIR.mkdir(parents=True, exist_ok=True)

    dest_video = KAGGLE_DATASET_DIR / "drone_footage.mp4"
    # File size is not identity: different recordings can have identical sizes.
    shutil.copy2(video_path, dest_video)
    # Old sparse cameras were extracted with different frame decoding/resizing.
    # Solve Phase A on the actual cloud frames instead of mixing camera/image sets.
    stale_sparse = KAGGLE_DATASET_DIR / "colmap_sparse"
    if stale_sparse.exists():
        shutil.rmtree(stale_sparse)

    metadata = {
        "title": "Spatial Twin Drone Data",
        "id": dataset_id,
        "licenses": [{"name": "CC0-1.0"}]
    }
    meta_path = KAGGLE_DATASET_DIR / "dataset-metadata.json"
    meta_json = json.dumps(metadata, indent=2)
    if not meta_path.exists() or meta_path.read_text(encoding="utf-8") != meta_json:
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(meta_json)

    try:
        # Check if dataset already exists
        await asyncio.to_thread(kaggle.api.dataset_status, dataset_id)
        print(f"[KAGGLE] Updating existing dataset '{dataset_id}'...")
        await asyncio.to_thread(
            kaggle.api.dataset_create_version,
            str(KAGGLE_DATASET_DIR),
            "New drone video upload",
            dir_mode="zip",
            quiet=False
        )
    except Exception as status_error:
        # A failed update must not silently reuse a previous dataset version.
        if not (getattr(status_error, "status", None) == 404 or "404" in str(status_error)):
            raise RuntimeError(f"Kaggle dataset upload failed: {status_error}") from status_error
        # Create new dataset
        try:
            print(f"[KAGGLE] Creating new dataset '{dataset_id}'...")
            await asyncio.to_thread(
                kaggle.api.dataset_create_new,
                str(KAGGLE_DATASET_DIR),
                dir_mode="zip",
                quiet=False
            )
        except Exception as e:
            raise RuntimeError(f"Kaggle dataset creation failed: {e}") from e

    # Dataset processing is asynchronous. Do not attach the previous ready version.
    for _ in range(120):
        data = await asyncio.to_thread(kaggle.api.dataset_status, dataset_id)
        if hasattr(data, "to_dict"):
            data = data.to_dict()
        status = str(data if isinstance(data, str) else data.get("status", "") if isinstance(data, dict) else getattr(data, "status", "")).lower().split(".")[-1]
        if status == "ready":
            return dataset_id
        if status in {"error", "failed"}:
            raise RuntimeError("Kaggle dataset processing failed. Retry the upload.")
        await asyncio.sleep(5)
    raise TimeoutError("Kaggle dataset did not become ready. Retry the upload.")

def sync_kaggle_splats_to_db(splat_file: Path, classes_file: Path) -> int:
    """
    Parses downloaded Kaggle 3DGS binary splats, clusters building structures via DBSCAN,
    writes extracted_structures.json, and syncs 3D SFCGAL solids into PostGIS database.
    """
    import numpy as np
    import json
    from sklearn.cluster import DBSCAN
    from shapely.geometry import MultiPoint, mapping

    dt = np.dtype([('pos', '<f4', 3), ('scale', '<f4', 3), ('rgba', 'u1', 4), ('rot', 'u1', 4)])
    data = np.fromfile(splat_file, dtype=dt)
    pos = data['pos']
    classes = np.fromfile(classes_file, dtype=np.uint8)

    # Remap class 2 to 0 if legacy worker used 2 for structures
    if np.all(classes != 0) and np.any(classes == 2):
        classes[classes == 2] = 0
        classes.tofile(classes_file)

    struct_mask = (classes == 0)
    struct_pts = pos[struct_mask]
    if len(struct_pts) == 0:
        return 0

    clustering = DBSCAN(eps=4.0, min_samples=30, n_jobs=-1).fit(struct_pts[:, :2])
    cluster_labels = clustering.labels_
    unique_clusters = sorted([c for c in set(cluster_labels) if c != -1])
    if len(unique_clusters) == 0 and len(struct_pts) > 0:
        print("[KAGGLE WARN] DBSCAN found no clusters with min_samples=30, treating all structure points as 1 building.")
        cluster_labels = np.zeros(len(struct_pts), dtype=int)
        unique_clusters = [0]

    structures = []
    for c_id in unique_clusters:
        pts = struct_pts[cluster_labels == c_id]
        min_x, min_y, min_z = pts.min(axis=0)
        max_x, max_y, max_z = pts.max(axis=0)
        hull = MultiPoint(pts[:, :2]).convex_hull
        cx, cy = (min_x + max_x) / 2.0, (min_y + max_y) / 2.0
        region = "center"
        if cy > 15:
            region = "north"
        elif cy < -15:
            region = "south"
        elif cx > 15:
            region = "east"
        elif cx < -15:
            region = "west"

        structures.append({
            "building_id": int(c_id + 1),
            "class": "structure",
            "region": region,
            "height_m": round(float(max_z - min_z), 1),
            "original_height_m": round(float(max_z - min_z), 1),
            "area_m2": round(float(hull.area), 1),
            "splat_count": int(len(pts)),
            "splat_bbox": {
                "min_x": round(float(min_x), 2),
                "min_y": round(float(min_y), 2),
                "min_z": round(float(min_z), 2),
                "max_x": round(float(max_x), 2),
                "max_y": round(float(max_y), 2),
                "max_z": round(float(max_z), 2)
            },
            "footprint": mapping(hull)
        })

    out_json = Path("./output/mill/extracted_structures.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w") as f:
        json.dump(structures, f, indent=2)

    # Write identity frame transform so PostGIS loader uses level frame
    frame_tf = {
        "plane_normal": [0.0, 0.0, 1.0],
        "ground_elevation": 0.0,
        "transform_matrix_4x4": [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0]
        ],
        "is_aligned": True
    }
    tf_path = Path("./output/mill/frame_transform.json")
    tf_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tf_path, "w") as f:
        json.dump(frame_tf, f, indent=2)

    return len(structures)

def safe_kaggle_kernels_output(kernel_id: str, target_dir: Path):
    """
    Downloads Kaggle kernel output files with Windows-safe UTF-8 encoding support.
    The official kaggle SDK writes the kernel log file using built-in open() without
    specifying encoding='utf-8', causing UnicodeEncodeError on Windows when logs
    contain unicode characters (such as progress bars or emojis).
    """
    import kaggle
    import builtins
    orig_open = builtins.open

    def utf8_safe_open(file, mode="r", *args, **kwargs):
        if "w" in mode and "b" not in mode and "encoding" not in kwargs:
            kwargs["encoding"] = "utf-8"
            kwargs["errors"] = "replace"
        return orig_open(file, mode, *args, **kwargs)

    try:
        builtins.open = utf8_safe_open
        kaggle.api.kernels_output(kernel_id, path=str(target_dir))
    finally:
        builtins.open = orig_open

def fetch_kaggle_kernel_failure_reason(kernel_id: str) -> Optional[str]:
    """Fetches kernel logs if available to provide actionable diagnostic details on failure."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return None
    import tempfile
    temp_dir = Path(tempfile.mkdtemp())
    try:
        safe_kaggle_kernels_output(kernel_id, temp_dir)
        log_files = list(temp_dir.glob("*.log")) + list(temp_dir.glob("*.txt"))
        for log_f in log_files:
            content = log_f.read_text(encoding="utf-8", errors="replace")
            if "Temporary failure in name resolution" in content or "Failed to establish a new connection" in content:
                return (
                    "Kaggle kernel has no internet access. Kaggle requires Phone Verification "
                    "to allow outbound internet access in GPU notebooks. Please verify your phone number in "
                    "your Kaggle account settings (https://www.kaggle.com/settings -> Phone Verification) and retry."
                )
            if "Traceback (most recent call last)" in content:
                tb_lines = content[content.rfind("Traceback (most recent call last)"):].splitlines()
                error_summary = " ".join([l.strip() for l in tb_lines[-4:] if l.strip()])
                return f"Kaggle worker crashed: {error_summary}"
    except Exception:
        pass
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return None

async def run_kaggle_3dgs_job(
    video_path: str | Path,
    progress_callback: Optional[Callable[[str, int, Dict[str, Any]], None]] = None,
    *, request: Optional[dict] = None, output_dir: Optional[Path] = None,
    timeout_seconds: int = 7200,
) -> Dict[str, Any]:
    """
    Submits a 3DGS training job to Kaggle Cloud GPU, monitors status,
    downloads and verifies results in isolation. Publication is a separate commit.
    """
    v_path = Path(video_path)
    from pipeline.scene_publication import sha256_file, validate_job_id
    if not v_path.is_file() or not v_path.stat().st_size:
        raise ValueError("The uploaded video is empty or missing")
    ticket = {"job_id": uuid.uuid4().hex, "source_name": v_path.name,
              "max_frames": 36, "image_width": 640, "render_width": 320,
              "iterations": 600, "max_gaussians": 40000, "camera_model": "SIMPLE_RADIAL",
              **(request or {}), "video_sha256": sha256_file(v_path)}
    validate_job_id(ticket["job_id"])
    if timeout_seconds <= 0:
        raise ValueError("Kaggle timeout must be positive")

    if not is_kaggle_configured():
        raise RuntimeError(
            "Kaggle credentials not configured. Please add KAGGLE_USERNAME and KAGGLE_KEY "
            "to your .env file."
        )

    username = ensure_kaggle_auth()
    import kaggle

    def report(step: str, pct: int, details: Dict[str, Any] = None):
        if details is None:
            details = {}
        if progress_callback:
            progress_callback(step, pct, details)
        print(f"[KAGGLE {pct:3d}%] {step}", flush=True)

    report("Authenticating with Kaggle Cloud API", 10)
    await asyncio.sleep(0.5)

    # 1. Upload video as Kaggle Dataset
    report(f"Uploading drone footage to Kaggle Cloud Dataset '{username}/spatial-twin-drone-data'", 25)
    dataset_id = await upload_drone_video_to_kaggle_dataset(v_path, username)

    # 2. Prepare GPU kernel
    # A unique kernel prevents polling/downloading a previous completed run.
    kernel_slug = "spatial-twin-" + ticket["job_id"]
    kernel_id = f"{username}/{kernel_slug}"
    prepare_kaggle_kernel_files(username, kernel_slug, dataset_id, ticket)

    report(f"Pushing GPU kernel '{kernel_id}' to Kaggle 16GB GPU cluster", 40)
    await asyncio.to_thread(kaggle.api.kernels_push, str(KAGGLE_KERNEL_DIR))

    # 3. Poll status
    report("Kaggle GPU cloud worker queued...", 45)
    max_checks = max(1, timeout_seconds // 5)
    for i in range(max_checks):
        await asyncio.sleep(5)
        try:
            status_data = await asyncio.to_thread(kaggle.api.kernels_status, kernel_id)
            if hasattr(status_data, "to_dict"):
                s_dict = status_data.to_dict()
                status_str = str(s_dict.get("status", "")).lower()
                failure_msg = s_dict.get("failureMessage") or s_dict.get("failure_message", "")
            elif isinstance(status_data, dict):
                status_str = str(status_data.get("status", "")).lower()
                failure_msg = status_data.get("failureMessage", "")
            else:
                status_str = str(getattr(status_data, "status", "")).lower()
                failure_msg = getattr(status_data, "failure_message", getattr(status_data, "failureMessage", ""))

            # Strip any enum prefix like "kernelworkerstatus."
            if "." in status_str:
                status_str = status_str.split(".")[-1]

            if status_str in {"running", "queued"}:
                pct = min(88, 48 + int((i / max_checks) * 40))
                report(f"Kaggle GPU training in progress ({status_str}, check {i+1}/{max_checks})...", pct)
            elif status_str in {"complete", "completed"}:
                report("Kaggle 3DGS training complete! Downloading 3D splats...", 90)
                break
            elif status_str in {"error", "failed"}:
                error_msg = failure_msg
                if not error_msg or error_msg.lower() == "kaggle kernel failed.":
                    diag = await asyncio.to_thread(fetch_kaggle_kernel_failure_reason, kernel_id)
                    error_msg = diag or failure_msg or "Kaggle kernel failed."
                raise RuntimeError(f"Kaggle execution failed: {error_msg}")
            elif status_str not in {"running", "queued"}:
                raise RuntimeError(f"Kaggle returned an unexpected worker status: {status_str}")
        except Exception as e:
            if isinstance(e, RuntimeError) or "failed" in str(e).lower() or "error" in str(e).lower():
                raise
            print(f"[KAGGLE POLL WARN] {e}", flush=True)
    else:
        raise TimeoutError("Kaggle reconstruction timed out; no output was published. Check the kernel log and retry.")

    # 4. Download output files from Kaggle
    report("Downloading verified Kaggle scene bundle...", 93)
    dest_dir = Path(output_dir) if output_dir else KAGGLE_KERNEL_DIR / ("output-" + ticket["job_id"])
    dest_dir.mkdir(parents=True, exist_ok=False)
    await asyncio.to_thread(safe_kaggle_kernels_output, kernel_id, dest_dir)
    manifest = verify_kaggle_bundle(dest_dir, ticket["job_id"], ticket["video_sha256"])
    report("Cloud reconstruction downloaded and verified", 97)
    return {
        "status": "completed",
        "provider": "kaggle",
        "kernel_id": kernel_id,
        "video": v_path.name,
        "buildings_extracted": 0,
        "gaussian_count": manifest["gaussian_count"],
        "class_counts": manifest["classification"]["class_counts"],
        "video_sha256": ticket["video_sha256"],
        "bundle_dir": str(dest_dir),
    }


def verify_kaggle_bundle(directory: Path, job_id: str, video_sha256: str) -> dict:
    """Reject stale, corrupt, or legacy cloud outputs before touching the viewer."""
    from pipeline.scene_publication import read_json, read_current_scene, sha256_file, validate_splat_files

    directory = Path(directory)
    result = read_json(directory / "cloud_result.json")
    manifest = read_current_scene(directory / "published")
    if (result.get("status") != "PASSED" or result.get("job_id") != job_id
            or result.get("video_sha256") != video_sha256 or not manifest
            or manifest.get("job_id") != job_id):
        raise ValueError("Kaggle output does not match this video upload")
    scene = directory / "published/scenes" / job_id
    if sha256_file(scene / "manifest.json") != result.get("manifest_sha256"):
        raise ValueError("Kaggle manifest failed integrity verification")
    quality = manifest.get("quality", {})
    if (any(quality.get(phase) != "PASSED" for phase in ("phase_a", "phase_b", "phase_c"))
            or manifest.get("coordinate_frame") != "COLMAP_PHASE_A"
            or manifest.get("semantics") != "CLASSIFIED_MULTIVIEW"
            or manifest.get("classification", {}).get("method") != "SEGFORMER_DEPTH_VISIBLE_MULTIVIEW"
            or manifest["classification"].get("thresholds") != {
                "pixel_confidence": 0.65, "min_views": 2, "min_agreement": 0.65,
                "relative_depth_tolerance": 0.02}):
        raise ValueError("Kaggle output is missing local A/B/C and depth-visible classification gates")
    validate_splat_files(scene / "scene.splat", scene / "scene.classes.u8", manifest["gaussian_count"], classified=True)
    return manifest


def publish_kaggle_bundle(directory: Path, static_dir: Path, job_id: str, video_sha256: str) -> dict:
    """Copy the already-verified immutable bundle and atomically switch the pointer."""
    from pipeline.scene_publication import atomic_json

    manifest = verify_kaggle_bundle(directory, job_id, video_sha256)
    static_dir = Path(static_dir)
    parent = static_dir / "scenes"
    parent.mkdir(parents=True, exist_ok=True)
    destination = parent / job_id
    if destination.exists():
        raise ValueError("Scene versions are immutable; use a new Kaggle job")
    staging = parent / ("." + job_id + "." + uuid.uuid4().hex + ".staging")
    try:
        shutil.copytree(Path(directory) / "published/scenes" / job_id, staging)
        os.replace(staging, destination)
        # Verify copied bytes before the single publication commit point.
        from pipeline.scene_publication import sha256_file
        for name, digest in manifest["sha256"].items():
            if sha256_file(destination / name) != digest:
                raise ValueError("Kaggle scene copy failed integrity verification")
        atomic_json(static_dir / "current-scene.json", manifest)
        return manifest
    finally:
        if staging.exists():
            shutil.rmtree(staging)
