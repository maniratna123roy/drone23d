"""Isolated API regressions. Worker doubles test control flow, NEVER real scene quality.

Unlike the historical tests these do not start GPU work, touch live static files,
or mutate a database. The separate real-video/browser run proves reconstruction.
"""
import asyncio
from pathlib import Path

import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.config import settings
from backend import pipeline_jobs as jobs
from backend.routers import pipeline as api
from pipeline.scene_publication import atomic_json


@pytest.fixture(autouse=True)
async def isolated_jobs(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PIPELINE_JOBS_DIR", str(tmp_path / "jobs"))
    monkeypatch.setattr(settings, "STATIC_ASSETS_DIR", str(tmp_path / "static"))
    monkeypatch.setattr(jobs, "active_tasks", set())
    monkeypatch.setattr(jobs, "upload_lock", asyncio.Lock())
    yield
    await jobs.shutdown()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as connection:
        yield connection


async def test_pipeline_status_idle(client):
    response = await client.get("/api/pipeline/status")
    assert response.status_code == 200
    assert response.json()["status"] == "idle"
    assert (await client.get("/api/pipeline/scene")).json() == {"status": "empty", "manifest": None}


async def test_no_manifest_never_loads_legacy_scene(client):
    root = Path(settings.STATIC_ASSETS_DIR)
    root.mkdir()
    (root / "scene.splat").write_bytes(b"legacy-not-verified")
    (root / "scene.classes.u8").write_bytes(b"\0")
    assert (await client.get("/api/pipeline/scene")).json()["status"] == "empty"


@pytest.mark.parametrize("filename,payload,code", [("test.txt", b"text", 400), ("test.mp4", b"", 400)])
async def test_invalid_upload_is_rejected(client, filename, payload, code):
    response = await client.post("/api/pipeline/upload", files={"file": (filename, payload)})
    assert response.status_code == code
    assert not jobs.active_tasks
    assert not list(jobs.root().glob("*/input.*"))


async def test_oversized_upload_is_removed(client, monkeypatch):
    monkeypatch.setattr(settings, "PIPELINE_MAX_UPLOAD_MB", 1)
    response = await client.post("/api/pipeline/upload", files={"file": ("too_big.mp4", b"x" * (1024 * 1024 + 1))})
    assert response.status_code == 413
    assert not list(jobs.root().glob("*/input.*"))
    assert not jobs.active_tasks


async def test_large_declared_body_rejected_before_job_or_multipart_parsing(client, monkeypatch):
    monkeypatch.setattr(settings, "PIPELINE_MAX_UPLOAD_MB", 1)
    response = await client.post("/api/pipeline/upload", content=b"small body", headers={"content-length": str(4 * 1024 * 1024)})
    assert response.status_code == 413
    assert not jobs.root().exists()


async def test_single_backend_owner_lock():
    jobs.acquire_worker_lock()
    with pytest.raises(RuntimeError, match="Another backend"):
        jobs.acquire_worker_lock()


async def test_upload_ticket_status_responsive_and_concurrent_upload_rejected(client, monkeypatch):
    entered, release = asyncio.Event(), asyncio.Event()

    async def worker(path, progress_callback, **kwargs):
        entered.set()
        progress_callback("Unit worker running", 30, {})
        await release.wait()
        raise RuntimeError("test gate failure; no substitute")

    monkeypatch.setattr(api, "execute_drone_video_pipeline", worker)
    response = await client.post("/api/pipeline/upload", files={"file": ("../../outside.mp4", b"unit fixture, not a video")})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    await asyncio.wait_for(entered.wait(), 2)
    directory = jobs.job_path(job_id)
    assert (directory / "input.mp4").is_file()
    assert jobs.get_state(job_id)["details"]["filename"] == "outside.mp4"
    assert (await client.get(f"/api/pipeline/status?job_id={job_id}")).json()["progress"] == 30
    assert (await client.post("/api/pipeline/upload", files={"file": ("other.mp4", b"x")})).status_code == 409
    assert (await client.post("/api/pipeline/reset")).status_code == 409
    release.set()
    await asyncio.gather(*list(jobs.active_tasks))
    status = (await client.get("/api/pipeline/status")).json()
    assert status["status"] == "error" and "test gate failure" in status["error"]
    assert not (Path(settings.STATIC_ASSETS_DIR) / "current-scene.json").exists()
    assert (await client.post("/api/pipeline/reset")).status_code == 200
    assert (await client.get(f"/api/pipeline/status?job_id={job_id}")).json()["status"] == "error"


async def test_completion_is_persisted_and_broadcast_failure_does_not_reverse_commit(client, monkeypatch):
    async def worker(*args, **kwargs):
        return {"status": "PASSED"}

    async def failing_broadcast(*args):
        raise RuntimeError("socket disconnected")

    monkeypatch.setattr(api, "execute_drone_video_pipeline", worker)
    monkeypatch.setattr(api, "publish_verified_scene", lambda *args: {"job_id": args[2], "gaussian_count": 2})
    monkeypatch.setattr(api.manager, "broadcast", failing_broadcast)
    response = await client.post("/api/pipeline/upload", files={"file": ("unit.mp4", b"fixture")})
    await asyncio.gather(*list(jobs.active_tasks))
    state = jobs.get_state(response.json()["job_id"])
    assert state["status"] == "completed" and state["progress"] == 100
    assert state["details"]["scene_published"] is True
    jobs.recover_interrupted_job()
    assert jobs.get_state()["status"] == "completed"


async def test_shutdown_cancels_owned_worker_and_records_failure(client, monkeypatch):
    entered = asyncio.Event()

    async def worker(*args, **kwargs):
        entered.set()
        await asyncio.Future()

    monkeypatch.setattr(api, "execute_drone_video_pipeline", worker)
    await client.post("/api/pipeline/upload", files={"file": ("unit.mp4", b"fixture")})
    await entered.wait()
    await jobs.shutdown()
    assert jobs.get_state()["status"] == "error"
    assert "shutdown" in jobs.get_state()["error"]


async def test_restart_marks_interrupted_job_without_publishing():
    job_id, _ = jobs.create_job("interrupted.mp4", ".mp4")
    jobs.recover_interrupted_job()
    assert jobs.get_state(job_id)["status"] == "error"
    assert "restart" in jobs.get_state(job_id)["error"]


async def test_publication_failure_never_reports_success(client, monkeypatch):
    async def worker(*args, **kwargs):
        return {"status": "PASSED"}

    def reject(*args):
        raise ValueError("artifact integrity failed")

    monkeypatch.setattr(api, "execute_drone_video_pipeline", worker)
    monkeypatch.setattr(api, "publish_verified_scene", reject)
    await client.post("/api/pipeline/upload", files={"file": ("unit.mp4", b"fixture")})
    await asyncio.gather(*list(jobs.active_tasks))
    assert jobs.get_state()["status"] == "error"
    assert "integrity" in jobs.get_state()["error"]


@pytest.mark.parametrize("job_id,code", [("../../outside", 400), ("f" * 32, 404)])
async def test_job_id_validation(client, job_id, code):
    assert (await client.get("/api/pipeline/status", params={"job_id": job_id})).status_code == code


import struct


async def test_kaggle_config_endpoint(client):
    cfg = (await client.get("/api/pipeline/kaggle-config")).json()
    assert "configured" in cfg
    assert "enabled" in cfg
    assert cfg["configured"] == cfg["enabled"]


async def test_upload_kaggle_bad_format(client):
    response = await client.post("/api/pipeline/upload-kaggle", files={"file": ("bad.txt", b"not a video")})
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


async def test_import_splat_bad_data(client):
    response = await client.post("/api/pipeline/import-splat", files={"file": ("corrupt.splat", b"short")})
    assert response.status_code == 400


async def test_import_valid_splat(client):
    # 32-byte binary splat fixture: pos=(0,0,0), scale=(1,1,1), rgba=(255,255,255,255), rot=(128,128,128,255)
    splat_bytes = struct.pack("<3f3f4B4B", 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 255, 255, 255, 255, 128, 128, 128, 255)
    response = await client.post("/api/pipeline/import-splat", files={"file": ("valid.splat", splat_bytes)})
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["manifest"]["gaussian_count"] == 1
    # Verify current-scene.json was published
    scene_resp = await client.get("/api/pipeline/scene")
    assert scene_resp.status_code == 200
    assert scene_resp.json()["manifest"]["gaussian_count"] == 1



async def test_bad_manifest_never_falls_back_to_demo(client):
    atomic_json(Path(settings.STATIC_ASSETS_DIR) / "current-scene.json", {"job_id": "../../bad"})
    assert (await client.get("/api/pipeline/scene")).status_code == 503


@pytest.mark.parametrize("method,path,body", [
    ("get", "/api/objects/structures", None), ("get", "/api/objects/project", None),
    ("get", "/api/objects/regions", None), ("post", "/api/query", {"text": "buildings taller than 20 metres"}),
    ("post", "/api/edit/preview", {"text": "raise buildings by 20 metres"}),
    ("post", "/api/edit/apply", {"preview_token": "old-token"}), ("post", "/api/edit/undo", {}),
])
@pytest.mark.parametrize("published", [False, True])
async def test_legacy_database_never_substitutes_uploaded_scene(client, method, path, body, published, monkeypatch):
    if published:
        from backend import scene_capabilities
        monkeypatch.setattr(scene_capabilities, "read_current_scene", lambda root: {"capabilities": {"queries": False, "edits": False}})
    response = await client.request(method, path, **({"json": body} if body is not None else {}))
    assert response.status_code == 409
    assert "database" in response.json()["detail"]
