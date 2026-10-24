"""VantageCam Background Job Manager.

Handles background pipeline execution, database updates, error handling,
and real-time WebSocket progress broadcasting.
Uses asyncpg directly (no ORM dependency).
"""

import asyncio
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional
import time

from backend.db.connection import get_pool
from backend.ws.vantagecam_manager import vantagecam_ws_manager
from vantagecam.orchestrator import PipelineOrchestrator


class VantageCamJobManager:
    """Manages VantageCam pipeline execution as background tasks."""

    def __init__(self):
        self.running_jobs = {}  # capture_id -> asyncio.Task

    async def start_pipeline(
        self,
        capture_id: str,
        video_path: str,
        gps_file_path: Optional[str],
        storage_base: str,
        device: str,
        tier: str,
    ) -> None:
        """Start the VantageCam pipeline for a capture."""
        pool = get_pool()
        pipeline_start_time = time.time()
        
        try:
            # Update status to PROCESSING
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE vantagecam_captures SET status = $1, updated_at = $2 WHERE id = $3",
                    "PROCESSING",
                    datetime.utcnow(),
                    capture_id,
                )

            # Broadcast status update
            await vantagecam_ws_manager.broadcast_status_update(
                capture_id=capture_id,
                status="PROCESSING",
                progress_percent=0,
                current_stage="probe",
            )

            # Initialize orchestrator
            storage_path = Path(storage_base)
            orchestrator = PipelineOrchestrator(
                storage_base=storage_path,
                device=device,
            )

            # Create capture in orchestrator
            orch_capture = orchestrator.create_capture(
                tier=tier,
                source_id=capture_id,
            )

            print(f"[{capture_id}] Starting pipeline: {video_path}")

            # Broadcast initial status
            await vantagecam_ws_manager.broadcast_stage_start(
                capture_id=capture_id,
                stage_index=0,
                stage_name="probe",
            )

            # Run pipeline in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._run_pipeline_sync,
                orchestrator,
                orch_capture,
                video_path,
                gps_file_path,
                capture_id,
            )

            # Calculate total duration
            total_duration = time.time() - pipeline_start_time

            # Update database with result
            await self._update_from_result(capture_id, result)

            # Broadcast completion
            await vantagecam_ws_manager.broadcast_pipeline_complete(
                capture_id=capture_id,
                total_duration_seconds=total_duration,
                status="COMPLETED",
                quality_verdict=result.get("quality_report", {}).get("verdict"),
                artifacts=[
                    {
                        "type": a.get("type"),
                        "path": a.get("path"),
                        "size_bytes": a.get("size_bytes"),
                    }
                    for a in result.get("artifacts", [])
                ],
            )

        except Exception as e:
            print(f"[ERROR] Pipeline failed for {capture_id}: {str(e)}")
            traceback.print_exc()
            
            # Calculate attempt from database
            attempt = 1
            pool = get_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT attempt_count, max_attempts FROM vantagecam_captures WHERE id = $1",
                    capture_id,
                )
                if row:
                    attempt = row["attempt_count"] + 1
                    max_attempts = row["max_attempts"]
                    
                    # Broadcast failure event
                    await vantagecam_ws_manager.broadcast_pipeline_failed(
                        capture_id=capture_id,
                        error_message=str(e),
                        attempt=attempt,
                        max_attempts=max_attempts,
                    )

            await self._handle_pipeline_error(capture_id, str(e))

    def _run_pipeline_sync(
        self,
        orchestrator: PipelineOrchestrator,
        orch_capture,
        video_path: str,
        gps_file_path: Optional[str],
        capture_id: str,
    ) -> dict:
        """Synchronous pipeline runner (runs in executor)."""
        try:
            video_file = Path(video_path)
            gps_file = Path(gps_file_path) if gps_file_path else None

            result = orchestrator.run_pipeline(
                capture=orch_capture,
                video_path=video_file,
                gps_file=gps_file,
            )

            print(f"[{capture_id}] Pipeline completed successfully")
            return result

        except Exception as e:
            print(f"[{capture_id}] Pipeline execution error: {str(e)}")
            raise

    async def _update_from_result(self, capture_id: str, result: dict) -> None:
        """Update database with pipeline results."""
        pool = get_pool()
        try:
            async with pool.acquire() as conn:
                # Update capture status
                status = result.get("status", "COMPLETED")
                await conn.execute(
                    "UPDATE vantagecam_captures SET status = $1, updated_at = $2 WHERE id = $3",
                    status,
                    datetime.utcnow(),
                    capture_id,
                )

                print(f"[{capture_id}] Database updated with pipeline results")

        except Exception as e:
            print(f"[ERROR] Failed to update database for {capture_id}: {str(e)}")
            raise

    async def _handle_pipeline_error(self, capture_id: str, error_message: str) -> None:
        """Handle pipeline error and update database."""
        pool = get_pool()
        try:
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE vantagecam_captures SET status = $1, error_message = $2, updated_at = $3 WHERE id = $4",
                    "FAILED",
                    error_message,
                    datetime.utcnow(),
                    capture_id,
                )
                print(f"[{capture_id}] Capture marked as FAILED in database")
        except Exception as e:
            print(f"[ERROR] Failed to handle error for {capture_id}: {str(e)}")

    async def get_job_status(self, capture_id: str) -> dict:
        """Get current status of a job."""
        pool = get_pool()
        async with pool.acquire() as conn:
            capture_row = await conn.fetchrow(
                "SELECT * FROM vantagecam_captures WHERE id = $1",
                capture_id,
            )
            
            if not capture_row:
                return {"status": "not_found"}

            stages_result = await conn.fetch(
                "SELECT * FROM vantagecam_stages WHERE capture_id = $1",
                capture_id,
            )
            
            completed = sum(1 for s in stages_result if s["status"] == "COMPLETED")
            total = 10

            return {
                "status": capture_row["status"],
                "progress_percent": (completed / total) * 100,
                "stages_completed": completed,
                "stages_total": total,
                "error_message": capture_row.get("error_message"),
            }


# Global job manager instance
job_manager = VantageCamJobManager()
