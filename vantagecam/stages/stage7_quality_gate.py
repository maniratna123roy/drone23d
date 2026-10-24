"""Stage 7: Quality Gate — Automated quality evaluation with retry ladder.

Polycam's reliability: After reconstruction, automatically check if the result 
meets quality thresholds. If not, retry with escalating strategies (more frames,
tighter masking, different parameters).

Real-world analogy: Like a factory quality inspector who either approves the product,
sends it back for rework, or escalates to a manager.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import numpy as np
from ..models import QualityMetrics, QualityReport, QualityVerdict


class QualityGateError(Exception):
    """Raised when quality evaluation fails."""
    pass


def compute_quality_metrics(
    sparse_points: int = 0,
    dense_points: int = 0,
    mesh_triangles: int = 0,
    splat_count: int = 0,
    registered_frames_ratio: float = 0.8,
    reprojection_error: float = 1.0,
    ssim_score: float = 0.85,
    frame_count: int = 100,
) -> QualityMetrics:
    """Compute quality metrics from reconstruction outputs.
    
    Args:
        sparse_points: Number of SfM points
        dense_points: Number of dense points
        mesh_triangles: Number of mesh triangles
        splat_count: Number of Gaussians
        registered_frames_ratio: Fraction of frames successfully registered
        reprojection_error: Mean reprojection error (pixels)
        ssim_score: Structural similarity (0-1)
        frame_count: Total frames in reconstruction
        
    Returns:
        QualityMetrics object
    """
    # Estimate ground sample distance (GSD)
    # Rough heuristic: better reconstructions have smaller GSD
    if dense_points > 0:
        gsd_cm = max(0.5, 50.0 / np.sqrt(dense_points / 100000))
    else:
        gsd_cm = 2.5
    
    return QualityMetrics(
        registered_frames_ratio=registered_frames_ratio,
        mean_reprojection_error_px=reprojection_error,
        sparse_points_count=sparse_points,
        dense_points_count=dense_points,
        mesh_triangles_count=mesh_triangles,
        mesh_hole_area_ratio=0.05,  # Estimate
        splat_count=splat_count,
        held_out_ssim=ssim_score,
        outlier_geometry_ratio=0.02,
        ground_sample_distance_cm=gsd_cm,
    )


def evaluate_quality(
    metrics: QualityMetrics,
    tier_config: "TierConfig",
) -> Tuple[QualityVerdict, Optional[str]]:
    """Evaluate if metrics meet tier thresholds.
    
    Args:
        metrics: Computed quality metrics
        tier_config: Tier configuration with quality thresholds
        
    Returns:
        Tuple of (verdict, retry_strategy or None)
    """
    # Base thresholds
    min_registered_ratio = 0.7
    max_reprojection_error = 2.0
    min_sparse_points = 100
    min_dense_points = 1000
    min_mesh_triangles = 100
    min_ssim = 0.70
    
    # Tier-specific adjustments
    if tier_config.id == "lite":
        min_registered_ratio = 0.60
        max_reprojection_error = 3.0
        min_dense_points = 500
        min_mesh_triangles = 50
        min_ssim = 0.60
    elif tier_config.id == "premium":
        min_registered_ratio = 0.85
        max_reprojection_error = 1.5
        min_dense_points = 50000
        min_mesh_triangles = 100000
        min_ssim = 0.80
    elif tier_config.id == "premium_advanced":
        min_registered_ratio = 0.90
        max_reprojection_error = 1.0
        min_dense_points = 1000000
        min_mesh_triangles = 500000
        min_ssim = 0.85
    
    issues = []
    
    # Check each metric
    if metrics.registered_frames_ratio < min_registered_ratio:
        issues.append(f"Low registration: {metrics.registered_frames_ratio:.1%} < {min_registered_ratio:.1%}")
    
    if metrics.mean_reprojection_error_px > max_reprojection_error:
        issues.append(f"High reprojection error: {metrics.mean_reprojection_error_px:.2f} > {max_reprojection_error:.2f} px")
    
    if metrics.sparse_points_count < min_sparse_points:
        issues.append(f"Few sparse points: {metrics.sparse_points_count} < {min_sparse_points}")
    
    if metrics.dense_points_count < min_dense_points:
        issues.append(f"Insufficient dense points: {metrics.dense_points_count} < {min_dense_points}")
    
    if metrics.mesh_triangles_count < min_mesh_triangles:
        issues.append(f"Low mesh resolution: {metrics.mesh_triangles_count} < {min_mesh_triangles}")
    
    if metrics.held_out_ssim < min_ssim:
        issues.append(f"Low SSIM: {metrics.held_out_ssim:.2f} < {min_ssim:.2f}")
    
    if len(issues) == 0:
        return QualityVerdict.PASS, None
    
    # Determine retry strategy
    if len(issues) == 1 and "registration" in issues[0]:
        return QualityVerdict.RETRY, "increase_keyframes"
    elif len(issues) == 1 and "dense points" in issues[0]:
        return QualityVerdict.RETRY, "increase_depth_confidence"
    elif len(issues) >= 2:
        return QualityVerdict.RETRY, "increase_frames_and_masking"
    else:
        return QualityVerdict.DEGRADED, None


def get_retry_strategy_adjustments(
    strategy: str,
    attempt: int,
) -> Dict[str, Any]:
    """Get parameter adjustments for a retry strategy.
    
    Args:
        strategy: Retry strategy name
        attempt: Current attempt number (1-indexed)
        
    Returns:
        Dict with parameter adjustments
    """
    adjustments = {}
    
    if strategy == "increase_keyframes":
        adjustments["frame_multiplier"] = 1.0 + (attempt - 1) * 0.5
        adjustments["parallax_threshold"] = max(0.5, 5.0 - (attempt - 1))
    
    elif strategy == "increase_depth_confidence":
        adjustments["depth_min_consistency_views"] = 1 + (attempt - 1)
        adjustments["depth_outlier_threshold"] = 0.02 / (attempt + 1)
    
    elif strategy == "increase_frames_and_masking":
        adjustments["frame_multiplier"] = 1.0 + (attempt - 1) * 0.3
        adjustments["enable_masking"] = True
        adjustments["masking_aggressive"] = attempt > 1
    
    elif strategy == "restart_with_validation":
        adjustments["validate_inputs"] = True
        adjustments["verbose_logging"] = True
        adjustments["frame_multiplier"] = 1.0
    
    return adjustments


def run_stage7_quality_gate(
    sfm_data: Dict[str, Any],
    dense_data: Dict[str, Any],
    mesh_data: Dict[str, Any],
    splat_data: Dict[str, Any],
    tier_config: "TierConfig",
    capture_id: str,
    attempt: int = 1,
    max_attempts: int = 3,
) -> Dict[str, Any]:
    """Run Stage 7: Quality gate evaluation.
    
    Args:
        sfm_data: SfM result from Stage 3
        dense_data: Dense result from Stage 4
        mesh_data: Mesh result from Stage 5a
        splat_data: Splat result from Stage 5b
        tier_config: Tier configuration
        capture_id: Capture job identifier
        attempt: Current attempt number (1-indexed)
        max_attempts: Maximum retry attempts
        
    Returns:
        Dict with quality gate results:
        - verdict: PASS, RETRY, DEGRADED, FAIL
        - metrics: QualityMetrics object
        - retry_strategy: if RETRY, the strategy to use
        - stage7_complete: whether to proceed
    """
    print(f"[{capture_id}] Stage 7: Quality Gate (Attempt {attempt}/{max_attempts})")
    
    try:
        # Step 1: Extract metrics from stages 3-5
        print(f"  Step 1: Computing quality metrics...")
        
        sparse_points = sfm_data.get("sparse_points_count", 0)
        dense_points = dense_data.get("dense_points_count", 0)
        mesh_triangles = mesh_data.get("mesh_triangles_count", 0)
        splat_count = splat_data.get("splat_count", 0)
        
        # Simulate metrics (in real implementation, these come from actual reconstruction)
        registered_ratio = 0.85 + np.random.randn() * 0.05
        reprojection_error = 1.0 + np.random.randn() * 0.2
        ssim_score = 0.85 + np.random.randn() * 0.05
        
        metrics = compute_quality_metrics(
            sparse_points=sparse_points,
            dense_points=dense_points,
            mesh_triangles=mesh_triangles,
            splat_count=splat_count,
            registered_frames_ratio=max(0.0, min(1.0, registered_ratio)),
            reprojection_error=max(0.0, reprojection_error),
            ssim_score=max(0.0, min(1.0, ssim_score)),
        )
        
        print(f"    Registration: {metrics.registered_frames_ratio:.1%}")
        print(f"    Reprojection error: {metrics.mean_reprojection_error_px:.2f} px")
        print(f"    Sparse points: {metrics.sparse_points_count}")
        print(f"    Dense points: {metrics.dense_points_count}")
        print(f"    Mesh triangles: {metrics.mesh_triangles_count}")
        print(f"    SSIM: {metrics.held_out_ssim:.3f}")
        
        # Step 2: Evaluate against thresholds
        print(f"  Step 2: Evaluating quality thresholds...")
        
        verdict, retry_strategy = evaluate_quality(metrics, tier_config)
        
        print(f"    Verdict: {verdict.value}")
        if retry_strategy:
            print(f"    Retry strategy: {retry_strategy}")
        
        # Step 3: Generate quality report
        report = QualityReport(
            job_id=capture_id,
            attempt=attempt,
            metrics=metrics,
            verdict=verdict,
            retry_strategy=retry_strategy,
        )
        
        # Step 4: Check if we should retry
        should_retry = (verdict == QualityVerdict.RETRY and attempt < max_attempts)
        
        if should_retry:
            print(f"  ⚠ Quality gate FAILED — will retry (attempt {attempt + 1}/{max_attempts})")
            adjustments = get_retry_strategy_adjustments(retry_strategy, attempt)
            print(f"    Adjustments: {json.dumps(adjustments, indent=6)}")
        
        elif verdict == QualityVerdict.PASS:
            print(f"  ✓ Quality gate PASSED")
        
        elif verdict == QualityVerdict.DEGRADED:
            print(f"  ⚠ Quality gate DEGRADED (accepted for low tier)")
        
        else:  # FAIL
            print(f"  ❌ Quality gate FAILED (final)")
        
        # Step 5: Save report
        report_dict = {
            "job_id": capture_id,
            "attempt": attempt,
            "verdict": verdict.value,
            "metrics": json.loads(metrics.model_dump_json()),
            "retry_strategy": retry_strategy,
        }
        
        return {
            "stage7_complete": True,
            "verdict": verdict.value,
            "metrics": metrics.model_dump(mode="json"),
            "retry_strategy": retry_strategy,
            "should_retry": should_retry,
            "attempt": attempt,
            "max_attempts": max_attempts,
        }
    
    except Exception as e:
        print(f"  ❌ Quality gate error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "stage7_complete": False,
            "error": str(e),
        }


if __name__ == "__main__":
    class MockTier:
        id = "standard"
    
    sfm = {"sparse_points_count": 700}
    dense = {"dense_points_count": 50000}
    mesh = {"mesh_triangles_count": 10000}
    splat = {"splat_count": 50000}
    
    result = run_stage7_quality_gate(sfm, dense, mesh, splat, MockTier(), "test_capture", attempt=1, max_attempts=3)
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2, default=str))
