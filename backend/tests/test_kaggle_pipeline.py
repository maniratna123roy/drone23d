"""Cloud transport regressions; numerical fixtures never claim real drone quality."""
import ast
import base64
import io
from pathlib import Path
import sys
from types import SimpleNamespace
import zipfile

import numpy as np
import pytest

from pipeline import kaggle_runner as cloud
from pipeline import kaggle_worker_script as worker
from pipeline import scene_publication as pub


JOB_ID = "c" * 32
VIDEO_HASH = "d" * 64


def test_cloud_ships_exact_local_reconstruction_without_secrets():
    request = {"job_id": JOB_ID, "video_sha256": VIDEO_HASH, "source_name": "drone.mp4"}
    script = worker.build_worker_script(request)
    tree = ast.parse(script)
    payload = ast.literal_eval(tree.body[0].value)
    assert ast.literal_eval(tree.body[1].value) == request
    with zipfile.ZipFile(io.BytesIO(base64.b64decode(payload))) as archive:
        assert set(archive.namelist()) == set(worker.WORKER_FILES) | {"pipeline/__init__.py", "pipeline/common/__init__.py"}
        root = Path(worker.__file__).resolve().parent.parent
        for name in worker.WORKER_FILES:
            assert archive.read(name) == (root / name).read_bytes()
            compile(archive.read(name), name, "exec")
    compile(script, "train_splat.py", "exec")


def test_kernel_requires_upload_bound_ticket(tmp_path, monkeypatch):
    monkeypatch.setattr(cloud, "KAGGLE_KERNEL_DIR", tmp_path)
    with pytest.raises(ValueError, match="request"):
        cloud.prepare_kaggle_kernel_files("unit")


@pytest.mark.parametrize("gpu_available", [True, False])
def test_cloud_bootstrap_rejects_missing_gpu_or_wrong_video_before_reconstruction(tmp_path, monkeypatch, gpu_available):
    import torch
    from pipeline import reconstruction_job

    output, inputs = tmp_path / "working", tmp_path / "input"
    output.mkdir()
    inputs.mkdir()
    (inputs / "drone_footage.mp4").write_bytes(b"different video")
    namespace = {"__name__": "unit_worker"}
    exec(worker.build_worker_script({"video_sha256": VIDEO_HASH}), namespace)
    namespace["Path"] = lambda name: {"/kaggle/working": output, "/kaggle/input": inputs}.get(name, Path(name))
    namespace["command"] = lambda *args: None
    namespace["ensure_cuda_colmap"] = lambda *args: None
    monkeypatch.setattr(torch.cuda, "is_available", lambda: gpu_available)
    monkeypatch.setattr(reconstruction_job, "run_reconstruction", lambda *args: pytest.fail("invalid input must not reconstruct"))
    with pytest.raises((RuntimeError, ValueError), match="GPU|upload"):
        namespace["main"]()
    assert not (output / "published").exists()


@pytest.mark.parametrize("same_size", [True, False])
async def test_dataset_replaces_cached_video_and_removes_mismatched_sparse(tmp_path, monkeypatch, same_size):
    dataset = tmp_path / "dataset"
    dataset.mkdir()
    (dataset / "drone_footage.mp4").write_bytes(b"old" if same_size else b"old footage")
    sparse = dataset / "colmap_sparse/sparse_txt"
    sparse.mkdir(parents=True)
    (sparse / "cameras.txt").write_text("wrong cameras")
    source = tmp_path / "new.mp4"
    source.write_bytes(b"new")
    uploads = []
    api = SimpleNamespace(dataset_status=lambda _: "ready",
                          dataset_create_version=lambda *args, **kwargs: uploads.append(args))
    monkeypatch.setitem(sys.modules, "kaggle", SimpleNamespace(api=api))
    monkeypatch.setattr(cloud, "KAGGLE_DATASET_DIR", dataset)
    assert await cloud.upload_drone_video_to_kaggle_dataset(source, "unit") == "unit/spatial-twin-drone-data"
    assert (dataset / "drone_footage.mp4").read_bytes() == b"new"
    assert not (dataset / "colmap_sparse").exists()
    assert len(uploads) == 1


async def test_dataset_update_failure_cannot_reuse_prior_version(tmp_path, monkeypatch):
    source = tmp_path / "new.mp4"
    source.write_bytes(b"new")

    def fail(*args, **kwargs):
        raise RuntimeError("upload network failure")

    api = SimpleNamespace(dataset_status=lambda _: {"status": "ready"}, dataset_create_version=fail,
                          dataset_create_new=lambda *args, **kwargs: pytest.fail("not a missing dataset"))
    monkeypatch.setitem(sys.modules, "kaggle", SimpleNamespace(api=api))
    monkeypatch.setattr(cloud, "KAGGLE_DATASET_DIR", tmp_path / "dataset")
    with pytest.raises(RuntimeError, match="upload failed"):
        await cloud.upload_drone_video_to_kaggle_dataset(source, "unit")


@pytest.fixture
def cloud_bundle(tmp_path):
    output = tmp_path / "download"
    scene = output / "published/scenes" / JOB_ID
    scene.mkdir(parents=True)
    data = np.zeros(3, dtype=pub.SPLAT_DTYPE)
    data["xyz"][:, 2] = 3
    data["scales"] = 0.1
    data["rgba"] = 255
    data["q"] = [255, 128, 128, 128]
    data.tofile(scene / "scene.splat")
    np.array([0, 2, 255], np.uint8).tofile(scene / "scene.classes.u8")
    thresholds = {"pixel_confidence": 0.65, "min_views": 2, "min_agreement": 0.65, "relative_depth_tolerance": 0.02}
    manifest = {"schema_version": 1, "job_id": JOB_ID, "gaussian_count": 3,
                "coordinate_frame": "COLMAP_PHASE_A", "semantics": "CLASSIFIED_MULTIVIEW",
                "quality": {"phase_a": "PASSED", "phase_b": "PASSED", "phase_c": "PASSED",
                            "completed_steps": 600, "heldout": {"surface_ssim": 0.887}},
                "sha256": {name: pub.sha256_file(scene / name) for name in ("scene.splat", "scene.classes.u8")},
                "classification": {"method": "SEGFORMER_DEPTH_VISIBLE_MULTIVIEW", "thresholds": thresholds,
                                   "class_counts": {"structure": 1, "road": 1, "unknown": 1}}}
    report = {"splat_sha256": manifest["sha256"]["scene.splat"],
              "classes_sha256": manifest["sha256"]["scene.classes.u8"],
              "class_counts": manifest["classification"]["class_counts"]}
    pub.atomic_json(scene / "classification_report.json", report)
    manifest["sha256"]["classification_report.json"] = pub.sha256_file(scene / "classification_report.json")
    pub.atomic_json(scene / "manifest.json", manifest)
    pub.atomic_json(output / "published/current-scene.json", manifest)
    pub.atomic_json(output / "cloud_result.json", {"status": "PASSED", "job_id": JOB_ID,
                    "video_sha256": VIDEO_HASH, "manifest_sha256": pub.sha256_file(scene / "manifest.json")})
    return output


def test_publish_preserves_measured_quality_and_surface_counts(cloud_bundle, tmp_path):
    static = tmp_path / "static"
    static.mkdir()
    (static / "scene.splat").write_bytes(b"previous legacy scene")
    manifest = cloud.publish_kaggle_bundle(cloud_bundle, static, JOB_ID, VIDEO_HASH)
    assert pub.read_current_scene(static) == manifest
    assert manifest["gaussian_count"] == 3
    assert manifest["classification"]["class_counts"]["structure"] == 1
    assert manifest["quality"]["heldout"]["surface_ssim"] == 0.887
    assert (static / "scene.splat").read_bytes() == b"previous legacy scene"
    with pytest.raises(ValueError, match="immutable"):
        cloud.publish_kaggle_bundle(cloud_bundle, static, JOB_ID, VIDEO_HASH)


@pytest.mark.parametrize("fault", ["video", "job", "geometry", "labels", "classification", "legacy_gates"])
def test_bad_bundle_cannot_replace_previous_scene(cloud_bundle, tmp_path, fault):
    scene = cloud_bundle / "published/scenes" / JOB_ID
    expected_job, expected_hash = JOB_ID, VIDEO_HASH
    if fault == "video":
        expected_hash = "e" * 64
    elif fault == "job":
        expected_job = "e" * 32
    elif fault in {"geometry", "labels", "classification"}:
        name = {"geometry": "scene.splat", "labels": "scene.classes.u8", "classification": "classification_report.json"}[fault]
        (scene / name).write_bytes(b"corrupt")
    else:
        manifest = pub.read_json(scene / "manifest.json")
        manifest["classification"]["thresholds"] = {"min_votes": 2}
        pub.atomic_json(scene / "manifest.json", manifest)
        pub.atomic_json(cloud_bundle / "published/current-scene.json", manifest)
        result = pub.read_json(cloud_bundle / "cloud_result.json")
        result["manifest_sha256"] = pub.sha256_file(scene / "manifest.json")
        pub.atomic_json(cloud_bundle / "cloud_result.json", result)
    static = tmp_path / "static"
    pub.atomic_json(static / "current-scene.json", {"previous": "scene"})
    before = (static / "current-scene.json").read_bytes()
    with pytest.raises((ValueError, OSError)):
        cloud.publish_kaggle_bundle(cloud_bundle, static, expected_job, expected_hash)
    assert (static / "current-scene.json").read_bytes() == before


@pytest.mark.parametrize("status,error", [("running", TimeoutError), ("error", RuntimeError), ("cancelled", RuntimeError)])
async def test_poll_failures_do_not_download_stale_scene(tmp_path, monkeypatch, status, error):
    source = tmp_path / "input.mp4"
    source.write_bytes(b"video fixture")
    monkeypatch.setattr(cloud, "is_kaggle_configured", lambda: True)
    monkeypatch.setattr(cloud, "ensure_kaggle_auth", lambda: "unit")

    async def upload(*args):
        return "unit/dataset"

    async def no_sleep(*args):
        pass

    monkeypatch.setattr(cloud, "upload_drone_video_to_kaggle_dataset", upload)
    monkeypatch.setattr(cloud.asyncio, "sleep", no_sleep)
    monkeypatch.setattr(cloud, "prepare_kaggle_kernel_files", lambda *args: None)
    monkeypatch.setattr(cloud, "safe_kaggle_kernels_output", lambda *args: pytest.fail("failed workers must not download"))
    api = SimpleNamespace(kernels_push=lambda *args: None, kernels_status=lambda *args: {"status": status})
    monkeypatch.setitem(sys.modules, "kaggle", SimpleNamespace(api=api))
    with pytest.raises(error):
        await cloud.run_kaggle_3dgs_job(source, timeout_seconds=5)


async def test_kaggle_api_uses_verified_bundle_not_legacy_static(tmp_path, monkeypatch):
    from backend import pipeline_jobs as jobs
    from backend.config import settings
    from backend.routers import pipeline as api

    monkeypatch.setattr(settings, "PIPELINE_JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setattr(settings, "STATIC_ASSETS_DIR", str(tmp_path / "static"))
    job_id, source = jobs.create_job("fixture.mp4", ".mp4")
    source.write_bytes(b"video fixture")
    seen = []

    async def reconstruct(path, **kwargs):
        assert kwargs["request"]["job_id"] == job_id
        assert kwargs["output_dir"] == jobs.job_path(job_id) / "kaggle-output"
        return {"bundle_dir": str(kwargs["output_dir"]), "video_sha256": VIDEO_HASH}

    def publish(*args):
        seen.append(args)
        return {"job_id": job_id, "gaussian_count": 3}

    async def broadcast(*args):
        pass

    monkeypatch.setattr(cloud, "run_kaggle_3dgs_job", reconstruct)
    monkeypatch.setattr(cloud, "publish_kaggle_bundle", publish)
    monkeypatch.setattr(api.manager, "broadcast", broadcast)
    await api.run_kaggle_pipeline_task(job_id, source)
    assert jobs.get_state(job_id)["status"] == "completed"
    assert seen[0][2:] == (job_id, VIDEO_HASH)
    assert not (Path(settings.STATIC_ASSETS_DIR) / "scene.splat").exists()


def test_completed_kaggle_bundle_recovers_after_backend_shutdown(cloud_bundle, tmp_path, monkeypatch):
    from backend import pipeline_jobs as jobs
    from backend.config import settings
    import shutil

    monkeypatch.setattr(settings, "PIPELINE_JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setattr(settings, "STATIC_ASSETS_DIR", str(tmp_path / "static"))
    job_dir = jobs.job_path(JOB_ID)
    job_dir.mkdir(parents=True)
    pub.atomic_json(job_dir / "request.json", {"job_id": JOB_ID, "source_name": "drone.mp4"})
    shutil.copytree(cloud_bundle, job_dir / "kaggle-output")
    state = {"job_id": JOB_ID, "status": "error", "progress": 93,
             "step": "Reconstruction stopped", "details": {},
             "error": "Kaggle processing stopped during backend shutdown."}
    pub.atomic_json(job_dir / "status.json", state)
    assert jobs.recover_completed_kaggle_job(state) is True
    recovered = jobs.get_state(JOB_ID)
    assert recovered["status"] == "completed"
    assert recovered["details"]["scene_published"] is True
