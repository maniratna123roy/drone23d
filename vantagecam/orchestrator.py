"""Orchestrator — VantageCam pipeline state machine with retry logic.

Manages the 10-stage pipeline, tracks state transitions, handles retries,
and ensures all stages complete correctly before proceeding to the next.

Real-world analogy: Like a project manager overseeing a construction site,
keeping track of progress, managing rework, and ensuring quality at each step.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from enum import Enum

from .models import Capture, CaptureStatus, StageName, StageStatus, StageRecord
from .tiers import get_tier
from .storage import StorageManager
from .stages.stage0_probe import run_stage0_probe
from .stages.stage1_frames import run_stage1_frames
from .stages.stage2_masking import run_stage2_masking
from .stages.stage3_sfm import run_stage3_sfm
from .stages.stage4_dense import run_stage4_dense
from .stages.stage5a_mesh import run_stage5a_mesh
from .stages.stage5b_splats import run_stage5b_splats
from .stages.stage6_georef import run_stage6_georef
from .stages.stage7_quality_gate import run_stage7_quality_gate
from .stages.stage8_export import run_stage8_export


class OrchestratorError(Exception):
    """Raised when orchestration fails."""
    pass


class RetryStrategy(str, Enum):
    """Retry escalation strategies."""
    INCREASE_KEYFRAMES = "increase_keyframes"
    INCREASE_DEPTH = "increase_depth_confidence"
    ENABLE_MASKING = "increase_frames_and_masking"
    RESTART = "restart_with_validation"


class PipelineOrchestrator:
    """Manages VantageCam pipeline execution with state machine."""
    
    def __init__(
        self,
        storage_base: Path = Path("output/vantagecam"),
        device: str = "cpu",
    ):
        """Initialize orchestrator.
        
        Args:
            storage_base: Base directory for all captures
            device: 'cpu' or 'cuda'
        """
        self.storage = StorageManager(storage_base)
        self.device = device
        self.current_capture: Optional[Capture] = None
    
    def create_capture(
        self,
        source_system: str = "vantage_spatial_twin",
        source_id: Optional[str] = None,
        tier: str = "standard",
    ) -> Capture:
        """Create a new capture job.
        
        Args:
            source_system: Source system identifier
            source_id: Source-specific identifier
            tier: Quality tier (lite, standard, premium, premium_advanced)
            
        Returns:
            New Capture object
        """
        # Generate capture ID
        now = datetime.now(timezone.utc)
        capture_id = f"cap_{now.strftime('%Y%m%d_%H%M%S')}_vantage"
        
        capture = Capture(
            id=capture_id,
            source_system=source_system,
            source_id=source_id,
            tier=tier,
            status=CaptureStatus.CREATED,
            max_attempts=get_tier(tier).qa_max_retries + 1,
        )
        
        self.current_capture = capture
        print(f"[{capture_id}] Capture created: {tier} tier, {capture.max_attempts} max attempts")
        
        return capture
    
    def run_pipeline(
        self,
        capture: Capture,
        video_path: Path,
        gps_file: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Run the complete 10-stage pipeline.
        
        Args:
            capture: Capture object
            video_path: Path to input video
            gps_file: Optional GPS trajectory file
            
        Returns:
            Dict with pipeline results
        """
        self.current_capture = capture
        capture.status = CaptureStatus.PROCESSING
        
        tier_config = get_tier(capture.tier)
        subdirs = self.storage.get_subdirs(capture.id)
        
        print(f"\n{'='*60}")
        print(f"VANTAGECAM PIPELINE — {capture.id}")
        print(f"{'='*60}")
        print(f"Tier: {capture.tier} ({tier_config.frame_budget} frames)")
        print(f"Max attempts: {capture.max_attempts}")
        
        # Retry loop
        for attempt in range(1, capture.max_attempts + 1):
            capture.attempt = attempt
            print(f"\n--- ATTEMPT {attempt}/{capture.max_attempts} ---\n")
            
            # Run stages 0-8
            try:
                # Stage 0: Probe
                if not self._run_stage(0, capture, lambda: run_stage0_probe(
                    video_path, capture.id
                ), subdirs):
                    raise OrchestratorError("Stage 0 probe failed")
                
                # Extract metadata from stage 0
                image_metadata = {
                    "width": 1920,
                    "height": 1080,
                    "fps": 30.0,
                }
                
                # Stage 1: Keyframe extraction
                if not self._run_stage(1, capture, lambda: run_stage1_frames(
                    subdirs["raw"], subdirs["frames"], tier_config, capture.id
                ), subdirs):
                    raise OrchestratorError("Stage 1 keyframe extraction failed")
                
                # Stage 2: Masking
                if not self._run_stage(2, capture, lambda: run_stage2_masking(
                    subdirs["frames"], subdirs["frames"],
                    tier_config, capture.id, device=self.device
                ), subdirs):
                    raise OrchestratorError("Stage 2 masking failed")
                
                # Stage 3: SfM
                stage3_result = None
                if not self._run_stage(3, capture, lambda: (
                    stage3_result := run_stage3_sfm(
                        subdirs["frames"], subdirs["work"],
                        gps_file, image_metadata, capture.id
                    )
                ), subdirs):
                    raise OrchestratorError("Stage 3 SfM failed")
                
                # Stage 4: Dense
                stage4_result = None
                if not self._run_stage(4, capture, lambda: (
                    stage4_result := run_stage4_dense(
                        subdirs["frames"], subdirs["work"],
                        stage3_result or {}, capture.id, use_neural_depth=False
                    )
                ), subdirs):
                    raise OrchestratorError("Stage 4 dense failed")
                
                # Stage 5a: Mesh
                stage5a_result = None
                if not self._run_stage(5, capture, lambda: (
                    stage5a_result := run_stage5a_mesh(
                        stage4_result or {}, subdirs["work"],
                        tier_config, capture.id
                    )
                ), subdirs, stage_name="5a"):
                    raise OrchestratorError("Stage 5a mesh failed")
                
                # Stage 5b: Splats
                stage5b_result = None
                if not self._run_stage(5, capture, lambda: (
                    stage5b_result := run_stage5b_splats(
                        stage4_result or {}, subdirs["work"],
                        tier_config, capture.id
                    )
                ), subdirs, stage_name="5b"):
                    raise OrchestratorError("Stage 5b splats failed")
                
                # Stage 6: Georeferencing
                if not self._run_stage(6, capture, lambda: run_stage6_georef(
                    stage5a_result or {}, stage4_result or {},
                    stage3_result or {}, subdirs["out"],
                    tier_config, capture.id
                ), subdirs):
                    raise OrchestratorError("Stage 6 georeferencing failed")
                
                # Stage 7: Quality Gate
                stage7_result = None
                if not self._run_stage(7, capture, lambda: (
                    stage7_result := run_stage7_quality_gate(
                        stage3_result or {}, stage4_result or {},
                        stage5a_result or {}, stage5b_result or {},
                        tier_config, capture.id,
                        attempt=attempt, max_attempts=capture.max_attempts
                    )
                ), subdirs):
                    raise OrchestratorError("Stage 7 quality gate failed")
                
                # Check quality gate verdict
                verdict = stage7_result.get("verdict") if stage7_result else "unknown"
                
                if verdict == "pass":
                    print(f"\n✓ Quality gate PASSED — proceeding to export")
                
                elif verdict == "retry":
                    if attempt < capture.max_attempts:
                        print(f"\n⚠ Quality gate RETRY — attempt {attempt + 1}")
                        continue
                    else:
                        print(f"\n❌ Quality gate FAILED after {attempt} attempts")
                        capture.status = CaptureStatus.FAILED
                        return {"success": False, "reason": "Quality gate failed after max attempts"}
                
                elif verdict == "degraded":
                    print(f"\n⚠ Quality gate DEGRADED — proceeding with caution")
                
                else:
                    print(f"\n❌ Quality gate FAIL")
                    capture.status = CaptureStatus.FAILED
                    return {"success": False, "reason": "Quality gate failed"}
                
                # Stage 8: Export
                if not self._run_stage(8, capture, lambda: run_stage8_export(
                    capture.id, capture.model_dump(mode="json"),
                    subdirs["work"], subdirs["out"],
                    quality_report=stage7_result
                ), subdirs):
                    raise OrchestratorError("Stage 8 export failed")
                
                # All stages passed!
                print(f"\n{'='*60}")
                print(f"✓ PIPELINE COMPLETE")
                print(f"{'='*60}")
                
                capture.status = CaptureStatus.COMPLETED
                return {
                    "success": True,
                    "capture_id": capture.id,
                    "attempt": attempt,
                }
            
            except OrchestratorError as e:
                print(f"\n❌ Pipeline error: {e}")
                if attempt < capture.max_attempts:
                    print(f"Retrying (attempt {attempt + 1}/{capture.max_attempts})...")
                    continue
                else:
                    capture.status = CaptureStatus.FAILED
                    return {"success": False, "reason": str(e), "attempt": attempt}
        
        # Max attempts exceeded
        capture.status = CaptureStatus.FAILED
        return {"success": False, "reason": "Max attempts exceeded"}
    
    def _run_stage(
        self,
        stage_num: int,
        capture: Capture,
        stage_func,
        subdirs: Dict[str, Path],
        stage_name: Optional[str] = None,
    ) -> bool:
        """Run a single stage and update capture state.
        
        Args:
            stage_num: Stage number (0-8)
            capture: Capture object
            stage_func: Function to run
            subdirs: Stage subdirectories
            stage_name: Optional override name (e.g., "5a")
            
        Returns:
            True if stage passed, False otherwise
        """
        name = stage_name or str(stage_num)
        
        try:
            capture.current_stage = StageName(f"stage{name.replace('a', '_mesh').replace('b', '_splats')}")
        except:
            pass
        
        try:
            result = stage_func()
            
            if not result.get(f"stage{name}_complete", False):
                print(f"  ❌ Stage {name} FAILED: {result.get('error', 'unknown error')}")
                return False
            
            print(f"  ✓ Stage {name} PASSED")
            return True
        
        except Exception as e:
            print(f"  ❌ Stage {name} ERROR: {e}")
            import traceback
            traceback.print_exc()
            return False


def run_full_pipeline(
    video_path: Path,
    tier: str = "standard",
    gps_file: Optional[Path] = None,
    source_id: Optional[str] = None,
    storage_base: Path = Path("output/vantagecam"),
    device: str = "cpu",
) -> Dict[str, Any]:
    """Run the complete VantageCam pipeline.
    
    Args:
        video_path: Input video file
        tier: Quality tier
        gps_file: Optional GPS trajectory
        source_id: Source identifier
        storage_base: Storage base directory
        device: 'cpu' or 'cuda'
        
    Returns:
        Pipeline result dict
    """
    orchestrator = PipelineOrchestrator(storage_base, device)
    
    capture = orchestrator.create_capture(
        source_id=source_id,
        tier=tier,
    )
    
    result = orchestrator.run_pipeline(capture, video_path, gps_file)
    
    return result


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python orchestrator.py <video_path> [tier] [gps_file]")
        sys.exit(1)
    
    video = Path(sys.argv[1])
    tier = sys.argv[2] if len(sys.argv) > 2 else "standard"
    gps = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    
    result = run_full_pipeline(video, tier=tier, gps_file=gps)
    print("\n=== PIPELINE RESULT ===")
    print(json.dumps(result, indent=2, default=str))
