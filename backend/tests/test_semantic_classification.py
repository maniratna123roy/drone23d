"""Numeric camera/evidence fixtures; real model results are recorded separately."""
import importlib

import numpy as np
from PIL import Image
import pytest

from pipeline import semantic_classification as sem
from pipeline import scene_publication as pub
from backend.tests.test_phase_d_publication import make_job


def camera():
    return {"model": "PINHOLE", "width": 8, "height": 8, "fx": 2., "fy": 2., "cx": 4., "cy": 4.}


def pose():
    return {"camera_id": 1, "R_cw": np.eye(3), "t_cw": np.zeros(3)}


def test_occlusion_behind_camera_and_unknown_do_not_invent_labels():
    points = np.array([[0, 0, 3], [0, 0, 5], [0, 0, -3], [30, 0, 3]])
    votes, visible = np.zeros((4, 4), np.uint32), np.zeros(4, np.uint32)
    mask = np.zeros((8, 8), np.uint8)
    for _ in range(2):
        sem.add_visible_votes(points, pose(), camera(), np.full((8, 8), 3.), mask, votes, visible)
    labels, _ = sem.consensus_labels(votes, visible)
    assert labels.tolist() == [0, 255, 255, 255]
    assert visible.tolist() == [2, 0, 0, 0]


def test_resized_depth_still_samples_original_mask_coordinates():
    points = np.array([[1.5, 0, 3]])
    votes, visible = np.zeros((1, 4), np.uint32), np.zeros(1, np.uint32)
    mask = np.full((8, 8), 255, np.uint8)
    mask[4, 5] = 3
    sem.add_visible_votes(points, pose(), camera(), np.full((4, 4), 3.), mask, votes, visible)
    assert votes.tolist() == [[0, 0, 0, 1]]


def test_unknown_views_count_against_consensus_and_ties_remain_unknown():
    votes = np.array([[2, 0, 0, 0], [2, 0, 0, 0], [2, 2, 0, 0], [0, 0, 1, 0], [0, 0, 0, 3]])
    labels, _ = sem.consensus_labels(votes, np.array([3, 4, 4, 1, 4]))
    assert labels.tolist() == [0, 255, 255, 255, 3]


@pytest.mark.parametrize("mask", [np.zeros((4, 4), np.uint8), np.full((8, 8), 4, np.uint8)])
def test_wrong_mask_dimensions_or_ids_rejected(mask):
    with pytest.raises(ValueError, match="mask"):
        sem.add_visible_votes(np.array([[0, 0, 3]]), pose(), camera(), np.ones((8, 8)), mask,
                              np.zeros((1, 4), np.uint32), np.zeros(1, np.uint32))


def test_low_confidence_and_unmapped_pixels_stay_unknown():
    import torch
    from types import SimpleNamespace

    class Inputs(dict):
        def to(self, _device):
            return self

    def processor(**kwargs):
        return Inputs()

    def model(**kwargs):
        logits = torch.zeros((1, 19, 1, 3))
        logits[0, 2, 0, 0] = 10  # confident building
        logits[0, 10, 0, 2] = 10  # confident sky
        return SimpleNamespace(logits=logits)

    result = sem.segment_image(Image.new("RGB", (3, 1)), model, processor)
    assert result.tolist() == [[0, 255, 255]]


@pytest.fixture
def classified_job(tmp_path, monkeypatch):
    root = make_job(tmp_path / "jobs")
    b = root / "phase_b"
    (b / "undistorted_sparse_txt").mkdir()
    for name in ("cameras.txt", "images.txt", "points3D.txt"):
        (b / "undistorted_sparse_txt" / name).write_text("numeric fixture")
    images = b / "dense/images"
    images.mkdir(parents=True)
    depths = b / "dense/stereo/depth_maps"
    depths.mkdir(parents=True)
    poses = {}
    for i in range(3):
        name = f"view{i}.png"
        poses[name] = pose()
        Image.new("RGB", (8, 8)).save(images / name)
        (depths / f"{name}.geometric.bin").write_bytes(b"8&8&1&" + np.full(64, 3., dtype="<f4").tobytes())
    monkeypatch.setattr("pipeline.colmap_reconstructor.parse_colmap_reconstruction", lambda _: (poses, {1: camera()}, [], []))
    monkeypatch.setattr(sem, "load_segmenter", lambda _: (None, None))
    monkeypatch.setattr(sem, "segment_image", lambda *args: np.zeros((8, 8), np.uint8))
    sem.classify_scene(root / "phase_c/assets/scene.splat", b, root / "semantics")
    return root


def test_classification_roundtrip_and_immutable_publication(classified_job, tmp_path):
    root = classified_job
    original = pub.sha256_file(root / "phase_c/assets/scene.splat")
    report = sem.validate_classification(root / "semantics", root / "phase_c/assets/scene.splat", root / "phase_b")
    assert report["class_counts"] == {"structure": 1, "terrain": 0, "road": 0, "vegetation": 0, "unknown": 1}
    result = pub.read_json(root / "result.json")
    for name in ("classification_report.json", "scene.classes.u8", "votes.npz"):
        result["artifact_sha256"][f"semantics/{name}"] = pub.sha256_file(root / "semantics" / name)
    pub.atomic_json(root / "result.json", result)
    manifest = pub.publish_verified_scene(root, tmp_path / "static", root.name, "unit.mp4")
    assert manifest["semantics"] == "CLASSIFIED_MULTIVIEW"
    assert manifest["capabilities"] == {"queries": False, "edits": False}
    assert manifest["sha256"]["scene.splat"] == original
    assert pub.read_current_scene(tmp_path / "static") == manifest


@pytest.mark.parametrize("relative", ["scene.classes.u8", "votes.npz", "masks/00000.png"])
def test_tampered_classification_rejected(classified_job, relative):
    root = classified_job
    path = root / "semantics" / relative
    path.write_bytes(path.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="evidence|masks"):
        sem.validate_classification(root / "semantics", root / "phase_c/assets/scene.splat", root / "phase_b")


def test_forged_labels_cannot_pass_by_updating_hash(classified_job):
    root = classified_job
    output = root / "semantics"
    (output / "scene.classes.u8").write_bytes(bytes([3, 3]))
    report = pub.read_json(output / "classification_report.json")
    report["classes_sha256"] = pub.sha256_file(output / "scene.classes.u8")
    pub.atomic_json(output / "classification_report.json", report)
    with pytest.raises(ValueError, match="votes"):
        sem.validate_classification(output, root / "phase_c/assets/scene.splat", root / "phase_b")


def test_classified_revision_keeps_previous_scene_and_source_bytes(classified_job, tmp_path):
    root = classified_job
    static = tmp_path / "static"
    previous = pub.publish_verified_scene(root, static, root.name, "unit.mp4")
    manifest = pub.publish_classified_revision(static, root / "semantics", root / "phase_b")
    assert manifest["source_job_id"] == previous["job_id"]
    assert manifest["job_id"] != previous["job_id"]
    assert manifest["sha256"]["scene.splat"] == previous["sha256"]["scene.splat"]
    assert pub.read_json(static / "scenes" / previous["job_id"] / "manifest.json") == previous
    assert pub.read_current_scene(static) == manifest


def test_legacy_labeler_never_trusts_same_length_labels_without_cameras(tmp_path):
    script = importlib.import_module("pipeline.04_label_splats")
    existing = tmp_path / "labels.npy"
    np.save(existing, np.zeros(2, np.uint8))
    with pytest.raises(ValueError, match="cameras"):
        script.label_splats_from_masks(output_labels_path=str(existing))
    assert np.load(existing).tolist() == [0, 0]


def test_missing_photographs_never_creates_synthetic_frames(tmp_path):
    script = importlib.import_module("pipeline.03_segment")
    with pytest.raises(ValueError, match="No camera images"):
        script.run_segmentation(str(tmp_path / "images"), str(tmp_path / "masks"), "cpu")
    assert not (tmp_path / "images").exists()


@pytest.mark.parametrize("fail", [False, True])
def test_upload_worker_requires_classification_before_result(classified_job, monkeypatch, fail):
    from pipeline.reconstruction_job import run_reconstruction

    root = classified_job
    (root / "result.json").unlink()
    pub.atomic_json(root / "request.json", {"input_file": "input.mp4", "max_frames": 5,
        "image_width": 640, "iterations": 600, "render_width": 320, "max_gaussians": 40000, "device": "cpu"})
    calls = []
    monkeypatch.setattr("pipeline.video_processor.extract_keyframes_from_video", lambda *args: {"extracted_frames_count": 3})
    monkeypatch.setattr("pipeline.colmap_reconstructor.stage_a_verify_colmap_geometry", lambda *args, **kwargs: {"status": "PASSED", "registered_images": 3})
    monkeypatch.setattr("pipeline.dense_reconstruction.stage_b_verify_dense_geometry", lambda *args, **kwargs: {"status": "PASSED", "retained_points": 2})
    monkeypatch.setattr("pipeline.gaussian_optimizer.execute_phase_c_3dgs_pipeline", lambda *args, **kwargs: {"status": "PASSED"})

    def classify(splat, phase_b, output, device):
        calls.append((splat, phase_b, output, device))
        if fail:
            raise ValueError("Classification failed")
        return pub.read_json(output / "classification_report.json")

    monkeypatch.setattr(sem, "classify_scene", classify)
    if fail:
        with pytest.raises(ValueError, match="Classification failed"):
            run_reconstruction(root / "request.json")
        assert not (root / "result.json").exists()
    else:
        result = run_reconstruction(root / "request.json")
        assert result["classification"]["structure"] == 1
        assert "semantics/votes.npz" in result["artifact_sha256"]
    assert calls == [(root / "phase_c/assets/scene.splat", root / "phase_b", root / "semantics", "cpu")]
