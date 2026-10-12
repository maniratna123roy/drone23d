"""Isolated worker for a single genuine video -> A -> B -> C reconstruction.

This process never publishes a live scene. Its parent API verifies and commits
completed assets, so an orphaned/interrupted worker cannot switch the web viewer.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import time
import traceback

from pipeline.scene_publication import atomic_json, read_json, sha256_file


def progress(step: str, percent: int, **details) -> None:
    print("SPATIAL_PROGRESS " + json.dumps({"step": step, "progress": percent, "details": details}), flush=True)


def run_reconstruction(request_path: Path) -> dict:
    from pipeline.video_processor import extract_keyframes_from_video
    from pipeline.colmap_reconstructor import stage_a_verify_colmap_geometry
    from pipeline.dense_reconstruction import stage_b_verify_dense_geometry
    from pipeline.gaussian_optimizer import execute_phase_c_3dgs_pipeline

    request = read_json(request_path)
    root = request_path.resolve().parent
    video = root / request["input_file"]
    if not video.resolve().is_relative_to(root) or not video.is_file():
        raise ValueError("Invalid job input video")
    start = time.perf_counter()
    frames, phase_a, phase_b, phase_c = (root / name for name in ("frames", "phase_a", "phase_b", "phase_c"))
    progress("Extracting real keyframes across the uploaded recording", 8)
    metadata = extract_keyframes_from_video(video, frames, request["max_frames"], request["image_width"])
    atomic_json(root / "video_metadata.json", metadata)
    progress("Phase A: solving cameras and checking sparse geometry", 15, frames=metadata["extracted_frames_count"])
    a = stage_a_verify_colmap_geometry(
        frames, phase_a,
        camera_model=request.get("camera_model", "SIMPLE_RADIAL")
    )
    if a["status"] != "PASSED":
        raise ValueError("Phase A camera geometry failed: " + ", ".join(a["quality_report"]["failed_checks"]))
    progress("Phase B: reconstructing only multi-view-supported surfaces", 35, registered_images=a["registered_images"])
    b = stage_b_verify_dense_geometry(frames, phase_a, phase_b, max_image_size=request["image_width"])
    if b["status"] != "PASSED":
        raise ValueError("Phase B surface verification failed: " + ", ".join(b["failed_checks"]))
    progress("Phase C: fitting real photographs with Gaussian optimization", 60, measured_points=b["retained_points"])
    c = execute_phase_c_3dgs_pipeline(
        phase_b, phase_c, iterations=request["iterations"], render_width=request["render_width"],
        max_gaussians=request["max_gaussians"], device=request["device"], seed=42,
    )
    if c["status"] != "PASSED":
        raise ValueError("Phase C photometric quality failed: " + ", ".join(c.get("quality_gate", {}).get("failed_checks", [])))
    from pipeline.semantic_classification import classify_scene
    progress("Classifying observed surfaces across registered camera views", 87)
    semantics = classify_scene(phase_c / "assets/scene.splat", phase_b, root / "semantics", device="cpu")
    artifact_names = ["phase_a/colmap_quality_report.json", "phase_b/dense_quality_report.json",
                      "phase_c/phase_c_report.json", "phase_c/model.pt", "phase_c/assets/scene.splat",
                      "phase_c/assets/scene.classes.u8", "semantics/classification_report.json",
                      "semantics/scene.classes.u8", "semantics/votes.npz"]
    result = {
        "status": "PASSED", "video_sha256": sha256_file(video),
        "frames_processed": metadata["extracted_frames_count"],
        "pipeline_duration_seconds": round(time.perf_counter() - start, 2),
        "artifact_sha256": {name: sha256_file(root / name) for name in artifact_names},
        "mock_scene_used": False, "procedural_fallback_run": False, "scene_published": False,
        "classification": semantics["class_counts"],
    }
    atomic_json(root / "result.json", result)
    progress("A/B/C passed; validating the immutable web scene", 95, **result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    try:
        run_reconstruction(args.request)
        return 0
    except Exception as exc:
        atomic_json(args.request.resolve().parent / "failure.json", {
            "error": str(exc), "scene_published": False,
            "guidance": "Use a continuous, well-lit shot with overlapping textured surfaces and camera translation; avoid cuts, blur and sky-only footage. No replacement geometry was generated.",
        })
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
