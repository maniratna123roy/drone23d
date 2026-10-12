"""Disk-backed, single-worker reconstruction tickets and restart recovery."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
import uuid

from backend.config import settings
from pipeline.scene_publication import atomic_json, read_json, read_current_scene, validate_job_id

active_tasks: set[asyncio.Task] = set()
upload_lock = asyncio.Lock()
_owner_file = None


def root() -> Path:
    return Path(settings.PIPELINE_JOBS_DIR).resolve()


def job_path(job_id: str) -> Path:
    return root() / validate_job_id(job_id)


def idle_state() -> dict:
    return {"job_id": None, "status": "idle", "step": "Ready for real drone footage",
            "progress": 0, "details": {}, "error": None}


def get_state(job_id: str | None = None) -> dict:
    if job_id is None:
        pointer = root() / "latest-job.json"
        if not pointer.exists():
            return idle_state()
        job_id = read_json(pointer).get("job_id")
        if job_id is None:
            return idle_state()
    return read_json(job_path(job_id) / "status.json")


def save_state(state: dict) -> None:
    state = {**state, "updated_at": datetime.now(timezone.utc).isoformat()}
    atomic_json(job_path(state["job_id"]) / "status.json", state)


def create_job(source_name: str, suffix: str) -> tuple[str, Path]:
    job_id = uuid.uuid4().hex
    directory = job_path(job_id)
    directory.mkdir(parents=True, exist_ok=False)
    atomic_json(directory / "request.json", {
        "job_id": job_id, "source_name": source_name, "input_file": f"input{suffix}",
        "max_frames": settings.PIPELINE_MAX_FRAMES, "image_width": settings.PIPELINE_IMAGE_WIDTH,
        "render_width": settings.PIPELINE_RENDER_WIDTH, "iterations": settings.PIPELINE_TRAIN_ITERATIONS,
        "max_gaussians": settings.PIPELINE_MAX_GAUSSIANS, "device": settings.PIPELINE_DEVICE,
        "camera_model": settings.PIPELINE_CAMERA_MODEL,
    })
    save_state({"job_id": job_id, "status": "processing", "step": "Receiving uploaded footage",
                "progress": 1, "details": {"filename": source_name}, "error": None})
    atomic_json(root() / "latest-job.json", {"job_id": job_id})
    return job_id, directory / f"input{suffix}"


def set_failure(job_id: str, error: str) -> None:
    state = get_state(job_id)
    state.update(status="error", step="Reconstruction stopped; previous verified scene was preserved", error=error or "Reconstruction stopped unexpectedly")
    save_state(state)


def acquire_worker_lock() -> None:
    """Best-effort OS file lock so two backends don't run reconstructions at once.

    On Windows, stale lock files from killed processes can block startup.
    After retrying, we delete the lock and try once more — a killed process
    can't actually be using the workspace, so this is safe.
    """
    global _owner_file
    root().mkdir(parents=True, exist_ok=True)
    lock_path = root() / ".worker.lock"

    import os, time

    def _try_lock() -> bool:
        global _owner_file
        stream = lock_path.open("a+b")
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            _owner_file = stream
            return True
        except OSError:
            stream.close()
            return False

    # Try a few times with a delay (handles --reload race)
    for _ in range(3):
        if _try_lock():
            return
        time.sleep(0.5)

    raise RuntimeError("Another backend is already running or holding the reconstruction worker lock.")




def recover_interrupted_job() -> None:
    state = get_state()
    if state["status"] not in {"processing", "error"}:
        return
    if state["status"] == "error" and state.get("error") != "Kaggle processing stopped during backend shutdown.":
        return
    if recover_completed_kaggle_job(state):
        return
    if state["status"] != "processing":
        return
    try:
        scene = read_current_scene(Path(settings.STATIC_ASSETS_DIR))
    except (OSError, ValueError):
        scene = None
    if scene and scene["job_id"] == state["job_id"]:
        state.update(status="completed", progress=100, step="Verified scene recovered after restart",
                     details={"manifest": scene}, error=None)
        save_state(state)
    else:
        set_failure(state["job_id"], "Processing was interrupted by a backend restart. Upload again to start a fresh job; no partial reconstruction was published.")


def recover_completed_kaggle_job(state: dict) -> bool:
    """Publish a cloud bundle that finished after the API task was cancelled."""
    if not isinstance(state, dict) or not state.get("job_id"):
        return False
    directory = job_path(state["job_id"])
    result_path = directory / "kaggle-output/cloud_result.json"
    request_path = directory / "request.json"
    if not result_path.is_file() or not request_path.is_file():
        return False
    try:
        result = read_json(result_path)
        if result.get("status") != "PASSED" or result.get("job_id") != state["job_id"]:
            return False
        from pipeline.kaggle_runner import publish_kaggle_bundle
        manifest = publish_kaggle_bundle(
            directory / "kaggle-output", Path(settings.STATIC_ASSETS_DIR),
            state["job_id"], result["video_sha256"],
        )
        save_state({
            "job_id": state["job_id"], "status": "completed", "progress": 100,
            "step": "Kaggle 3D reconstruction recovered after backend restart", "error": None,
            "details": {**state.get("details", {}), **result, "scene_published": True, "manifest": manifest},
        })
        return True
    except (OSError, ValueError, KeyError) as exc:
        print(f"[PIPELINE RECOVERY] Kaggle bundle is not publishable: {exc}", flush=True)
        return False


async def shutdown() -> None:
    global _owner_file
    tasks = list(active_tasks)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    if _owner_file is not None:
        _owner_file.close()
        _owner_file = None
