"""Phase A regression tests. No real footage, models, GPU jobs or database writes."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from pipeline import colmap_reconstructor as colmap


def sparse_fixture():
    points = {i: np.array([i * 0.01, 0.0, 10.0]) for i in range(100)}
    poses = {
        f"frame_{i:05d}.jpg": {
            "t_w": np.array([float(i), 0.0, 0.0]),
            "obs_point3D_ids": list(points),
        }
        for i in range(4)
    }
    return poses, points, [0.25] * 100


def test_quality_pass_includes_observed_tracks_and_relative_scale():
    poses, points, errors = sparse_fixture()
    report = colmap.evaluate_colmap_quality(poses, points, errors, 4, sorted(poses))
    assert report["status"] == "PASSED"
    assert report["failed_checks"] == []
    assert report["multi_view_points"] == 100
    assert report["median_track_length"] == 4
    assert report["scale_status"] == "RELATIVE_UNCALIBRATED"
    assert report["median_triangulation_angle_deg"] > 0
    assert "trajectory_max_step_m" not in report
    json.dumps(report, allow_nan=False)


@pytest.mark.parametrize("case", [
    "missing_errors", "nan_error", "negative_error", "missing_tracks",
    "stationary", "nonfinite_pose", "nonfinite_point", "few_points",
    "low_registration", "high_error", "trajectory_jump",
])
def test_quality_gate_fails_closed(case):
    poses, points, errors = sparse_fixture()
    total = 4
    if case == "missing_errors":
        errors = []
    elif case == "nan_error":
        errors[0] = float("nan")
    elif case == "negative_error":
        errors[0] = -1.0
    elif case == "missing_tracks":
        for pose in poses.values():
            pose.pop("obs_point3D_ids")
    elif case == "stationary":
        for pose in poses.values():
            pose["t_w"] = np.zeros(3)
    elif case == "nonfinite_pose":
        poses["frame_00000.jpg"]["t_w"][0] = float("nan")
    elif case == "nonfinite_point":
        points[0][0] = float("inf")
    elif case == "few_points":
        points = {0: points[0]}
        errors = [0.25]
    elif case == "low_registration":
        total = 20
    elif case == "high_error":
        errors = [4.0] * 100
    elif case == "trajectory_jump":
        poses["frame_00003.jpg"]["t_w"][0] = 100.0
    report = colmap.evaluate_colmap_quality(poses, points, errors, total, sorted(poses))
    assert report["status"] == "FAILED"
    assert report["failed_checks"]
    json.dumps(report, allow_nan=False)


def test_parser_keeps_empty_observation_lines_and_names_with_spaces(tmp_path):
    (tmp_path / "cameras.txt").write_text("1 PINHOLE 640 360 500 500 320 180\n")
    (tmp_path / "points3D.txt").write_text("10 0 0 10 255 255 255 0.2 2 0\n")
    (tmp_path / "images.txt").write_text(
        "# header\n1 1 0 0 0 0 0 0 1 frame empty.jpg\n\n"
        "2 1 0 0 0 -1 0 0 1 frame_00001.jpg\n320 180 10\n"
    )
    poses, _, points, errors = colmap.parse_colmap_reconstruction(tmp_path)
    assert len(poses) == 2
    assert poses["frame empty.jpg"]["obs_uv"].shape == (0, 2)
    assert poses["frame_00001.jpg"]["obs_point3D_ids"] == [10]
    assert len(points) == len(errors) == 1


def test_sfm_checks_command_failure_and_retains_log(tmp_path, monkeypatch):
    images = tmp_path / "images"
    images.mkdir()
    (images / "frame_00000.jpg").touch()
    (images / "frame_00001.jpg").touch()
    calls = []

    def fail_command(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=7, stdout="", stderr="SIFT device unavailable")

    monkeypatch.setattr(colmap.subprocess, "run", fail_command)
    monkeypatch.setattr(colmap.torch.cuda, "is_available", lambda: False)
    workspace = tmp_path / "run"
    with pytest.raises(RuntimeError, match="feature_extractor.*7"):
        colmap.run_colmap_sfm(images, workspace, Path("colmap"))
    assert len(calls) == 1  # Never match/map after failed extraction.
    assert "SIFT device unavailable" in (workspace / "logs/01_feature_extractor.log").read_text()


def test_sfm_refuses_stale_workspace_without_deleting_it(tmp_path, monkeypatch):
    images = tmp_path / "images"
    images.mkdir()
    (images / "frame_00000.jpg").touch()
    (images / "frame_00001.jpg").touch()
    workspace = tmp_path / "run"
    workspace.mkdir()
    old_database = workspace / "database.db"
    old_database.write_bytes(b"existing reconstruction")
    monkeypatch.setattr(colmap.subprocess, "run", lambda *a, **k: pytest.fail("must not execute"))
    with pytest.raises(ValueError, match="fresh workspace"):
        colmap.run_colmap_sfm(images, workspace, Path("colmap"))
    assert old_database.read_bytes() == b"existing reconstruction"


def test_sfm_selects_largest_component_and_runs_bundle_adjustment(tmp_path, monkeypatch):
    images = tmp_path / "images"
    images.mkdir()
    (images / "frame_00000.jpg").touch()
    (images / "frame_00001.jpg").touch()
    workspace = tmp_path / "run"
    calls = []

    def run_command(command, **kwargs):
        calls.append(command)
        if command[1] == "mapper":
            for name in ("0", "1"):
                model = workspace / "sparse" / name
                model.mkdir()
                (model / "images.bin").touch()
        if command[1] == "model_converter" and command[-1] == "PLY":
            Path(command[command.index("--output_path") + 1]).write_bytes(b"ply\n")
        return SimpleNamespace(returncode=0, stdout="successful stage", stderr="")

    def parse_model(path):
        count = 3 if path.name == "0" else 4
        return {str(i): {} for i in range(count)}, {}, {0: np.zeros(3)}, [0.25]

    monkeypatch.setattr(colmap.subprocess, "run", run_command)
    monkeypatch.setattr(colmap, "parse_colmap_reconstruction", parse_model)
    monkeypatch.setattr(colmap.torch.cuda, "is_available", lambda: False)
    *_, selected = colmap.run_colmap_sfm(images, workspace, Path("colmap"))
    assert selected.name == "1"
    assert [cmd[1] for cmd in calls].count("bundle_adjuster") == 1
    bundle_cmd = next(cmd for cmd in calls if cmd[1] == "bundle_adjuster")
    assert Path(bundle_cmd[bundle_cmd.index("--input_path") + 1]) == selected
    manifest = json.loads((workspace / "sfm_commands.json").read_text())
    assert len(manifest) == len(calls)
    assert all(item["returncode"] == 0 for item in manifest)


def test_failed_phase_a_blocks_dense_entrypoint(tmp_path, monkeypatch):
    images = tmp_path / "images"
    images.mkdir()
    poses, points, _ = sparse_fixture()
    for name in poses:
        (images / name).touch()
    monkeypatch.setattr(colmap, "run_colmap_sfm", lambda **kwargs: (
        poses, {}, points, [], tmp_path / "sparse.ply", tmp_path / "sparse/0"
    ))
    monkeypatch.setattr(colmap, "get_depth_pipeline", lambda: pytest.fail("no neural fallback"))
    monkeypatch.setattr(colmap, "run_colmap_mvs_dense", lambda **kw: pytest.fail("failed gate must stop MVS"))
    with pytest.raises(RuntimeError, match="Phase A quality gate failed"):
        colmap.reconstruct_3d_with_colmap(images_dir=images, output_ply=tmp_path / "out/scene.ply")


def test_video_extractor_preserves_aspect_ratio(tmp_path, monkeypatch):
    # Tiny generated frames, not a private video or GPU reconstruction.
    from PIL import Image
    from pipeline import video_processor

    source = tmp_path / "fixture.mp4"
    from contextlib import nullcontext
    source.write_bytes(b"unit frame-decoder fixture")
    stream = SimpleNamespace(type="video", frames=60, average_rate=30,
                             duration=60, time_base=1 / 30, width=160, height=90)
    frames = [SimpleNamespace(time=i / 30, width=160, height=90,
                              to_image=lambda: Image.new("RGB", (160, 90))) for i in range(60)]
    container = SimpleNamespace(streams=SimpleNamespace(video=[stream]), decode=lambda *args: iter(frames))
    monkeypatch.setattr(video_processor.av, "open", lambda *a: nullcontext(container))
    result = video_processor.extract_keyframes_from_video(source, tmp_path / "frames", max_frames=24, target_width=96)
    assert result["extracted_frames_count"] == 24
    for path in result["frames"]:
        with Image.open(path) as image:
            assert image.size == (96, 54)


def test_phase_a_exports_failure_report_without_dense_work(tmp_path, monkeypatch):
    images = tmp_path / "images"
    images.mkdir()
    poses, points, _ = sparse_fixture()
    for name in poses:
        (images / name).touch()
    workspace = tmp_path / "run"
    monkeypatch.setattr(colmap, "run_colmap_sfm", lambda **kwargs: (
        poses, {}, points, [], workspace / "sparse_cloud.ply", workspace / "sparse/0"
    ))
    monkeypatch.setattr(colmap, "get_depth_pipeline", lambda: pytest.fail("no depth in Phase A"))
    monkeypatch.setattr(colmap, "run_colmap_mvs_dense", lambda **kw: pytest.fail("no MVS in Phase A"))
    result = colmap.stage_a_verify_colmap_geometry(images, workspace)
    assert result["status"] == "FAILED"
    report = json.loads((workspace / "colmap_quality_report.json").read_text())
    assert report["status"] == "FAILED"
    assert "NOT RUN" in result["validation_report"]
    assert "Cross-View Consistency:   PASSED" not in result["validation_report"]
    assert (workspace / "validation_report.txt").is_file()
    assert (workspace / "trajectory.png").is_file()


@pytest.mark.parametrize("status,expected_exit", [("PASSED", 0), ("FAILED", 1)])
def test_stage_a_cli_dispatch_and_exit_status(monkeypatch, status, expected_exit):
    monkeypatch.setattr(colmap, "stage_a_verify_colmap_geometry", lambda **kwargs: {
        "status": status, "registered_images": 4,
    })
    monkeypatch.setattr(colmap, "reconstruct_3d_with_colmap", lambda **kw: pytest.fail("no Stage B"))
    assert colmap.main(["--stage", "stage_a", "--images", "frames", "--workspace", "run"]) == expected_exit


def test_stage_a_cli_has_friendly_execution_error(monkeypatch, capsys):
    def fail(**kwargs):
        raise RuntimeError("COLMAP mapper did not produce a model")
    monkeypatch.setattr(colmap, "stage_a_verify_colmap_geometry", fail)
    assert colmap.main(["--stage", "stage_a"]) == 1
    assert "COLMAP mapper did not produce a model" in capsys.readouterr().err
