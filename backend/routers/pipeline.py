"""Verified local upload API: isolated jobs, fail-closed gates, atomic scenes."""
from __future__ import annotations

import asyncio
from pathlib import Path
import re
from typing import Any, Literal

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from backend.config import settings
from backend import pipeline_jobs as jobs
from backend.ws.manager import manager
from pipeline.video_orchestrator import execute_drone_video_pipeline
from pipeline.scene_publication import (
    atomic_json,
    publish_verified_scene,
    publish_external_splat_scene,
    read_current_scene,
    read_json,
)



router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


class PipelineStatusResponse(BaseModel):
    job_id: str | None = None
    status: Literal["idle", "processing", "completed", "error"]
    step: str
    progress: int
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


async def run_pipeline_task(job_id: str, file_path: Path) -> None:
    directory = jobs.job_path(job_id)

    def update_progress(step: str, percent: int, details: dict) -> None:
        state = jobs.get_state(job_id)
        if state["status"] != "processing":
            raise RuntimeError("Job no longer owns a processing ticket")
        state.update(step=step, progress=max(state["progress"], min(99, percent)),
                     details={**state["details"], **details})
        jobs.save_state(state)

    try:
        result = await execute_drone_video_pipeline(
            file_path, progress_callback=update_progress, job_dir=directory,
            timeout_seconds=settings.PIPELINE_TIMEOUT_SECONDS,
        )
        request = read_json(directory / "request.json")
        update_progress("Publishing verified Gaussian assets", 98, {})
        # Once commit begins, finish it even during graceful shutdown. Cancelling a
        # to_thread alone cannot stop that thread and would misreport a committed scene.
        commit = asyncio.create_task(asyncio.to_thread(
            publish_verified_scene, directory, Path(settings.STATIC_ASSETS_DIR), job_id, request["source_name"],
        ))
        interrupted = False
        try:
            manifest = await asyncio.shield(commit)
        except asyncio.CancelledError:
            manifest = await commit
            interrupted = True
        jobs.save_state({"job_id": job_id, "status": "completed", "progress": 100,
                         "step": "Verified 3D reconstruction ready", "error": None,
                         "details": {**result, "scene_published": True, "manifest": manifest}})
        if not interrupted:
            # Socket failure must not turn a successfully committed scene into an error.
            try:
                await manager.broadcast({"type": "scene_diff", "updated": [], "removed": [],
                                         "version": job_id, "source": "verified_video_pipeline",
                                         "manifest": manifest})
            except Exception as exc:
                print(f"[PIPELINE] Scene committed; WebSocket notification failed: {type(exc).__name__}", flush=True)
    except asyncio.CancelledError:
        jobs.set_failure(job_id, "Processing stopped during backend shutdown. Upload again to restart; no partial scene was published.")
        raise
    except asyncio.TimeoutError:
        jobs.set_failure(job_id, "Reconstruction exceeded its configured time limit and was stopped. Try a shorter continuous, textured camera shot; the previous scene was preserved.")
    except Exception as exc:
        import traceback
        traceback.print_exc()
        msg = str(exc).strip() or f"{type(exc).__name__}: Reconstruction worker failed"
        print(f"[PIPELINE ERROR] Job {job_id} failed: {msg}", flush=True)
        jobs.set_failure(job_id, msg)


@router.get("/status", response_model=PipelineStatusResponse)
async def get_pipeline_status(job_id: str | None = None):
    try:
        state = jobs.get_state(job_id)
        if state.get("status") == "error" and jobs.recover_completed_kaggle_job(state):
            state = jobs.get_state(job_id)
        return state
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(404, "That reconstruction job was not found") from exc


@router.get("/scene")
async def get_scene():
    try:
        manifest = await asyncio.to_thread(read_current_scene, Path(settings.STATIC_ASSETS_DIR))
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(503, "The published scene is missing or inconsistent. No demo or substitute scene will be shown; upload again or inspect the saved job.") from exc
    return {"status": "ready" if manifest else "empty", "manifest": manifest}


def is_active_reconstruction() -> bool:
    if jobs.upload_lock.locked() or bool(jobs.active_tasks):
        return True
    # If no task is running in memory, check if state on disk was left as 'processing'
    st = jobs.get_state()
    if st.get("status") == "processing":
        job_id = st.get("job_id")
        if job_id:
            jobs.set_failure(job_id, "Previous reconstruction was interrupted. Upload again to start fresh.")
        return False
    return False


async def run_kaggle_pipeline_task(job_id: str, file_path: Path) -> None:
    directory = jobs.job_path(job_id)

    def update_progress(step: str, percent: int, details: dict | None = None) -> None:
        state = jobs.get_state(job_id)
        if state["status"] != "processing":
            raise RuntimeError("Job no longer owns a processing ticket")
        state.update(
            step=step,
            progress=max(state["progress"], min(99, percent)),
            details={**state["details"], **(details or {})},
        )
        jobs.save_state(state)

    try:
        from pipeline.kaggle_runner import run_kaggle_3dgs_job, publish_kaggle_bundle
        update_progress("Authenticating with Kaggle Cloud API", 5)
        request = read_json(directory / "request.json")
        result = await run_kaggle_3dgs_job(
            file_path, progress_callback=update_progress, request=request,
            output_dir=directory / "kaggle-output", timeout_seconds=settings.PIPELINE_TIMEOUT_SECONDS,
        )

        update_progress("Publishing Kaggle 3DGS scene assets", 98)
        manifest = await asyncio.to_thread(
            publish_kaggle_bundle, Path(result["bundle_dir"]), Path(settings.STATIC_ASSETS_DIR),
            job_id, result["video_sha256"],
        )

        jobs.save_state({
            "job_id": job_id,
            "status": "completed",
            "progress": 100,
            "step": "Kaggle 3D reconstruction ready",
            "error": None,
            "details": {
                **result,
                "scene_published": True,
                "manifest": manifest,
            },
        })
        try:
            await manager.broadcast({
                "type": "scene_diff",
                "updated": [],
                "removed": [],
                "version": job_id,
                "source": "kaggle_3dgs_pipeline",
                "manifest": manifest,
            })
        except Exception as exc:
            print(f"[PIPELINE] Kaggle scene committed; WS broadcast notice: {exc}", flush=True)
    except asyncio.CancelledError:
        # Kaggle kernels continue after the API task is cancelled. If the
        # isolated bundle already arrived, publish it instead of reporting a
        # false Kaggle failure; startup/status recovery handles later arrival.
        if jobs.recover_completed_kaggle_job(jobs.get_state(job_id)):
            return
        jobs.set_failure(job_id, "Kaggle processing stopped during backend shutdown; the cloud result will be recovered if it completes.")
        raise
    except Exception as exc:
        import traceback
        traceback.print_exc()
        msg = str(exc).strip() or f"{type(exc).__name__}: Kaggle worker failed"
        print(f"[KAGGLE PIPELINE ERROR] Job {job_id} failed: {msg}", flush=True)
        jobs.set_failure(job_id, msg)


@router.post("/reset")
async def reset_pipeline():
    if is_active_reconstruction():
        raise HTTPException(409, "A reconstruction is active. Reset cannot cancel it or allow a second job.")
    atomic_json(jobs.root() / "latest-job.json", {"job_id": None})
    return {"status": "ok", "message": "Status reset; saved jobs and the verified scene were preserved"}


@router.post("/upload")
async def upload_drone_video(request: Request, file: UploadFile = File(...)):
    filename = re.split(r"[/\\]", file.filename or "")[-1]
    suffix = Path(filename).suffix.lower()
    if suffix not in {".mp4", ".mov", ".avi", ".mkv"}:
        await file.close()
        raise HTTPException(400, "Unsupported file format. Please upload an MP4, MOV, AVI or MKV camera recording.")
    limit = settings.PIPELINE_MAX_UPLOAD_MB * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > limit + 1024 * 1024:
        await file.close()
        raise HTTPException(413, f"Video exceeds the {settings.PIPELINE_MAX_UPLOAD_MB}MB upload limit")
    if is_active_reconstruction():
        await file.close()
        raise HTTPException(409, "A video is already being processed. Please wait; concurrent GPU jobs are disabled.")
    async with jobs.upload_lock:
        job_id, destination = jobs.create_job(filename[:255], suffix)
        try:
            total = 0
            with destination.open("xb") as stream:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > limit:
                        raise HTTPException(413, f"Video exceeds the {settings.PIPELINE_MAX_UPLOAD_MB}MB upload limit")
                    await asyncio.to_thread(stream.write, chunk)
            if total == 0:
                raise HTTPException(400, "The uploaded video is empty. Please select a camera recording.")
        except BaseException as exc:
            destination.unlink(missing_ok=True)
            jobs.set_failure(job_id, str(exc.detail) if isinstance(exc, HTTPException) else "Upload was interrupted; no reconstruction was started.")
            if isinstance(exc, (HTTPException, asyncio.CancelledError)):
                raise
            raise HTTPException(500, "The video could not be saved. Check free disk space and try again.") from exc
        finally:
            await file.close()
        state = jobs.get_state(job_id)
        state.update(step="Video received; starting verified reconstruction", progress=5,
                     details={"filename": filename[:255], "file_size_bytes": total})
        jobs.save_state(state)
        task = asyncio.create_task(run_pipeline_task(job_id, destination))
        jobs.active_tasks.add(task)
        task.add_done_callback(jobs.active_tasks.discard)
    return {"job_id": job_id, "status": "processing", "message": "Video received. Real camera, surface and Gaussian verification has started; this can take several minutes."}


@router.get("/kaggle-config")
async def get_kaggle_config():
    import os
    from pipeline.kaggle_runner import is_kaggle_configured
    configured = is_kaggle_configured()
    username = (os.environ.get("KAGGLE_USERNAME") or settings.KAGGLE_USERNAME or "").strip()
    return {
        "configured": configured,
        "username": username,
        "enabled": configured,
        "reason": "Kaggle 16GB GPU training is ready." if configured else "Kaggle credentials not configured in .env",
    }


@router.post("/upload-kaggle")
async def upload_drone_video_kaggle(request: Request, file: UploadFile = File(...)):
    filename = re.split(r"[/\\]", file.filename or "")[-1]
    suffix = Path(filename).suffix.lower()
    if suffix not in {".mp4", ".mov", ".avi", ".mkv"}:
        await file.close()
        raise HTTPException(400, "Unsupported file format. Please upload an MP4, MOV, AVI or MKV camera recording.")

    from pipeline.kaggle_runner import is_kaggle_configured
    if not is_kaggle_configured():
        await file.close()
        raise HTTPException(400, "Kaggle credentials not configured. Please set KAGGLE_USERNAME and KAGGLE_KEY in .env")

    limit = settings.PIPELINE_MAX_UPLOAD_MB * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > limit + 1024 * 1024:
        await file.close()
        raise HTTPException(413, f"Video exceeds the {settings.PIPELINE_MAX_UPLOAD_MB}MB upload limit")

    if is_active_reconstruction():
        await file.close()
        raise HTTPException(409, "A reconstruction is already active. Please wait; concurrent GPU jobs are disabled.")

    async with jobs.upload_lock:
        job_id, destination = jobs.create_job(filename[:255], suffix)
        try:
            total = 0
            with destination.open("xb") as stream:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > limit:
                        raise HTTPException(413, f"Video exceeds the {settings.PIPELINE_MAX_UPLOAD_MB}MB upload limit")
                    await asyncio.to_thread(stream.write, chunk)
            if total == 0:
                raise HTTPException(400, "The uploaded video is empty. Please select a camera recording.")
        except BaseException as exc:
            destination.unlink(missing_ok=True)
            jobs.set_failure(job_id, str(exc.detail) if isinstance(exc, HTTPException) else "Upload was interrupted; no reconstruction was started.")
            if isinstance(exc, (HTTPException, asyncio.CancelledError)):
                raise
            raise HTTPException(500, "The video could not be saved. Check free disk space and try again.") from exc
        finally:
            await file.close()

        state = jobs.get_state(job_id)
        state.update(
            step="Video received; submitting Kaggle 16GB GPU training job",
            progress=5,
            details={"filename": filename[:255], "file_size_bytes": total, "provider": "kaggle"}
        )
        jobs.save_state(state)
        task = asyncio.create_task(run_kaggle_pipeline_task(job_id, destination))
        jobs.active_tasks.add(task)
        task.add_done_callback(jobs.active_tasks.discard)

    return {
        "job_id": job_id,
        "status": "processing",
        "message": "Video received. Kaggle 16GB GPU training initiated; results will download automatically."
    }


@router.post("/import-splat")
async def import_trained_splat(request: Request, file: UploadFile = File(...)):
    filename = re.split(r"[/\\]", file.filename or "")[-1]
    suffix = Path(filename).suffix.lower()
    if suffix not in {".splat", ".ply"}:
        await file.close()
        raise HTTPException(400, "Unsupported file format. Please upload a .splat or .ply 3D Gaussian file.")

    limit = settings.PIPELINE_MAX_UPLOAD_MB * 1024 * 1024
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > limit + 1024 * 1024:
        await file.close()
        raise HTTPException(413, f"File exceeds the {settings.PIPELINE_MAX_UPLOAD_MB}MB upload limit")

    if is_active_reconstruction():
        await file.close()
        raise HTTPException(409, "A reconstruction is already active. Please wait for it to complete.")

    async with jobs.upload_lock:
        job_id, destination = jobs.create_job(filename[:255], suffix)
        try:
            total = 0
            with destination.open("xb") as stream:
                while chunk := await file.read(1024 * 1024):
                    total += len(chunk)
                    if total > limit:
                        raise HTTPException(413, f"File exceeds the {settings.PIPELINE_MAX_UPLOAD_MB}MB upload limit")
                    await asyncio.to_thread(stream.write, chunk)
            if total == 0:
                raise HTTPException(400, "The uploaded file is empty.")
        except BaseException as exc:
            destination.unlink(missing_ok=True)
            jobs.set_failure(job_id, str(exc.detail) if isinstance(exc, HTTPException) else "Upload was interrupted.")
            if isinstance(exc, (HTTPException, asyncio.CancelledError)):
                raise
            raise HTTPException(500, "The file could not be saved.") from exc
        finally:
            await file.close()

        try:
            static_dir = Path(settings.STATIC_ASSETS_DIR)
            if suffix == ".ply":
                from pipeline.common.io import load_ply, save_splat
                ply_data = await asyncio.to_thread(load_ply, str(destination))
                splat_conv = destination.with_suffix(".splat")
                await asyncio.to_thread(
                    save_splat,
                    str(splat_conv),
                    ply_data["positions"],
                    ply_data["scales"],
                    ply_data["colors"],
                    ply_data["rotations"],
                )
                active_splat = splat_conv
            else:
                active_splat = destination

            manifest = await asyncio.to_thread(
                publish_external_splat_scene,
                active_splat,
                static_dir,
                job_id,
                filename[:255],
                None,
                "imported_splat",
            )

            num_buildings = 0
            try:
                from pipeline.extract_scene_structures import extract_and_sync_scene_structures
                sync_res = await extract_and_sync_scene_structures(job_id)
                num_buildings = sync_res.get("buildings_extracted", 0)
                manifest = sync_res.get("manifest", manifest)
            except Exception as e:
                print(f"[PIPELINE WARN] Structure extraction failed: {e}", flush=True)

            jobs.save_state({
                "job_id": job_id,
                "status": "completed",
                "progress": 100,
                "step": "Imported 3D scene ready",
                "error": None,
                "details": {
                    "manifest": manifest,
                    "buildings_extracted": num_buildings,
                    "filename": filename[:255],
                    "file_size_bytes": total,
                }
            })
            try:
                await manager.broadcast({
                    "type": "scene_diff",
                    "updated": [],
                    "removed": [],
                    "version": job_id,
                    "source": "imported_splat",
                    "manifest": manifest,
                })
            except Exception:
                pass

            return {
                "status": "completed",
                "message": "3D scene imported successfully",
                "buildings_extracted": num_buildings,
                "manifest": manifest,
            }
        except Exception as exc:
            jobs.set_failure(job_id, f"Failed to import 3D splat: {exc}")
            raise HTTPException(400, f"Failed to import 3D splat: {exc}") from exc


@router.post("/align-structures")
async def align_structures(job_id: str | None = None):
    """
    Extracts building proxy geometry from the active scene,
    populates PostGIS 3D SFCGAL solids, and enables natural language
    queries and edits.
    """
    try:
        from pipeline.extract_scene_structures import extract_and_sync_scene_structures
        result = await extract_and_sync_scene_structures(job_id)
        # Broadcast updated scene capabilities to all connected clients
        try:
            await manager.broadcast({
                "type": "scene_diff",
                "updated": [],
                "removed": [],
                "version": result["manifest"]["job_id"],
                "source": "align_structures",
                "manifest": result["manifest"],
            })
        except Exception:
            pass
        return result
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(500, f"Structure alignment failed: {exc}") from exc

