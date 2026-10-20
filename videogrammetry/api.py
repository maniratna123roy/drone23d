"""Capture API for Videogrammetry Sidecar.
Implements the HTTP API contracts defined in Section 8 of the architecture document:
- POST /v1/captures -> create capture record
- POST /v1/captures/{id}/upload -> upload drone video
- POST /v1/captures/{id}/start -> start reconstruction pipeline
- GET  /v1/captures/{id} -> get status, stages, progress, attempt, quality
- GET  /v1/captures/{id}/artifacts -> list signed/direct artifact download URLs
- GET  /v1/captures/{id}/manifest -> retrieve manifest.json audit trail
- GET  /v1/captures -> list all captures
- GET  /v1/tiers -> list available quality tiers
- Static artifact file serving under /videogrammetry/artifacts/
"""

import asyncio
import os
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from videogrammetry.models import (
    Capture,
    CaptureStatus,
    CreateCaptureRequest,
    StartCaptureRequest,
    ArtifactRef,
)
from videogrammetry.tiers import TIERS, get_tier
from videogrammetry.storage import StorageManager
from videogrammetry.orchestrator import PipelineOrchestrator

# Setup base directories
WORKSPACE_DIR = Path(__file__).resolve().parent.parent
STORAGE_BASE = WORKSPACE_DIR / "output" / "videogrammetry"
STORAGE_BASE.mkdir(parents=True, exist_ok=True)

storage_mgr = StorageManager(STORAGE_BASE)
orchestrator = PipelineOrchestrator(storage_mgr, base_url="/api/videogrammetry/artifacts")

# In-memory database of captures
captures_db: Dict[str, Capture] = {}

def _load_existing_captures():
    if not storage_mgr.captures_dir.exists():
        return
    for cdir in storage_mgr.captures_dir.iterdir():
        if cdir.is_dir() and cdir.name.startswith("cap_"):
            cid = cdir.name
            out_dir = cdir / "out"
            has_model = (out_dir / "scene.glb").exists() and (out_dir / "scene.glb").stat().st_size > 0
            raw_dir = cdir / "raw"
            v_files = list(raw_dir.glob("*.mp4")) + list(raw_dir.glob("*.mov"))
            v_name = v_files[0].name if v_files else "drone_video.mp4"

            if cid in captures_db:
                if captures_db[cid].status == CaptureStatus.FAILED and has_model:
                    captures_db[cid].status = CaptureStatus.COMPLETED
                    captures_db[cid].progress = 100.0
                    captures_db[cid].error_message = None
                    from videogrammetry.models import StageStatus
                    for st in captures_db[cid].stages:
                        st.status = StageStatus.COMPLETED
                continue

            capture = Capture(
                id=cid,
                source_system="vantage_spatial_twin",
                tier="standard",
                status=CaptureStatus.COMPLETED if has_model else CaptureStatus.FAILED,
                progress=100.0 if has_model else 0.0,
                video_filename=v_name,
            )
            orchestrator.initialize_capture_stages(capture)
            if has_model:
                from videogrammetry.models import StageStatus
                for st in capture.stages:
                    st.status = StageStatus.COMPLETED
            captures_db[cid] = capture

_load_existing_captures()

router = APIRouter(prefix="/v1", tags=["videogrammetry"])

@router.get("/tiers")
def list_tiers():
    """Returns available quality tiers (Lite, Standard, Premium, Premium Advanced)."""
    return [t.model_dump() for t in TIERS.values()]

@router.get("/captures")
def list_captures():
    """List all captures in descending order of creation."""
    _load_existing_captures()
    return [c.model_dump() for c in reversed(list(captures_db.values()))]

@router.post("/captures", status_code=201)
def create_capture(req: CreateCaptureRequest):
    """Creates a new capture and generates upload coordinates."""
    cid = f"cap_{uuid.uuid4().hex[:8]}"
    tier_cfg = get_tier(req.tier)

    capture = Capture(
        id=cid,
        source_system=req.source_system,
        source_id=req.source_id,
        tier=tier_cfg.id,
        crs=req.crs,
    )
    orchestrator.initialize_capture_stages(capture)
    captures_db[cid] = capture

    return {
        "capture_id": cid,
        "tier": tier_cfg.id,
        "status": capture.status,
        "upload": {
            "method": "POST",
            "url": f"/api/videogrammetry/v1/captures/{cid}/upload",
            "accepted_codecs": ["h264", "hevc", "mp4", "mov"],
        }
    }

@router.post("/captures/{id}/upload")
async def upload_capture_video(
    id: str,
    file: UploadFile = File(...),
    gps_file: Optional[UploadFile] = File(None)
):
    """Receives drone video and optional companion GPS/SRT file."""
    if id not in captures_db:
        raise HTTPException(status_code=404, detail="Capture not found")

    capture = captures_db[id]
    raw_dir = storage_mgr.get_raw_dir(id)

    # Save video file
    video_dest = raw_dir / file.filename
    with open(video_dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    capture.video_filename = file.filename
    capture.video_size_bytes = video_dest.stat().st_size
    capture.status = CaptureStatus.QUEUED

    # Optional GPS file
    if gps_file and gps_file.filename:
        gps_dest = raw_dir / gps_file.filename
        with open(gps_dest, "wb") as buffer:
            shutil.copyfileobj(gps_file.file, buffer)
        capture.has_gps = True

    return {
        "status": "uploaded",
        "capture_id": id,
        "video_filename": file.filename,
        "size_bytes": capture.video_size_bytes,
        "has_gps": capture.has_gps,
        "next_step": f"POST /v1/captures/{id}/start",
    }

@router.post("/captures/{id}/start")
async def start_capture(
    id: str,
    req: StartCaptureRequest,
    bg_tasks: BackgroundTasks
):
    """Launches the 8-stage Videogrammetry reconstruction state machine."""
    if id not in captures_db:
        raise HTTPException(status_code=404, detail="Capture not found")

    capture = captures_db[id]
    if capture.status == CaptureStatus.PROCESSING:
        return {"status": "already_running", "capture_id": id}

    if req.tier:
        capture.tier = get_tier(req.tier).id
    if req.crs:
        capture.crs = req.crs

    raw_dir = storage_mgr.get_raw_dir(id)
    video_path = raw_dir / (capture.video_filename or "video.mp4")

    # If no real video uploaded yet (e.g. testing), create a sample placeholder video
    if not video_path.exists():
        import cv2
        import numpy as np
        video_path = raw_dir / "sample_drone_orbit.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out_vid = cv2.VideoWriter(str(video_path), fourcc, 24.0, (1280, 720))
        for f_i in range(120): # 5 seconds sample
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            frame[:] = (70 + (f_i % 10), 80, 85)
            cv2.putText(frame, f"VANTAGE DRONE PASS - FRAME {f_i}", (100, 360), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
            out_vid.write(frame)
        out_vid.release()
        capture.video_filename = video_path.name
        capture.video_size_bytes = video_path.stat().st_size

    # Launch in background: offload to Colab GPU if connected, else run locally
    from videogrammetry.colab_bridge import colab_bridge
    if colab_bridge.is_connected:
        bg_tasks.add_task(orchestrator.run_colab, capture, video_path)
    else:
        bg_tasks.add_task(orchestrator.run, capture, video_path)

    return {
        "status": "started",
        "capture_id": id,
        "tier": capture.tier,
        "mode": "colab_gpu" if colab_bridge.is_connected else "local",
        "tracking_url": f"/api/videogrammetry/v1/captures/{id}"
    }

@router.get("/colab/status")
async def get_colab_status():
    """Returns live connection status and GPU specs of the remote Colab worker."""
    from videogrammetry.colab_bridge import colab_bridge
    if colab_bridge.worker_url:
        return await colab_bridge.check_health()
    return {
        "connected": False,
        "worker_url": None,
        "device": None,
        "vram_gb": 0,
        "message": "No Google Colab GPU worker connected."
    }

@router.post("/colab/connect")
async def connect_colab_worker(payload: Dict[str, Any]):
    """Connects to a remote Google Colab GPU worker (e.g. from Cloudflare tunnel)."""
    from videogrammetry.colab_bridge import colab_bridge
    worker_url = payload.get("worker_url", "").strip()
    if not worker_url:
        raise HTTPException(status_code=400, detail="worker_url is required")
    health = await colab_bridge.check_health(worker_url)
    if not health.get("connected"):
        raise HTTPException(
            status_code=502,
            detail=f"Could not connect to Colab worker at {worker_url}: {health.get('error', 'Health check timed out')}"
        )
    return health

@router.post("/colab/register")
async def register_colab_worker(payload: Dict[str, Any]):
    """Webhook for Colab notebook to automatically register its tunnel URL upon startup.
    Eliminates manual copy-pasting for the user.
    """
    from videogrammetry.colab_bridge import colab_bridge
    worker_url = payload.get("worker_url", "").strip()
    if not worker_url:
        raise HTTPException(status_code=400, detail="worker_url is required")
    health = await colab_bridge.check_health(worker_url)
    return {"registered": health.get("connected", False), "status": health}

@router.post("/colab/disconnect")
def disconnect_colab_worker():
    """Disconnects the remote Google Colab GPU worker."""
    from videogrammetry.colab_bridge import colab_bridge
    colab_bridge.worker_url = None
    colab_bridge.is_connected = False
    return {"status": "disconnected"}

@router.get("/captures/{id}")
def get_capture_status(id: str):
    """Retrieves live capture status, current stage, attempt number, and quality metrics."""
    if id not in captures_db:
        _load_existing_captures()
    if id not in captures_db:
        raise HTTPException(status_code=404, detail="Capture not found")
    return captures_db[id].model_dump()

@router.get("/captures/{id}/artifacts")
def get_capture_artifacts(id: str):
    """Returns download URLs for all produced artifacts (GLB, OBJ, LAZ, Orthomosaic, etc.)."""
    if id not in captures_db:
        _load_existing_captures()
    if id not in captures_db:
        raise HTTPException(status_code=404, detail="Capture not found")
    capture = captures_db[id]
    if not capture.artifacts:
        out_dir = storage_mgr.get_out_dir(id)
        tier_cfg = get_tier(capture.tier)
        from videogrammetry.stages.stage8_export import Stage8Export
        capture.artifacts = Stage8Export(out_dir, base_url="/api/videogrammetry/artifacts").execute(
            capture_id=id,
            tier_config=tier_cfg,
            quality_report=capture.quality_report,
            crs=capture.crs
        )
    return {
        "capture_id": id,
        "status": capture.status,
        "artifacts": [a.model_dump() for a in capture.artifacts],
    }

@router.get("/captures/{id}/manifest")
def get_capture_manifest(id: str):
    """Retrieves the full manifest.json audit trail."""
    out_dir = storage_mgr.get_out_dir(id)
    manifest_file = out_dir / "manifest.json"
    if not manifest_file.exists():
        raise HTTPException(status_code=404, detail="Manifest not yet generated")
    return FileResponse(manifest_file, media_type="application/json", filename="manifest.json")

@router.get("/captures/{id}/model")
def get_capture_model(id: str):
    """Directly serves scene.glb, point_cloud.ply, or mesh.obj with proper MIME type and CORS."""
    out_dir = storage_mgr.get_out_dir(id)
    glb_file = out_dir / "scene.glb"
    if glb_file.exists():
        return FileResponse(
            glb_file,
            media_type="model/gltf-binary",
            filename=f"{id}_scene.glb",
            headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"}
        )
    ply_file = out_dir / "point_cloud.ply"
    if ply_file.exists():
        return FileResponse(
            ply_file,
            media_type="application/octet-stream",
            filename=f"{id}_point_cloud.ply",
            headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"}
        )
    obj_file = out_dir / "mesh.obj"
    if obj_file.exists():
        return FileResponse(
            obj_file,
            media_type="text/plain",
            filename=f"{id}_mesh.obj",
            headers={"Access-Control-Allow-Origin": "*", "Cache-Control": "no-cache"}
        )
    raise HTTPException(status_code=404, detail="3D model (scene.glb/point_cloud.ply/mesh.obj) not found for this capture")

@router.post("/captures/{id}/import-model")
async def import_capture_model(
    id: str,
    file: UploadFile = File(...)
):
    """Allows importing a pre-trained model (e.g. from Google Colab) into this capture."""
    out_dir = storage_mgr.get_out_dir(id)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = file.filename.lower()

    if fname.endswith(".glb"):
        dest = out_dir / "scene.glb"
        kind = "glb"
        mime = "model/gltf-binary"
    elif fname.endswith(".ply"):
        dest = out_dir / "point_cloud.ply"
        kind = "ply"
        mime = "application/octet-stream"
    elif fname.endswith(".obj"):
        dest = out_dir / "mesh.obj"
        kind = "obj"
        mime = "text/plain"
    elif fname.endswith(".splat"):
        dest = out_dir / "scene.splat"
        kind = "splat"
        mime = "application/octet-stream"
    else:
        dest = out_dir / file.filename
        kind = "model"
        mime = "application/octet-stream"

    with open(dest, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    size_bytes = dest.stat().st_size

    if id in captures_db:
        cap = captures_db[id]
        cap.status = CaptureStatus.COMPLETED
        cap.progress = 100.0
        # Register artifact reference if not already present
        existing = next((a for a in cap.artifacts if a.filename == dest.name), None)
        if not existing:
            cap.artifacts.append(
                ArtifactRef(
                    id=f"{id}_{kind}",
                    capture_id=id,
                    kind=kind,
                    filename=dest.name,
                    uri=f"/api/videogrammetry/artifacts/{id}/{dest.name}",
                    bytes=size_bytes,
                    mime_type=mime,
                    produced_by_stage="colab_import"
                )
            )

    return {
        "status": "imported",
        "capture_id": id,
        "filename": dest.name,
        "bytes": size_bytes,
        "kind": kind,
        "model_url": f"/v1/captures/{id}/model"
    }

# Standalone FastAPI App for the Sidecar
sidecar_app = FastAPI(title="Videogrammetry Sidecar API", version="1.0.0")

sidecar_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sidecar_app.include_router(router)

# Mount artifacts folder
sidecar_app.mount(
    "/artifacts",
    StaticFiles(directory=str(storage_mgr.captures_dir)),
    name="videogrammetry_artifacts"
)

# Export router and app
__all__ = ["router", "sidecar_app", "captures_db", "orchestrator", "storage_mgr"]
