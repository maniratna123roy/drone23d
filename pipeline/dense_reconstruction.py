"""Phase B: measured multi-view surfaces, never inferred architecture.

Like a surveyor accepting a surface only when multiple photographs agree,
this stage checks native COLMAP geometric depth before publishing a dense PLY.
All output stays in the Phase A COLMAP frame (relative, uncalibrated units).
"""

import hashlib
import json
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from plyfile import PlyData, PlyElement

from pipeline import colmap_reconstructor as colmap


def read_colmap_depth(path: Path) -> np.ndarray:
    """Read COLMAP's width&height&channels& + little-endian float32 format."""
    with Path(path).open("rb") as stream:
        header = bytearray()
        while header.count(b"&") < 3:
            byte = stream.read(1)
            if not byte or len(header) >= 64:
                raise ValueError(f"Invalid COLMAP depth header: {path}")
            header.extend(byte)
        try:
            width, height, channels = map(int, header[:-1].split(b"&"))
        except ValueError as exc:
            raise ValueError(f"Invalid COLMAP depth dimensions: {path}") from exc
        if width <= 0 or height <= 0 or channels != 1:
            raise ValueError(f"Expected a nonempty single-channel depth map: {path}")
        payload = stream.read()
    if len(payload) != width * height * 4:
        raise ValueError(f"Truncated or oversized COLMAP depth data: {path}")
    return np.frombuffer(payload, dtype="<f4").reshape((width, height), order="F").T.copy()


def project_points(points, pose, camera, width, height):
    """Project into undistorted pinhole images, accounting for depth resizing."""
    if camera.get("model") not in {"PINHOLE", "SIMPLE_PINHOLE"}:
        raise ValueError("Phase B depth validation requires undistorted pinhole cameras")
    if camera["width"] <= 0 or camera["height"] <= 0:
        raise ValueError("Camera dimensions must be positive")
    xyz = np.asarray(points, dtype=np.float64) @ np.asarray(pose["R_cw"]).T + pose["t_cw"]
    z = xyz[:, 2]
    valid = np.isfinite(xyz).all(axis=1) & (z > 0)
    indices = np.flatnonzero(valid)
    sx, sy = width / camera["width"], height / camera["height"]
    u = (camera["fx"] * xyz[indices, 0] / z[indices] + camera["cx"]) * sx
    v = (camera["fy"] * xyz[indices, 1] / z[indices] + camera["cy"]) * sy
    inside = np.isfinite(u) & np.isfinite(v) & (u >= 0) & (u < width - 0.5) & (v >= 0) & (v < height - 0.5)
    return indices[inside], np.rint(u[inside]).astype(int), np.rint(v[inside]).astype(int), z[indices[inside]]


def measure_depth_support(points, poses, cameras, depth_maps, depth_tolerance=0.02):
    """Count independent geometric-depth views; no data means zero support.

    Occluded/out-of-frame points are not contradictions, but do not add votes.
    This rechecks MVS measurements, not held-out ground truth or metric accuracy.
    """
    if not 0 < depth_tolerance < 1:
        raise ValueError("Depth tolerance must be between zero and one")
    counts = np.zeros(len(points), dtype=np.uint32)
    views = {}
    for name, pose in poses.items():
        if name not in depth_maps:
            continue
        depth = depth_maps[name]
        height, width = depth.shape
        indices, u, v, z = project_points(points, pose, cameras[pose["camera_id"]], width, height)
        sampled = depth[v, u]
        valid = np.isfinite(sampled) & (sampled > 0)
        relative_error = np.full(len(indices), np.inf)
        relative_error[valid] = np.abs(sampled[valid] - z[valid]) / z[valid]
        supported = valid & (relative_error <= depth_tolerance)
        counts[indices[supported]] += 1
        views[name] = {
            "valid_depth_pixels": int(np.count_nonzero(np.isfinite(depth) & (depth > 0))),
            "projected_candidates": len(indices),
            "supported_candidates": int(supported.sum()),
            "median_supported_relative_depth_error": float(np.median(relative_error[supported])) if supported.any() else None,
        }
    return counts, {"depth_tolerance_relative": depth_tolerance, "views_checked": len(views), "per_view": views}


def write_dense_ply(path, points, colors, normals):
    """Preserve observed geometry/RGB/normals without fabricated Gaussian fields."""
    fields = [(name, "f4") for name in ("x", "y", "z", "nx", "ny", "nz")]
    fields += [(name, "u1") for name in ("red", "green", "blue")]
    vertices = np.empty(len(points), dtype=fields)
    for index, name in enumerate(("x", "y", "z")):
        vertices[name] = points[:, index]
    for index, name in enumerate(("nx", "ny", "nz")):
        vertices[name] = normals[:, index]
    for index, name in enumerate(("red", "green", "blue")):
        vertices[name] = colors[:, index]
    PlyData([PlyElement.describe(vertices, "vertex")], text=False).write(str(path))


def write_dense_previews(points, colors, poses, cameras, images_dir, output_dir):
    """Three source/point/overlay triptychs; not Gaussian renders or ground truth."""
    output_dir.mkdir(parents=True, exist_ok=True)
    names = sorted(poses)
    paths = []
    for index in sorted({0, len(names) // 2, len(names) - 1}):
        name = names[index]
        with Image.open(images_dir / name) as image:
            original = np.array(image.convert("RGB"))
        height, width = original.shape[:2]
        indices, u, v, z = project_points(points, poses[name], cameras[poses[name]["camera_id"]], width, height)
        # Nearest point per pixel; black pixels honestly remain unobserved.
        order = np.argsort(z)
        _, first = np.unique(v[order] * width + u[order], return_index=True)
        selected = order[first]
        projected = np.zeros_like(original)
        projected[v[selected], u[selected]] = colors[indices[selected]]
        overlay = original.copy()
        overlay[v[selected], u[selected]] = (
            original[v[selected], u[selected]] * 0.35 + colors[indices[selected]] * 0.65
        ).astype(np.uint8)
        triptych = np.hstack((original, projected, overlay))
        banner = np.zeros((26, width * 3, 3), dtype=np.uint8)
        for x, title in ((5, "Undistorted source"), (width + 5, "Measured dense points (not 3DGS)"), (2 * width + 5, "Point overlay")):
            cv2.putText(banner, title, (x, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)
        path = output_dir / f"{Path(name).stem}_dense.png"
        Image.fromarray(np.vstack((banner, triptych))).save(path)
        paths.append(str(path))
    return paths


def stage_b_verify_dense_geometry(images_dir, phase_a_workspace, workspace_dir,
                                  max_image_size=640, min_points=500):
    """Continue a passed Phase A model with native MVS, no automatic fallback.

    Output: raw fused PLY, filtered geometry-only PLY, undistorted images/cameras,
    geometric depth maps, support counts, diagnostic images and a JSON report.
    A failed gate returns FAILED; execution failures raise with a saved report.
    """
    started = time.perf_counter()
    source = Path(images_dir).resolve()
    phase_a = Path(phase_a_workspace).resolve()
    root = Path(workspace_dir).resolve()
    prior = json.loads((phase_a / "colmap_quality_report.json").read_text(encoding="utf-8"))
    if not isinstance(prior, dict) or prior.get("status") != "PASSED":
        raise ValueError("Phase A must have a PASSED quality report before Phase B")
    if not all(isinstance(prior.get(key), str) and prior[key] for key in
               ("input_images_directory", "selected_sparse_model")) or not isinstance(prior.get("registered_image_names"), list):
        raise ValueError("Phase A report is missing required input/model/camera metadata; rerun Phase A")
    if max_image_size <= 0 or min_points <= 0:
        raise ValueError("Image size and minimum point count must be positive")
    if not source.is_dir() or source != Path(prior["input_images_directory"]).resolve():
        raise ValueError("Use the same input image directory verified in Phase A")
    sparse_model = Path(prior["selected_sparse_model"]).resolve()
    if not sparse_model.is_relative_to(phase_a):
        raise ValueError("Selected sparse model must belong to the Phase A workspace")
    if not all((sparse_model / name).is_file() for name in ("cameras.bin", "images.bin", "points3D.bin")):
        raise ValueError("Phase A sparse binary model is incomplete")
    prior_commands = json.loads((phase_a / "sfm_commands.json").read_text(encoding="utf-8"))
    if (not isinstance(prior_commands, list) or not prior_commands
            or any(not isinstance(item, dict) or item.get("returncode") != 0
                   or not isinstance(item.get("command"), list) or len(item["command"]) < 2
                   for item in prior_commands)
            or not any(item["command"][1] == "bundle_adjuster" for item in prior_commands)):
        raise ValueError("Phase A must contain successful command and bundle-adjustment evidence")
    if root.exists() and any(root.iterdir()):
        raise ValueError("Phase B requires a fresh workspace; existing results are preserved")
    executable = colmap.find_colmap_executable()
    if executable is None:
        raise RuntimeError("COLMAP is unavailable; Phase B cannot run without it")
    root.mkdir(parents=True, exist_ok=True)
    report = {
        "phase": "B", "status": "FAILED", "source": "COLMAP_GEOMETRIC_MVS",
        "phase_a_workspace": str(phase_a), "input_images_directory": str(source),
        "coordinate_frame": "COLMAP_PHASE_A", "scale_status": "RELATIVE_UNCALIBRATED",
        "neural_depth_run": False, "procedural_fallback_run": False,
        "gaussian_optimization_run": False, "scene_published": False,
        "semantic_labeling_run": False, "ground_alignment_run": False,
        "thresholds": {"min_retained_points": min_points, "min_depth_support_views": 2,
                       "relative_depth_tolerance": 0.02},
    }
    report_path = root / "dense_quality_report.json"
    try:
        # Read the actual saved binary model rather than trusting a status string.
        source_txt = root / "phase_a_model_txt"
        source_txt.mkdir()
        colmap.run_logged_colmap([
            str(executable), "model_converter", "--input_path", str(sparse_model),
            "--output_path", str(source_txt), "--output_type", "TXT",
        ], root, "01_verify_phase_a_model")
        poses, cameras, points, errors = colmap.parse_colmap_reconstruction(source_txt)
        input_names = (phase_a / "input_images.txt").read_text(encoding="utf-8").splitlines()
        gate = colmap.evaluate_colmap_quality(poses, points, errors, len(input_names), input_names)
        report["phase_a_recheck"] = gate
        if gate["status"] != "PASSED" or set(poses) != set(prior["registered_image_names"]):
            raise ValueError("Saved Phase A binary geometry no longer passes its gate")
        fingerprints = {}
        for name in input_names:
            image_path = (source / name).resolve()
            if not image_path.is_relative_to(source) or not image_path.is_file():
                raise ValueError(f"Missing/invalid Phase A input image: {name}")
            fingerprints[name] = hashlib.sha256(image_path.read_bytes()).hexdigest()
            if name in poses:
                with Image.open(image_path) as image:
                    camera = cameras[poses[name]["camera_id"]]
                    if image.size != (camera["width"], camera["height"]):
                        raise ValueError(f"Input image dimensions differ from Phase A intrinsics: {name}")
        report["input_sha256"] = fingerprints

        dense = root / "dense"
        positions, colors, normals = colmap.run_colmap_mvs_dense(
            images_dir=source, sparse_model_dir=sparse_model, dense_workspace_dir=dense,
            colmap_bin=executable, max_image_size=max_image_size
        )
        undistorted_txt = root / "undistorted_sparse_txt"
        undistorted_txt.mkdir()
        colmap.run_logged_colmap([
            str(executable), "model_converter", "--input_path", str(dense / "sparse"),
            "--output_path", str(undistorted_txt), "--output_type", "TXT",
        ], root, "02_export_undistorted_cameras")
        dense_poses, dense_cameras, _, _ = colmap.parse_colmap_reconstruction(undistorted_txt)
        if set(dense_poses) != set(poses):
            raise ValueError("Undistorted camera set differs from the verified sparse model")
        for name in poses:
            if not (np.allclose(dense_poses[name]["R_cw"], poses[name]["R_cw"], atol=1e-6)
                    and np.allclose(dense_poses[name]["t_cw"], poses[name]["t_cw"], atol=1e-6)):
                raise ValueError("Dense camera coordinate frame changed unexpectedly")
        depths = {}
        for name in dense_poses:
            path = dense / "stereo/depth_maps" / f"{name}.geometric.bin"
            if not path.is_file():
                raise ValueError(f"Missing geometric depth map for {name}")
            depths[name] = read_colmap_depth(path)
        finite = np.isfinite(positions).all(axis=1) & np.isfinite(normals).all(axis=1)
        finite &= np.linalg.norm(normals, axis=1) > 1e-8
        support = np.zeros(len(positions), dtype=np.uint32)
        support[finite], consistency = measure_depth_support(
            positions[finite], dense_poses, dense_cameras, depths
        )
        keep = finite & (support >= 2)
        retained = int(keep.sum())
        np.save(root / "depth_support_counts.npy", support)
        checks = {
            "phase_a_revalidated": gate["status"] == "PASSED",
            "all_registered_geometric_depth_maps": len(depths) == len(poses),
            "all_views_have_valid_depth": all(view["valid_depth_pixels"] > 0 for view in consistency["per_view"].values()),
            "enough_multiview_surface_points": retained >= min_points,
        }
        report.update({
            "status": "PASSED" if all(checks.values()) else "FAILED",
            "checks": checks, "failed_checks": [key for key, passed in checks.items() if not passed],
            "registered_images": len(poses), "candidate_points": len(positions),
            "invalid_points_or_normals": int((~finite).sum()),
            "retained_points": retained, "rejected_points": int((~keep).sum()),
            "retained_fraction": retained / max(len(positions), 1),
            "minimum_retained_support_views": int(support[keep].min()) if retained else None,
            "median_retained_support_views": float(np.median(support[keep])) if retained else None,
            "depth_consistency": consistency,
            "max_image_size": max_image_size,
            "raw_fused_ply": str(dense / "fused.ply"),
            "undistorted_images": str(dense / "images"),
            "undistorted_sparse_txt": str(undistorted_txt),
        })
        if report["status"] == "PASSED":
            verified = root / "verified_dense.ply"
            write_dense_ply(verified, positions[keep], colors[keep], normals[keep])
            report["verified_dense_ply"] = str(verified)
            report["diagnostic_images"] = write_dense_previews(
                positions[keep], colors[keep], dense_poses, dense_cameras,
                dense / "images", root / "diagnostics"
            )
            report["bounds_relative"] = {"min": positions[keep].min(axis=0).tolist(), "max": positions[keep].max(axis=0).tolist()}
        report["elapsed_seconds"] = round(time.perf_counter() - started, 2)
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        summary = (f"PHASE B: {report['status']}\n"
                   f"Registered views: {len(poses)}\nFused candidates: {len(positions)}\n"
                   f"Retained multi-view points: {retained}\n"
                   "Geometry: COLMAP geometric MVS in unchanged Phase A frame\n"
                   "Scale: RELATIVE / UNCALIBRATED\n"
                   "Neural depth, procedural fallback, Gaussian training, scene publication: NOT RUN\n")
        (root / "validation_report.txt").write_text(summary, encoding="utf-8")
        print(summary, flush=True)
        return report
    except Exception as exc:
        report.update(status="FAILED", error=str(exc), elapsed_seconds=round(time.perf_counter() - started, 2))
        report_path.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
        raise
