"""Phase 4 verification test — Georeferencing & Quality Gate (Stages 6-7)."""

import json
from pathlib import Path
import tempfile
import numpy as np
from stages.stage6_georef import run_stage6_georef
from stages.stage7_quality_gate import run_stage7_quality_gate, compute_quality_metrics, evaluate_quality
from tiers import get_tier
from models import QualityVerdict


def test_stage6_georef():
    """Test Stage 6: Georeferencing."""
    print("\n=== TEST: Stage 6 Georeferencing ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        output_dir = tmpdir / "stage6"
        
        mesh_data = {"mesh_triangles_count": 10000}
        dense_data = {"dense_points": np.random.randn(5000, 3)}
        sfm_data = {}
        
        tier = get_tier("standard")
        
        result = run_stage6_georef(
            mesh_data, dense_data, sfm_data,
            output_dir, tier, "test_georef",
            utm_zone=44
        )
        
        assert result["stage6_complete"] == True
        assert "orthomosaic_file" in result
        assert "dsm_file" in result
        assert "laz_file" in result
        assert "crs" in result
        
        print(f"  ✓ Georeferencing complete")
        print(f"    Orthomosaic: {result['orthomosaic_file']}")
        print(f"    DSM: {result['dsm_file']}")
        print(f"    Point cloud: {result['laz_file']}")
        print(f"    CRS: {result['crs']['crs']}")
        
        print(f"✓ Stage 6 test PASSED")


def test_quality_metrics():
    """Test quality metric computation."""
    print("\n=== TEST: Quality Metrics ===")
    
    metrics = compute_quality_metrics(
        sparse_points=1000,
        dense_points=100000,
        mesh_triangles=50000,
        splat_count=100000,
        registered_frames_ratio=0.85,
        reprojection_error=0.8,
        ssim_score=0.88,
        frame_count=100,
    )
    
    assert metrics.sparse_points_count == 1000
    assert metrics.dense_points_count == 100000
    assert metrics.mesh_triangles_count == 50000
    assert metrics.registered_frames_ratio == 0.85
    
    print(f"  ✓ Metrics computed correctly")
    print(f"    Sparse: {metrics.sparse_points_count}")
    print(f"    Dense: {metrics.dense_points_count}")
    print(f"    Mesh: {metrics.mesh_triangles_count}")
    print(f"    Registration: {metrics.registered_frames_ratio:.1%}")
    print(f"    SSIM: {metrics.held_out_ssim:.3f}")
    
    print(f"✓ Quality metrics test PASSED")


def test_quality_evaluation():
    """Test quality gate evaluation."""
    print("\n=== TEST: Quality Evaluation ===")
    
    # Test PASS verdict
    good_metrics = compute_quality_metrics(
        sparse_points=5000,
        dense_points=100000,
        mesh_triangles=100000,
        splat_count=100000,
        registered_frames_ratio=0.90,
        reprojection_error=0.8,
        ssim_score=0.88,
    )
    
    tier = get_tier("standard")
    verdict, strategy = evaluate_quality(good_metrics, tier)
    
    print(f"  Test 1: Good reconstruction")
    print(f"    Verdict: {verdict.value}")
    assert verdict == QualityVerdict.PASS
    
    # Test RETRY verdict
    poor_metrics = compute_quality_metrics(
        sparse_points=500,
        dense_points=10000,
        mesh_triangles=1000,
        splat_count=10000,
        registered_frames_ratio=0.60,
        reprojection_error=3.0,
        ssim_score=0.60,
    )
    
    verdict, strategy = evaluate_quality(poor_metrics, tier)
    
    print(f"  Test 2: Poor reconstruction")
    print(f"    Verdict: {verdict.value}")
    print(f"    Retry strategy: {strategy}")
    assert verdict == QualityVerdict.RETRY
    assert strategy is not None
    
    print(f"✓ Quality evaluation test PASSED")


def test_stage7_quality_gate():
    """Test Stage 7: Quality gate."""
    print("\n=== TEST: Stage 7 Quality Gate ===")
    
    sfm_data = {"sparse_points_count": 1000}
    dense_data = {"dense_points_count": 100000}
    mesh_data = {"mesh_triangles_count": 50000}
    splat_data = {"splat_count": 100000}
    
    tier = get_tier("standard")
    
    result = run_stage7_quality_gate(
        sfm_data, dense_data, mesh_data, splat_data,
        tier, "test_qgate", attempt=1, max_attempts=3
    )
    
    assert result["stage7_complete"] == True
    assert "verdict" in result
    assert "metrics" in result
    assert result["attempt"] == 1
    assert result["max_attempts"] == 3
    
    print(f"  ✓ Quality gate complete")
    print(f"    Verdict: {result['verdict']}")
    print(f"    Attempt: {result['attempt']}/{result['max_attempts']}")
    if result.get("retry_strategy"):
        print(f"    Retry strategy: {result['retry_strategy']}")
    
    print(f"✓ Stage 7 test PASSED")


def test_stages_imports():
    """Test that all Stage 6-7 modules can be imported."""
    print("\n=== TEST: Stage Imports ===")
    
    try:
        from stages import stage6_georef
        from stages import stage7_quality_gate
        
        print(f"  ✓ stage6_georef imported")
        print(f"  ✓ stage7_quality_gate imported")
        
        assert hasattr(stage6_georef, 'run_stage6_georef')
        assert hasattr(stage7_quality_gate, 'run_stage7_quality_gate')
        
        print("✓ Stage imports test PASSED")
    
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        raise


def test_tier_quality_thresholds():
    """Test tier-specific quality thresholds."""
    print("\n=== TEST: Tier Quality Thresholds ===")
    
    from stages.stage7_quality_gate import evaluate_quality
    
    # Create metrics that should PASS in Lite but FAIL in Premium
    marginal_metrics = compute_quality_metrics(
        sparse_points=500,
        dense_points=5000,
        mesh_triangles=5000,
        splat_count=5000,
        registered_frames_ratio=0.75,
        reprojection_error=2.0,
        ssim_score=0.75,
    )
    
    lite = get_tier("lite")
    standard = get_tier("standard")
    premium = get_tier("premium")
    
    lite_verdict, _ = evaluate_quality(marginal_metrics, lite)
    standard_verdict, _ = evaluate_quality(marginal_metrics, standard)
    premium_verdict, _ = evaluate_quality(marginal_metrics, premium)
    
    print(f"  Marginal metrics evaluation:")
    print(f"    Lite verdict: {lite_verdict.value}")
    print(f"    Standard verdict: {standard_verdict.value}")
    print(f"    Premium verdict: {premium_verdict.value}")
    
    # Lite should be more permissive than Premium
    assert lite_verdict in [QualityVerdict.PASS, QualityVerdict.DEGRADED]
    assert premium_verdict != QualityVerdict.PASS
    
    print(f"✓ Tier quality thresholds test PASSED")


def print_summary():
    """Print Phase 4 summary."""
    print("\n" + "=" * 60)
    print("PHASE 4 SUMMARY — Georeferencing & Quality Gate")
    print("=" * 60)
    print("""
Created files:
  - vantagecam/stages/stage6_georef.py (Georeferencing)
  - vantagecam/stages/stage7_quality_gate.py (Quality gate)

Key features:
  Stage 6: Orthomosaic generation (GeoTIFF), DSM generation,
           LAZ point cloud export, CRS metadata
  Stage 7: Quality metric computation, threshold evaluation,
           Retry ladder with 3 escalating strategies

Quality gate verdicts:
  - PASS: Meets all thresholds
  - RETRY: Failed thresholds, will retry with adjusted parameters
  - DEGRADED: Marginal quality, accepted for lower tiers
  - FAIL: Failed thresholds, max retries exceeded

Retry strategies:
  1. increase_keyframes — Add more frames
  2. increase_depth_confidence — Stricter multi-view consensus
  3. increase_frames_and_masking — More frames + SegFormer masking
  4. restart_with_validation — Full restart with logging

GIS Integration:
  - Orthomosaic: Top-down georeferenced image (GeoTIFF)
  - DSM: Elevation model (GeoTIFF)
  - LAZ/PLY: Point cloud (LAS/LiDAR format)
  - CRS: UTM coordinate system (configurable zone)

Tier-specific thresholds:
  - Lite: Permissive (60% registration, 3px error, 500k points min)
  - Standard: Balanced (70% registration, 2px error, 1M points min)
  - Premium: Strict (85% registration, 1.5px error, 50M points min)
  - Premium Advanced: Very strict (90% registration, 1px error, 1B points min)

Next: Phase 5 — Export & Orchestrator (Stage 8 + State Machine)
""")


if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 4 VERIFICATION TEST — VantageCam v1")
    print("=" * 60)
    
    try:
        test_stages_imports()
        test_quality_metrics()
        test_quality_evaluation()
        test_tier_quality_thresholds()
        test_stage6_georef()
        test_stage7_quality_gate()
        
        print_summary()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
