"""Paint observed Gaussians from confident, depth-visible multi-camera labels.

Semantics never change geometry, imply metres, or enable database edits.
The pinned pretrained model runs on CPU so the local AI can keep its GPU.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import time

import numpy as np
from PIL import Image

from pipeline.dense_reconstruction import project_points, read_colmap_depth
from pipeline.scene_publication import SPLAT_DTYPE, atomic_json, read_json, sha256_file

MODEL = "nvidia/segformer-b0-finetuned-cityscapes-1024-1024"
REVISION = "21b3847fae21ddee674abd31129307b6a1235bd9"
CLASS_NAMES = {0: "structure", 1: "terrain", 2: "road", 3: "vegetation", 255: "unknown"}
CITYSCAPES_MAP = {0: 2, 1: 2, 2: 0, 3: 0, 4: 0, 8: 3, 9: 1}
PALETTE = np.zeros((256, 3), dtype=np.uint8)
PALETTE[[0, 1, 2, 3, 255]] = [[245, 158, 11], [168, 116, 72], [90, 160, 240], [40, 210, 100], [110, 110, 120]]


def load_segmenter(device="cpu"):
    import torch
    from transformers import SegformerForSemanticSegmentation, SegformerImageProcessor

    if device not in {"cpu", "cuda"}:
        raise ValueError("Classification device must be cpu or cuda")
    if device == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA classification requested but CUDA is unavailable; use cpu")
    if device == "cpu":
        torch.set_num_threads(min(4, torch.get_num_threads()))
    processor = SegformerImageProcessor.from_pretrained(MODEL, revision=REVISION)
    model = SegformerForSemanticSegmentation.from_pretrained(MODEL, revision=REVISION).to(device).eval()
    return model, processor


def segment_image(image, model, processor, device="cpu", min_confidence=0.65):
    import torch

    if not 0.5 <= min_confidence <= 1:
        raise ValueError("Pixel confidence must be between 0.5 and 1")
    inputs = processor(images=image, return_tensors="pt").to(device)
    with torch.inference_mode():
        logits = model(**inputs).logits
        logits = torch.nn.functional.interpolate(logits, size=(image.height, image.width), mode="bilinear", align_corners=False)
        confidence, predicted = logits.softmax(dim=1).max(dim=1)
        confidence = confidence[0].cpu().numpy()
        predicted = predicted[0].cpu().numpy()
    mask = np.full(predicted.shape, 255, dtype=np.uint8)
    for source, target in CITYSCAPES_MAP.items():
        mask[(predicted == source) & (confidence >= min_confidence)] = target
    return mask


def add_visible_votes(points, pose, camera, depth, mask, votes, visible, tolerance=0.02):
    """One vote per visible camera; sky/low-confidence votes remain UNKNOWN."""
    if not 0 < tolerance < 1:
        raise ValueError("Depth tolerance must be between zero and one")
    if mask.shape != (camera["height"], camera["width"]) or mask.dtype != np.uint8:
        raise ValueError("Semantic mask must match the undistorted camera dimensions")
    if not np.isin(mask, list(CLASS_NAMES)).all():
        raise ValueError("Semantic mask contains invalid class IDs")
    indices, u, v, z = project_points(points, pose, camera, depth.shape[1], depth.shape[0])
    measured = depth[v, u]
    supported = np.isfinite(measured) & (measured > 0) & (np.abs(measured - z) <= tolerance * z)
    indices = indices[supported]
    # Project independently at mask resolution (depth maps can be downsampled).
    selected, u, v, _ = project_points(points[indices], pose, camera, mask.shape[1], mask.shape[0])
    indices = indices[selected]
    labels = mask[v, u]
    visible[indices] += 1
    for class_id in range(4):
        votes[indices[labels == class_id], class_id] += 1
    return int(len(indices))


def consensus_labels(votes, visible, min_views=2, min_agreement=0.65):
    if min_views < 2 or not 0.5 < min_agreement <= 1:
        raise ValueError("Classification requires >=2 views and a strict majority")
    if (votes.ndim != 2 or votes.shape[1] != 4 or visible.shape != (len(votes),)
            or not np.isfinite(votes).all() or not np.isfinite(visible).all()
            or (votes < 0).any() or (visible < 0).any() or (votes.sum(axis=1) > visible).any()):
        raise ValueError("Invalid semantic vote evidence")
    winner = votes.argmax(axis=1)
    support = votes.max(axis=1)
    agreement = support / np.maximum(visible, 1)
    labels = np.full(len(votes), 255, dtype=np.uint8)
    accepted = (support >= min_views) & (agreement >= min_agreement)
    labels[accepted] = winner[accepted]
    return labels, agreement.astype(np.float32)


def classify_scene(splat_path: Path, phase_b: Path, output: Path, device="cpu") -> dict:
    """Fresh evidence directory, exact exported row order, no elevation fallback."""
    from pipeline.colmap_reconstructor import parse_colmap_reconstruction

    started = time.perf_counter()
    splat_path, phase_b, output = Path(splat_path).resolve(), Path(phase_b).resolve(), Path(output).resolve()
    report_b = read_json(phase_b / "dense_quality_report.json")
    if (report_b.get("status") != "PASSED" or report_b.get("source") != "COLMAP_GEOMETRIC_MVS"
            or report_b.get("coordinate_frame") != "COLMAP_PHASE_A"):
        raise ValueError("Classification needs passed geometric MVS in the original camera frame")
    if output.exists() and any(output.iterdir()):
        raise ValueError("Classification requires a fresh output directory; previous evidence is preserved")
    size = splat_path.stat().st_size
    if not size or size % 32 or size // 32 > 1_000_000:
        raise ValueError("Invalid Gaussian file size")
    data = np.fromfile(splat_path, dtype=SPLAT_DTYPE)
    points = data["xyz"]
    if not np.isfinite(points).all():
        raise ValueError("Classification requires finite Gaussian positions")
    poses, cameras, _, _ = parse_colmap_reconstruction(phase_b / "undistorted_sparse_txt")
    if len(poses) < 2:
        raise ValueError("Classification requires at least two registered camera views")
    source_hash = sha256_file(splat_path)
    output.mkdir(parents=True, exist_ok=True)
    masks = output / "masks"
    masks.mkdir()
    diagnostics = output / "diagnostics"
    diagnostics.mkdir()
    votes = np.zeros((len(points), 4), dtype=np.uint32)
    visible = np.zeros(len(points), dtype=np.uint32)
    model, processor = load_segmenter(device)
    fingerprints = {"dense_quality_report.json": sha256_file(phase_b / "dense_quality_report.json")}
    for name in ("cameras.txt", "images.txt", "points3D.txt"):
        relative = f"undistorted_sparse_txt/{name}"
        fingerprints[relative] = sha256_file(phase_b / relative)
    names = sorted(poses)
    per_view = {}
    for index, name in enumerate(names):
        image_path = (phase_b / "dense/images" / name).resolve()
        depth_path = (phase_b / "dense/stereo/depth_maps" / f"{name}.geometric.bin").resolve()
        if not image_path.is_relative_to(phase_b) or not depth_path.is_relative_to(phase_b):
            raise ValueError("Invalid camera image path")
        camera = cameras[poses[name]["camera_id"]]
        with Image.open(image_path) as image_file:
            image = image_file.convert("RGB")
        if image.size != (camera["width"], camera["height"]):
            raise ValueError(f"Image/camera size mismatch for {name}")
        mask = segment_image(image, model, processor, device)
        depth = read_colmap_depth(depth_path)
        supported = add_visible_votes(points, poses[name], camera, depth, mask, votes, visible)
        mask_path = masks / f"{index:05d}.png"
        Image.fromarray(mask).save(mask_path)
        per_view[name] = {"mask": f"masks/{mask_path.name}", "mask_sha256": sha256_file(mask_path), "visible_gaussians": supported}
        for path in (image_path, depth_path):
            fingerprints[path.relative_to(phase_b).as_posix()] = sha256_file(path)
        if index in {0, len(names) // 2, len(names) - 1}:
            rgb = np.asarray(image)
            overlay = (rgb * 0.45 + PALETTE[mask] * 0.55).astype(np.uint8)
            Image.fromarray(np.hstack([rgb, PALETTE[mask], overlay])).save(diagnostics / f"{index:05d}.png")
        print(f"[CLASSIFY] {index + 1}/{len(names)} {name}: {supported:,} depth-visible Gaussians", flush=True)
    del model, processor
    labels, agreement = consensus_labels(votes, visible)
    if not (labels != 255).any():
        raise ValueError("No classes met the two-view confidence gate. Inspect masks; previous scene is preserved")
    np.save(output / "labels.npy", labels)
    np.savez_compressed(output / "votes.npz", votes=votes, visible=visible, agreement=agreement)
    labels.tofile(output / "scene.classes.u8")
    if source_hash != sha256_file(splat_path):
        raise ValueError("Gaussian source changed during classification")
    report = {
        "status": "PASSED", "method": "SEGFORMER_DEPTH_VISIBLE_MULTIVIEW", "model": MODEL, "revision": REVISION,
        "device": device, "coordinate_frame": "COLMAP_PHASE_A", "gaussian_count": len(points),
        "splat_sha256": source_hash, "classes_sha256": sha256_file(output / "scene.classes.u8"),
        "votes_sha256": sha256_file(output / "votes.npz"), "phase_b_workspace": str(phase_b),
        "input_sha256": fingerprints, "per_view": per_view,
        "thresholds": {"pixel_confidence": 0.65, "min_views": 2, "min_agreement": 0.65, "relative_depth_tolerance": 0.02},
        "class_counts": {name: int((labels == key).sum()) for key, name in CLASS_NAMES.items()},
        "classified_fraction": float(np.mean(labels != 255)), "duration_seconds": round(time.perf_counter() - started, 2),
        "limitations": ["Pretrained Cityscapes predictions; not ground-truth accuracy or building instance counts.",
                        "Unknown includes occluded, unsupported, low-confidence and conflicting observations.",
                        "Classification does not calibrate scale, ground, or database objects."],
    }
    atomic_json(output / "classification_report.json", report)
    return report


def validate_classification(output: Path, splat_path: Path, phase_b: Path) -> dict:
    """Check source binding, all evidence hashes, and recompute the voting decision."""
    output, phase_b = Path(output), Path(phase_b).resolve()
    report = read_json(output / "classification_report.json")
    if (report.get("status") != "PASSED" or report.get("method") != "SEGFORMER_DEPTH_VISIBLE_MULTIVIEW"
            or report.get("model") != MODEL or report.get("revision") != REVISION
            or report.get("splat_sha256") != sha256_file(splat_path)
            or Path(report.get("phase_b_workspace", "")).resolve() != phase_b
            or report.get("classes_sha256") != sha256_file(output / "scene.classes.u8")
            or report.get("votes_sha256") != sha256_file(output / "votes.npz")):
        raise ValueError("Classification evidence does not match this scene")
    if report.get("thresholds") != {"pixel_confidence": 0.65, "min_views": 2, "min_agreement": 0.65, "relative_depth_tolerance": 0.02}:
        raise ValueError("Classification thresholds changed")
    fingerprints = report.get("input_sha256", {})
    if not fingerprints or len(report.get("per_view", {})) < 2:
        raise ValueError("Classification camera evidence is missing")
    for relative, digest in fingerprints.items():
        path = (phase_b / relative).resolve()
        if not path.is_relative_to(phase_b) or sha256_file(path) != digest:
            raise ValueError("Classification inputs changed")
    for view in report["per_view"].values():
        path = (output / view["mask"]).resolve()
        if not path.is_relative_to(output.resolve()) or sha256_file(path) != view["mask_sha256"]:
            raise ValueError("Classification masks changed")
    with np.load(output / "votes.npz", allow_pickle=False) as evidence:
        expected, _ = consensus_labels(evidence["votes"], evidence["visible"])
    labels = np.fromfile(output / "scene.classes.u8", dtype=np.uint8)
    count = Path(splat_path).stat().st_size // 32
    if (len(labels) != count or report.get("gaussian_count") != count
            or not np.array_equal(labels, expected) or not (labels != 255).any()
            or report.get("class_counts") != {name: int((labels == key).sum()) for key, name in CLASS_NAMES.items()}):
        raise ValueError("Classification labels/counts disagree with camera votes")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splat", type=Path, required=True)
    parser.add_argument("--phase-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--publish-current", type=Path, help="Publish labels only if this static directory still displays the same source")
    args = parser.parse_args()
    try:
        report = classify_scene(args.splat, args.phase_b, args.output, args.device)
        validate_classification(args.output, args.splat, args.phase_b)
        if args.publish_current:
            from pipeline.scene_publication import publish_classified_revision
            publish_classified_revision(args.publish_current, args.output, args.phase_b)
        print(report["class_counts"], flush=True)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"Classification stopped: {exc}\nPrevious scene is preserved. Inspect the classification inputs and retry in a fresh output directory.\n")


if __name__ == "__main__":
    main()
