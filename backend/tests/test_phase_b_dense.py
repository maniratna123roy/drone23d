"""Strict Phase B tests: generated data and mocked COLMAP; no footage/GPU jobs."""

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from plyfile import PlyData, PlyElement

from pipeline import colmap_reconstructor as colmap


def dense_module():
    return importlib.import_module("pipeline.dense_reconstruction")


def write_depth(path, depth):
    path.parent.mkdir(parents=True, exist_ok=True)
    height, width = depth.shape
    path.write_bytes(f"{width}&{height}&1&".encode() + np.asarray(depth.T, dtype="<f4").tobytes(order="F"))


def test_colmap_depth_reader_preserves_layout(tmp_path):
    values = np.arange(12, dtype=np.float32).reshape(3, 4)
    path = tmp_path / "depth.bin"
    write_depth(path, values)
    np.testing.assert_array_equal(dense_module().read_colmap_depth(path), values)


@pytest.mark.parametrize("payload", [b"missing header", b"2&2&1&\x00", b"0&2&1&", b"2&2&3&"])
def test_colmap_depth_reader_rejects_corruption(tmp_path, payload):
    path = tmp_path / "broken.bin"
    path.write_bytes(payload)
    with pytest.raises(ValueError):
        dense_module().read_colmap_depth(path)


def camera_fixture():
    poses = {
        f"frame_{i}.jpg": {"camera_id": "1", "R_cw": np.eye(3),
                            "t_cw": np.array([-float(i), 0., 0.]),
                            "t_w": np.array([float(i), 0., 0.])}
        for i in range(3)
    }
    cameras = {"1": {"model": "PINHOLE", "width": 100, "height": 100,
                       "fx": 50., "fy": 50., "cx": 50., "cy": 50.}}
    # Deliberately half-size depth maps; projection must scale intrinsics.
    depths = {name: np.full((50, 50), 10., dtype=np.float32) for name in poses}
    return poses, cameras, depths


def test_dense_support_uses_geometric_depth_and_rejects_unobserved_points():
    poses, cameras, depths = camera_fixture()
    points = np.array([[0., 0., 10.], [0., 0., 30.], [0., 0., -10.], [100., 0., 10.]])
    counts, stats = dense_module().measure_depth_support(points, poses, cameras, depths)
    assert counts.tolist() == [3, 0, 0, 0]
    assert stats["depth_tolerance_relative"] == 0.02
    assert stats["views_checked"] == 3


def test_dense_support_never_accepts_missing_or_invalid_depth():
    poses, cameras, depths = camera_fixture()
    points = np.array([[0., 0., 10.]])
    counts, _ = dense_module().measure_depth_support(points, poses, cameras, {})
    assert counts.tolist() == [0]
    for depth in depths.values():
        depth[:] = np.nan
    counts, _ = dense_module().measure_depth_support(points, poses, cameras, depths)
    assert counts.tolist() == [0]


def test_dense_support_rejects_distorted_camera_contract():
    poses, cameras, depths = camera_fixture()
    cameras["1"]["model"] = "OPENCV"
    with pytest.raises(ValueError, match="undistorted"):
        dense_module().measure_depth_support(np.array([[0., 0., 10.]]), poses, cameras, depths)


def write_cloud(path, *, normals=True):
    fields = [(name, "f4") for name in ("x", "y", "z")]
    if normals:
        fields += [(name, "f4") for name in ("nx", "ny", "nz")]
    fields += [(name, "u1") for name in ("red", "green", "blue")]
    data = np.zeros(2, dtype=fields)
    data["z"] = 10.
    data["red"] = 143
    if normals:
        data["nz"] = -1.
    PlyData([PlyElement.describe(data, "vertex")]).write(str(path))


def test_dense_ply_retains_observed_colors_and_normals(tmp_path):
    path = tmp_path / "fused.ply"
    write_cloud(path)
    positions, colors, normals = colmap.read_dense_ply(path)
    assert positions.shape == colors.shape == normals.shape == (2, 3)
    assert colors[:, 0].tolist() == [143, 143]
    np.testing.assert_array_equal(normals[:, 2], [-1., -1.])


def test_dense_ply_does_not_invent_missing_normals(tmp_path):
    path = tmp_path / "fused.ply"
    write_cloud(path, normals=False)
    with pytest.raises(ValueError, match="normal"):
        colmap.read_dense_ply(path)


@pytest.mark.parametrize("failed_stage", ["image_undistorter", "patch_match_stereo", "stereo_fusion"])
def test_dense_command_failure_is_fatal_and_logged(tmp_path, monkeypatch, failed_stage):
    calls = []

    def execute(command, **kwargs):
        calls.append(command[1])
        if command[1] == failed_stage:
            kwargs["stdout"].write("controlled failure\n")
        return SimpleNamespace(returncode=4 if command[1] == failed_stage else 0)

    monkeypatch.setattr(colmap.subprocess, "run", execute)
    with pytest.raises(RuntimeError, match=failed_stage):
        colmap.run_colmap_mvs_dense(tmp_path, tmp_path, tmp_path / "dense", Path("colmap"), 640)
    expected = ["image_undistorter", "patch_match_stereo", "stereo_fusion"]
    assert calls == expected[:expected.index(failed_stage) + 1]
    logs = sorted((tmp_path / "dense/logs").glob("*.log"))
    assert "controlled failure" in logs[-1].read_text()


def test_dense_runner_rejects_stale_output(tmp_path, monkeypatch):
    dense = tmp_path / "dense"
    dense.mkdir()
    (dense / "fused.ply").write_bytes(b"previous result")
    monkeypatch.setattr(colmap.subprocess, "run", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(ValueError, match="fresh"):
        colmap.run_colmap_mvs_dense(tmp_path, tmp_path, dense, Path("colmap"))
    assert (dense / "fused.ply").read_bytes() == b"previous result"


def test_phase_b_refuses_failed_phase_a_before_execution(tmp_path, monkeypatch):
    phase_a = tmp_path / "phase_a"
    phase_a.mkdir()
    (phase_a / "colmap_quality_report.json").write_text(json.dumps({"status": "FAILED"}))
    monkeypatch.setattr(colmap.subprocess, "run", lambda *a, **k: pytest.fail("failed Phase A must stop"))
    with pytest.raises(ValueError, match="Phase A"):
        dense_module().stage_b_verify_dense_geometry(tmp_path, phase_a, tmp_path / "phase_b")


@pytest.mark.parametrize("report", [[], {"status": "PASSED"}, {"status": "PASSED", "input_images_directory": 42}])
def test_phase_b_rejects_malformed_phase_a_metadata(tmp_path, report):
    phase_a = tmp_path / "phase_a"
    phase_a.mkdir()
    (phase_a / "colmap_quality_report.json").write_text(json.dumps(report))
    with pytest.raises(ValueError, match="Phase A"):
        dense_module().stage_b_verify_dense_geometry(tmp_path, phase_a, tmp_path / "phase_b")


def test_phase_b_cli_requires_phase_a_workspace(capsys):
    assert colmap.main(["--stage", "stage_b"]) == 1
    assert "--phase-a-workspace" in capsys.readouterr().err


@pytest.mark.parametrize("status,exit_code", [("PASSED", 0), ("FAILED", 1)])
def test_phase_b_cli_dispatches_only_strict_dense_path(monkeypatch, status, exit_code):
    monkeypatch.setattr(dense_module(), "stage_b_verify_dense_geometry", lambda **kw: {
        "status": status, "retained_points": 1234,
    })
    monkeypatch.setattr(colmap, "reconstruct_3d_with_colmap", lambda **kw: pytest.fail("legacy fallback path"))
    assert colmap.main(["--stage", "stage_b", "--phase-a-workspace", "previous-run"]) == exit_code


def test_filtered_ply_is_geometry_not_fabricated_gaussians(tmp_path):
    module = dense_module()
    points = np.array([[1., 2., 3.]], dtype=np.float32)
    colors = np.array([[123, 42, 2]], dtype=np.uint8)
    normals = np.array([[0., 0., 1.]], dtype=np.float32)
    path = tmp_path / "verified.ply"
    module.write_dense_ply(path, points, colors, normals)
    fields = PlyData.read(str(path))["vertex"].data.dtype.names
    assert set(fields) == {"x", "y", "z", "nx", "ny", "nz", "red", "green", "blue"}
    np.testing.assert_array_equal(colmap.read_dense_ply(path)[0], points)


@pytest.mark.parametrize("mode", ["valid", "few_points", "single_view", "nonfinite", "missing_depth", "command_failure"])
def test_phase_b_flow_reports_measured_result_without_fallback(tmp_path, monkeypatch, mode):
    from PIL import Image
    import shutil

    module = dense_module()
    images = tmp_path / "images"
    images.mkdir()
    phase_a = tmp_path / "phase_a"
    model = phase_a / "sparse/0"
    model.mkdir(parents=True)
    for name in ("cameras.bin", "images.bin", "points3D.bin"):
        (model / name).touch()
    names = [f"frame_{i}.jpg" for i in range(3)]
    for name in names:
        Image.new("RGB", (64, 48), (120, 90, 60)).save(images / name)
    (phase_a / "colmap_quality_report.json").write_text(json.dumps({
        "status": "PASSED", "input_images_directory": str(images),
        "selected_sparse_model": str(model), "registered_image_names": names,
    }))
    (phase_a / "input_images.txt").write_text("\n".join(names))
    (phase_a / "sfm_commands.json").write_text(json.dumps([
        {"command": ["colmap", "bundle_adjuster"], "returncode": 0}
    ]))
    ties = {i: np.array([i * 0.001, 0., 10.]) for i in range(100)}
    poses = {name: {"camera_id": "1", "R_cw": np.eye(3),
                    "t_cw": np.array([-0.2 * i, 0., 0.]),
                    "t_w": np.array([0.2 * i, 0., 0.]), "obs_point3D_ids": list(ties)}
             for i, name in enumerate(names)}
    cameras = {"1": {"model": "PINHOLE", "width": 64, "height": 48,
                       "fx": 50., "fy": 50., "cx": 32., "cy": 24.}}
    monkeypatch.setattr(colmap, "find_colmap_executable", lambda: Path("colmap"))
    monkeypatch.setattr(colmap, "parse_colmap_reconstruction", lambda path: (poses, cameras, ties, [0.2] * 100))
    monkeypatch.setattr(colmap, "run_logged_colmap", lambda *a, **kw: None)
    monkeypatch.setattr(colmap, "get_depth_pipeline", lambda: pytest.fail("no neural fallback"))
    count = 100 if mode == "few_points" else 600
    points = np.column_stack((np.linspace(-0.4, 0.4, count), np.zeros(count), np.full(count, 10.))).astype(np.float32)
    if mode == "nonfinite":
        points[:, 2] = np.nan
    colors = np.full((count, 3), 120, dtype=np.uint8)
    normals = np.tile([0., 0., -1.], (count, 1)).astype(np.float32)

    def native_mvs(**kwargs):
        if mode == "command_failure":
            raise RuntimeError("controlled PatchMatch failure")
        dense = kwargs["dense_workspace_dir"]
        (dense / "images").mkdir(parents=True)
        for i, name in enumerate(names):
            shutil.copyfile(images / name, dense / "images" / name)
            if mode == "missing_depth" and i == 2:
                continue
            depth = 20. if mode == "single_view" and i > 0 else 10.
            write_depth(dense / "stereo/depth_maps" / f"{name}.geometric.bin", np.full((48, 64), depth))
        return points, colors, normals

    monkeypatch.setattr(colmap, "run_colmap_mvs_dense", native_mvs)
    root = tmp_path / "phase_b"
    if mode in {"missing_depth", "command_failure"}:
        with pytest.raises((ValueError, RuntimeError)):
            module.stage_b_verify_dense_geometry(images, phase_a, root)
    else:
        module.stage_b_verify_dense_geometry(images, phase_a, root)
    report = json.loads((root / "dense_quality_report.json").read_text())
    assert report["status"] == ("PASSED" if mode == "valid" else "FAILED")
    assert report["neural_depth_run"] is False
    assert report["procedural_fallback_run"] is False
    assert report["scene_published"] is False
    if mode == "valid":
        assert report["retained_points"] == 600
        assert report["minimum_retained_support_views"] == 3
        np.testing.assert_array_equal(colmap.read_dense_ply(root / "verified_dense.ply")[0], points)
        assert len(report["diagnostic_images"]) == 3
    else:
        assert not (root / "verified_dense.ply").exists()
