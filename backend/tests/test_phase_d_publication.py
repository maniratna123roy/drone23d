"""Numerical/control-flow fixtures only; no reconstructed scene is fabricated.

All writes live in pytest's temporary directory. Real-video evidence is recorded
separately by the native A/B/C worker and the browser acceptance run.
"""
from pathlib import Path
import shutil

import numpy as np
import pytest

from pipeline import scene_publication as pub


ARTIFACTS = ("phase_a/colmap_quality_report.json", "phase_b/dense_quality_report.json",
             "phase_c/phase_c_report.json", "phase_c/model.pt", "phase_c/assets/scene.splat",
             "phase_c/assets/scene.classes.u8")


def update_hashes(root):
    pub.atomic_json(root / "result.json", {"status": "PASSED", "video_sha256": pub.sha256_file(root / "input.mp4"),
        "artifact_sha256": {name: pub.sha256_file(root / name) for name in ARTIFACTS}})


def make_job(parent, job_id="a" * 32):
    root = parent / job_id
    root.mkdir(parents=True)
    (root / "input.mp4").write_bytes(b"unit fixture, not real footage")
    pub.atomic_json(root / "request.json", {"job_id": job_id, "source_name": "unit.mp4", "input_file": "input.mp4"})
    pub.atomic_json(root / "phase_a/colmap_quality_report.json", {"status": "PASSED"})
    pub.atomic_json(root / "phase_b/dense_quality_report.json", {
        "status": "PASSED", "source": "COLMAP_GEOMETRIC_MVS", "coordinate_frame": "COLMAP_PHASE_A",
        "phase_a_workspace": str((root / "phase_a").resolve()), "registered_images": 5, "retained_points": 2,
    })
    (root / "phase_b/verified_dense.ply").write_bytes(b"unit cloud fingerprint fixture")
    pub.atomic_json(root / "phase_c/phase_c_report.json", {
        "status": "PASSED", "phase_b_workspace": str((root / "phase_b").resolve()),
        "coordinate_frame": "COLMAP_PHASE_A", "checkpoint_roundtrip_exact": True,
        "quality_gate": {"status": "PASSED", "checks": {"unit_check": True}},
        "export_roundtrip": {"passed": True, "psnr_delta_db": .001},
        "input_sha256": {"verified_dense.ply": pub.sha256_file(root / "phase_b/verified_dense.ply")},
        "final_gaussians": 2, "completed_steps": 300,
        "final": {"heldout": {"surface_psnr_db": 23.}}, "validation_scope": "unit test; not scene evidence",
    })
    assets = root / "phase_c/assets"
    assets.mkdir()
    (root / "phase_c/model.pt").write_bytes(b"unit checkpoint fingerprint fixture")
    data = np.zeros(2, dtype=pub.SPLAT_DTYPE)
    data["xyz"] = [[0, 0, 3], [1, 0, 4]]
    data["scales"] = [.03, .02, .01]
    data["rgba"] = [12, 34, 56, 100]
    data["q"] = [255, 128, 128, 128]
    data.tofile(assets / "scene.splat")
    (assets / "scene.classes.u8").write_bytes(bytes([255, 255]))
    update_hashes(root)
    return root


@pytest.fixture

def job(tmp_path, monkeypatch):
    monkeypatch.setattr(pub, "camera_for_scene", lambda *args: {
        "position": [0, 0, 0], "target": [0, 0, 3], "up": [0, -1, 0],
        "fov_y_degrees": 40., "near": .001, "far": 50.,
    })
    return make_job(tmp_path / "jobs")


def publish(job, destination):
    return pub.publish_verified_scene(job, destination, job.name, "unit.mp4")


def test_atomic_versioned_publication_preserves_legacy_files(job, tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "scene.splat").write_bytes(b"unrelated legacy scene")
    manifest = publish(job, static)
    assert manifest["gaussian_count"] == 2
    assert manifest["semantics"] == "UNKNOWN"
    assert manifest["scale_status"] == "RELATIVE_UNCALIBRATED"
    assert manifest["capabilities"] == {"queries": False, "edits": False}
    assert pub.read_current_scene(static) == manifest
    assert (static / "scene.splat").read_bytes() == b"unrelated legacy scene"
    assert (static / "scenes" / job.name / "scene.splat").read_bytes() == (job / "phase_c/assets/scene.splat").read_bytes()
    with pytest.raises(ValueError, match="immutable"):
        publish(job, static)


@pytest.mark.parametrize("phase,filename", [("phase_a", "colmap_quality_report.json"),
    ("phase_b", "dense_quality_report.json"), ("phase_c", "phase_c_report.json")])

def test_any_failed_stage_blocks_publication(job, tmp_path, phase, filename):
    path = job / phase / filename
    report = pub.read_json(path)
    report["status"] = "FAILED"
    pub.atomic_json(path, report)
    update_hashes(job)
    with pytest.raises(ValueError, match="Every reconstruction stage"):
        publish(job, tmp_path / "static")
    assert not (tmp_path / "static/current-scene.json").exists()


@pytest.mark.parametrize("change", ["input", "checkpoint", "export", "report"])

def test_changed_verified_artifact_rejected(job, tmp_path, change):
    path = {"input": "input.mp4", "checkpoint": "phase_c/model.pt", "export": "phase_c/assets/scene.splat",
            "report": "phase_c/phase_c_report.json"}[change]
    with (job / path).open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="upload|artifacts changed"):
        publish(job, tmp_path / "static")


@pytest.mark.parametrize("change", ["foreign_workspace", "procedural", "frame", "checkpoint_gate", "export_gate", "parameter_gate", "dense_input"])

def test_provenance_and_quality_fail_closed(job, tmp_path, change):
    path = job / "phase_c/phase_c_report.json"
    report = pub.read_json(path)
    if change == "foreign_workspace":
        report["phase_b_workspace"] = str(tmp_path)
    elif change == "procedural":
        report["procedural_fallback_run"] = True
    elif change == "frame":
        report["coordinate_frame"] = "guessed_metres"
    elif change == "checkpoint_gate":
        report["checkpoint_roundtrip_exact"] = False
    elif change == "export_gate":
        report["export_roundtrip"]["passed"] = False
    elif change == "parameter_gate":
        report["quality_gate"]["checks"]["unit_check"] = False
    else:
        (job / "phase_b/verified_dense.ply").write_bytes(b"changed dense source")
    pub.atomic_json(path, report)
    update_hashes(job)
    with pytest.raises(ValueError):
        publish(job, tmp_path / "static")


@pytest.mark.parametrize("change", ["short_splat", "short_classes", "false_labels", "nan", "negative_scale", "zero_rotation", "zero_alpha"])

def test_invalid_binary_never_publishes(job, tmp_path, change):
    path = job / "phase_c/assets/scene.splat"
    sidecar = job / "phase_c/assets/scene.classes.u8"
    data = np.fromfile(path, dtype=pub.SPLAT_DTYPE)
    if change == "short_splat":
        path.write_bytes(path.read_bytes()[:-1])
    elif change == "short_classes":
        sidecar.write_bytes(b"\xff")
    elif change == "false_labels":
        sidecar.write_bytes(b"\0\0")
    else:
        if change == "nan":
            data["xyz"][0, 0] = np.nan
        elif change == "negative_scale":
            data["scales"][0, 0] = -1
        elif change == "zero_rotation":
            data["q"][:] = 128
        elif change == "zero_alpha":
            data["rgba"][:, 3] = 0
        data.tofile(path)
    update_hashes(job)
    with pytest.raises(ValueError):
        publish(job, tmp_path / "static")


def test_failed_commit_preserves_previous_manifest(job, tmp_path, monkeypatch):
    static = tmp_path / "static"
    first = publish(job, static)
    second = make_job(tmp_path / "jobs", "b" * 32)
    original_write = pub.atomic_json

    def fail_pointer(path, value):
        if path.name == "current-scene.json":
            raise OSError("simulated disk failure at commit")
        original_write(path, value)

    monkeypatch.setattr(pub, "atomic_json", fail_pointer)
    with pytest.raises(OSError):
        publish(second, static)
    assert pub.read_current_scene(static) == first
    assert not list((static / "scenes").glob("*.staging"))


def test_changed_published_bytes_detected(job, tmp_path):
    static = tmp_path / "static"
    publish(job, static)
    path = static / "scenes" / job.name / "scene.splat"
    content = bytearray(path.read_bytes())
    content[24] ^= 1
    path.write_bytes(content)
    with pytest.raises(ValueError, match="changed"):
        pub.read_current_scene(static)


def test_metadata_pair_mismatch_is_not_accepted(job, tmp_path):
    static = tmp_path / "static"
    manifest = publish(job, static)
    manifest["source_name"] = "unrelated video"
    pub.atomic_json(static / "current-scene.json", manifest)
    with pytest.raises(ValueError, match="inconsistent"):
        pub.read_current_scene(static)
