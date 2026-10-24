"""FastAPI Router for VantageCam Pipeline Integration.

Endpoints for creating captures, managing pipeline jobs, and querying status.
"""

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, File, UploadFile
from fastapi.responses import JSONResponse
import json

from backend.config import settings
from backend.db.connection import get_pool
from backend.schemas.vantagecam import (
    CaptureResponse,
    CreateCaptureRequest,
    StartCaptureRequest,
    CaptureListResponse,
    CaptureStatusResponse,
    StageResponse,
    ArtifactResponse,
)
from backend.vantagecam_jobs import job_manager
from vantagecam.tiers import get_tier, list_tiers

router = APIRouter(prefix="/api/vantagecam", tags=["vantagecam"])


def _generate_capture_id() -> str:
    """Generate a unique capture ID in the format: cap_YYYYMMDD_HHMMSS_UUID."""
    now = datetime.utcnow()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    unique_suffix = str(uuid.uuid4())[:8]
    return f"cap_{timestamp}_{unique_suffix}"


async def _create_capture_in_db(
    capture_id: str,
    tier: str,
    device: str,
    storage_dir: str,
) -> dict:
    """Create a new capture record in the database."""
    pool = get_pool()
    tier_config = get_tier(tier)
    if not tier_config:
        raise ValueError(f"Invalid tier: {tier}")

    max_attempts = tier_config.get("max_attempts", 1)
    
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO vantagecam_captures 
            (id, tier, status, attempt_count, max_attempts, storage_dir, device, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """, capture_id, tier, "CREATED", 0, max_attempts, storage_dir, device, datetime.utcnow(), datetime.utcnow())

    return {
        "id": capture_id,
        "tier": tier,
        "status": "CREATED",
        "attempt_count": 0,
        "max_attempts": max_attempts,
        "storage_dir": storage_dir,
        "device": device,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }


async def _get_capture_by_id(capture_id: str) -> Optional[dict]:
    """Fetch a capture from the database."""
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM vantagecam_captures WHERE id = $1",
            capture_id
        )
    return dict(row) if row else None


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/config")
async def get_vantagecam_config():
    """Get VantageCam configuration and available tiers."""
    return {
        "available_tiers": list_tiers(),
        "storage_base_dir": "output/vantagecam/captures",
        "supported_devices": ["cpu", "cuda:0", "cuda:1"],
        "max_video_size_mb": 2048,
    }


@router.post("/captures", response_model=CaptureResponse)
async def create_capture(request: CreateCaptureRequest):
    """Create a new VantageCam capture job.
    
    Args:
        tier: Quality tier ('lite', 'standard', 'premium', 'premium_advanced')
        device: Device to use ('cpu' or 'cuda:0')
    
    Returns:
        Newly created capture record.
    """
    # Validate tier
    tier_config = get_tier(request.tier)
    if not tier_config:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {request.tier}")

    # Generate capture ID and storage path
    capture_id = _generate_capture_id()
    storage_base = Path("output/vantagecam/captures")
    storage_dir = storage_base / capture_id
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Create in database
    try:
        capture_data = await _create_capture_in_db(
            capture_id=capture_id,
            tier=request.tier,
            device=request.device,
            storage_dir=str(storage_dir),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create capture: {str(e)}")

    return CaptureResponse(
        id=capture_data["id"],
        tier=capture_data["tier"],
        status=capture_data["status"],
        attempt_count=capture_data["attempt_count"],
        max_attempts=capture_data["max_attempts"],
        storage_dir=capture_data["storage_dir"],
        device=capture_data["device"],
        created_at=capture_data["created_at"],
        updated_at=capture_data["updated_at"],
    )


@router.get("/captures")
async def list_captures(skip: int = 0, limit: int = 100):
    """List all VantageCam captures."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM vantagecam_captures ORDER BY created_at DESC LIMIT $1 OFFSET $2",
            limit,
            skip,
        )
    
    captures = [CaptureResponse(**dict(row)) for row in rows]
    return CaptureListResponse(total=len(captures), captures=captures)


@router.get("/captures/{capture_id}", response_model=CaptureStatusResponse)
async def get_capture_status(capture_id: str):
    """Get status of a specific capture job."""
    capture_data = await _get_capture_by_id(capture_id)
    if not capture_data:
        raise HTTPException(status_code=404, detail=f"Capture {capture_id} not found")

    # Get stages
    pool = get_pool()
    async with pool.acquire() as conn:
        stages_rows = await conn.fetch(
            "SELECT * FROM vantagecam_stages WHERE capture_id = $1 ORDER BY stage_index",
            capture_id,
        )
    
    stages = [StageResponse(**dict(row)) for row in stages_rows]
    
    # Calculate progress percentage
    total_stages = 10
    completed_stages = sum(1 for s in stages if s.status == "COMPLETED")
    progress_percent = (completed_stages / total_stages) * 100 if total_stages > 0 else 0

    return CaptureStatusResponse(
        id=capture_data["id"],
        tier=capture_data["tier"],
        status=capture_data["status"],
        attempt_count=capture_data["attempt_count"],
        max_attempts=capture_data["max_attempts"],
        error_message=capture_data.get("error_message"),
        progress_percent=progress_percent,
        stages=stages,
        created_at=capture_data["created_at"],
        updated_at=capture_data["updated_at"],
    )


@router.post("/captures/{capture_id}/upload")
async def upload_video(
    capture_id: str,
    video: UploadFile = File(...),
    gps_file: Optional[UploadFile] = File(None),
):
    """Upload video and optional GPS file for a capture."""
    capture_data = await _get_capture_by_id(capture_id)
    if not capture_data:
        raise HTTPException(status_code=404, detail=f"Capture {capture_id} not found")

    if capture_data["status"] not in ("CREATED", "UPLOADING"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot upload to capture in status {capture_data['status']}",
        )

    # Create storage directories
    storage_path = Path(capture_data["storage_dir"])
    raw_dir = storage_path / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Save video file
    video_filename = video.filename or "video.mp4"
    video_path = raw_dir / video_filename
    with open(video_path, "wb") as f:
        content = await video.read()
        f.write(content)

    # Save GPS file if provided
    gps_path = None
    if gps_file:
        gps_filename = gps_file.filename or "gps.log"
        gps_path = raw_dir / gps_filename
        with open(gps_path, "wb") as f:
            content = await gps_file.read()
            f.write(content)

    # Update capture in database
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE vantagecam_captures 
            SET video_path = $1, gps_file_path = $2, status = $3, updated_at = $4
            WHERE id = $5
            """,
            str(video_path),
            str(gps_path) if gps_path else None,
            "UPLOADING",
            datetime.utcnow(),
            capture_id,
        )

    return {
        "capture_id": capture_id,
        "video_path": str(video_path),
        "gps_file_path": str(gps_path) if gps_path else None,
        "status": "uploaded",
    }


@router.post("/captures/{capture_id}/start")
async def start_capture_pipeline(
    capture_id: str,
    background_tasks: BackgroundTasks,
):
    """Start the VantageCam pipeline for a capture."""
    capture_data = await _get_capture_by_id(capture_id)
    if not capture_data:
        raise HTTPException(status_code=404, detail=f"Capture {capture_id} not found")

    if not capture_data.get("video_path"):
        raise HTTPException(
            status_code=400,
            detail="Video file has not been uploaded yet",
        )

    if capture_data["status"] not in ("UPLOADING", "RETRYING"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot start pipeline from status {capture_data['status']}",
        )

    # Update status to QUEUED
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE vantagecam_captures 
            SET status = $1, updated_at = $2
            WHERE id = $3
            """,
            "QUEUED",
            datetime.utcnow(),
            capture_id,
        )

    # Schedule background task via job manager
    background_tasks.add_task(
        job_manager.start_pipeline,
        capture_id=capture_id,
        video_path=capture_data["video_path"],
        gps_file_path=capture_data.get("gps_file_path"),
        storage_base="output/vantagecam/captures",
        device=capture_data["device"],
        tier=capture_data["tier"],
    )

    return {
        "capture_id": capture_id,
        "status": "queued",
        "message": "Pipeline execution started in background",
    }


@router.get("/captures/{capture_id}/artifacts")
async def list_capture_artifacts(capture_id: str):
    """List all artifacts produced by a capture."""
    capture_data = await _get_capture_by_id(capture_id)
    if not capture_data:
        raise HTTPException(status_code=404, detail=f"Capture {capture_id} not found")

    pool = get_pool()
    async with pool.acquire() as conn:
        artifacts_rows = await conn.fetch(
            "SELECT * FROM vantagecam_artifacts WHERE capture_id = $1",
            capture_id,
        )

    return {
        "capture_id": capture_id,
        "artifacts": [
            {
                "id": a["id"],
                "type": a["artifact_type"],
                "file_path": a["file_path"],
                "file_size_bytes": a["file_size_bytes"],
                "created_at": a["created_at"],
            }
            for a in artifacts_rows
        ],
    }


@router.get("/captures/{capture_id}/manifest")
async def get_capture_manifest(capture_id: str):
    """Get the manifest.json for a completed capture."""
    capture_data = await _get_capture_by_id(capture_id)
    if not capture_data:
        raise HTTPException(status_code=404, detail=f"Capture {capture_id} not found")

    # Load manifest from storage
    manifest_path = Path(capture_data["storage_dir"]) / "out" / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Manifest not found. Pipeline may not have completed yet.",
        )

    with open(manifest_path, "r") as f:
        manifest = json.load(f)

    return manifest


@router.delete("/captures/{capture_id}")
async def delete_capture(capture_id: str):
    """Delete a capture and its associated files."""
    capture_data = await _get_capture_by_id(capture_id)
    if not capture_data:
        raise HTTPException(status_code=404, detail=f"Capture {capture_id} not found")

    # Delete from database (cascades to stages, artifacts, quality report)
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "DELETE FROM vantagecam_captures WHERE id = $1",
            capture_id,
        )

    # Clean up storage directory
    import shutil
    storage_path = Path(capture_data["storage_dir"])
    if storage_path.exists():
        shutil.rmtree(storage_path)

    return {
        "capture_id": capture_id,
        "status": "deleted",
        "message": "Capture and its files have been removed",
    }
