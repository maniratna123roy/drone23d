"""Phase 1 verification test for VantageCam v1 models, tiers, and storage."""

import json
from pathlib import Path
from datetime import datetime, timezone
from models import (
    Capture, CaptureStatus, StageName, StageStatus, StageRecord,
    QualityMetrics, QualityReport, QualityVerdict,
    CreateCaptureRequest, StartCaptureRequest
)
from tiers import get_tier, list_tiers
from storage import StorageManager


def test_models():
    """Test Pydantic model creation and serialization."""
    print("\n=== TEST: Models ===")
    
    # Create a capture
    capture = Capture(
        id="cap_test_001",
        source_system="vantage_spatial_twin",
        source_id="inspection_uuid_123",
        tier="standard",
        status=CaptureStatus.CREATED,
        video_filename="flight_001.mp4",
        video_size_bytes=1_000_000_000,
        video_duration_s=120.0,
        video_resolution="3840x2160",
        video_fps=30.0,
        has_gps=True,
    )
    
    # Add stage records
    capture.stages = [
        StageRecord(stage=StageName.STAGE_0_PROBE, title="Probe Input"),
        StageRecord(stage=StageName.STAGE_1_FRAMES, title="Parallax Keyframes"),
        StageRecord(stage=StageName.STAGE_2_MASKING, title="Dynamic Masking"),
        StageRecord(stage=StageName.STAGE_3_SFM, title="Structure-from-Motion"),
        StageRecord(stage=StageName.STAGE_4_DENSE, title="Dense Reconstruction"),
        StageRecord(stage=StageName.STAGE_5A_MESH, title="Mesh Generation"),
        StageRecord(stage=StageName.STAGE_5B_SPLATS, title="Gaussian Splats"),
        StageRecord(stage=StageName.STAGE_6_GEOREF, title="Georeferencing"),
        StageRecord(stage=StageName.STAGE_7_QUALITY_GATE, title="Quality Gate"),
        StageRecord(stage=StageName.STAGE_8_EXPORT, title="Export Artifacts"),
    ]
    
    # Serialize to JSON
    capture_dict = capture.model_dump(mode='json')
    print(f"✓ Created capture: {capture.id}")
    print(f"  - Status: {capture.status}")
    print(f"  - Tier: {capture.tier}")
    print(f"  - Stages: {len(capture.stages)}")
    print(f"  - JSON size: {len(json.dumps(capture_dict))} bytes")
    
    # Test quality report
    metrics = QualityMetrics(
        registered_frames_ratio=0.92,
        mean_reprojection_error_px=0.8,
        sparse_points_count=120_000,
        dense_points_count=5_000_000,
        mesh_triangles_count=150_000,
        held_out_ssim=0.89,
    )
    report = QualityReport(
        job_id="cap_test_001",
        attempt=1,
        metrics=metrics,
        verdict=QualityVerdict.PASS,
    )
    print(f"✓ Quality report: {report.verdict} (attempt {report.attempt})")
    print(f"  - Registered frames: {metrics.registered_frames_ratio*100:.1f}%")
    print(f"  - Reprojection error: {metrics.mean_reprojection_error_px:.2f} px")
    
    # Test request models
    create_req = CreateCaptureRequest(tier="premium", source_id="test_123")
    start_req = StartCaptureRequest(tier="premium", gps_file_ref="gps.csv")
    print(f"✓ Request models serialize correctly")
    
    print("✓ All model tests PASSED")


def test_tiers():
    """Test tier configurations."""
    print("\n=== TEST: Tiers ===")
    
    tiers = list_tiers()
    print(f"✓ Available tiers: {len(tiers)}")
    
    for tier_id, tier in tiers.items():
        print(f"  - {tier.name} (id={tier_id})")
        print(f"    Frame budget: {tier.frame_budget}")
        print(f"    Max retries: {tier.qa_max_retries}")
        print(f"    Mesh triangles: {tier.mesh_triangle_budget:,}")
        print(f"    Splat target: {tier.splat_count_target:,}")
        print(f"    Dynamic masks: {tier.dynamic_masks}")
    
    # Test lookup
    standard = get_tier("standard")
    assert standard.id == "standard"
    assert standard.frame_budget == 400
    
    premium = get_tier("PREMIUM")  # Case-insensitive
    assert premium.id == "premium"
    
    default = get_tier("nonexistent")
    assert default.id == "standard"
    
    print(f"✓ Tier lookup works (including case-insensitive)")
    print("✓ All tier tests PASSED")


def test_storage():
    """Test storage manager directory structure."""
    print("\n=== TEST: Storage Manager ===")
    
    # Create a temporary test directory
    test_base = Path("output/vantagecam_test")
    storage = StorageManager(test_base)
    
    capture_id = "cap_test_001"
    
    # Get subdirectories
    subdirs = storage.get_subdirs(capture_id)
    print(f"✓ Created capture directory structure:")
    for name, path in subdirs.items():
        assert path.exists(), f"Directory {name} not created!"
        try:
            rel_path = path.relative_to(test_base)
        except ValueError:
            rel_path = path.relative_to(Path.cwd())
        print(f"  - {name}: {rel_path}")
    
    # Test artifact path
    artifact_path = storage.artifact_path(capture_id, "glb", "model.glb")
    assert artifact_path.name == "model.glb" and "out" in str(artifact_path)
    print(f"✓ Artifact path: .../{artifact_path.parent.name}/{artifact_path.name}")
    
    # Test manifest save/load
    manifest = {
        "capture_id": capture_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "artifacts": [
            {"kind": "glb", "filename": "model.glb"},
            {"kind": "laz", "filename": "pointcloud.laz"},
        ]
    }
    saved_path = storage.save_manifest(capture_id, manifest)
    assert saved_path.exists()
    try:
        rel_saved = saved_path.relative_to(test_base)
    except ValueError:
        rel_saved = saved_path.relative_to(Path.cwd())
    print(f"✓ Saved manifest to {rel_saved}")
    
    loaded = storage.load_manifest(capture_id)
    assert loaded is not None
    assert loaded["capture_id"] == capture_id
    print(f"✓ Loaded manifest: {len(loaded.get('artifacts', []))} artifacts")
    
    # Cleanup
    cap_dir_path = storage.get_capture_dir(capture_id)
    storage.cleanup_capture(capture_id, keep_artifacts=False)
    assert not cap_dir_path.exists(), "Cleanup did not remove capture directory"
    print(f"✓ Cleanup removed capture directory")
    
    # Also clean up test base
    import shutil
    if test_base.exists():
        shutil.rmtree(test_base)
    
    print("✓ All storage tests PASSED")


def print_sample_capture():
    """Print a sample capture for visual inspection."""
    print("\n=== SAMPLE: Capture JSON ===")
    
    capture = Capture(
        id="cap_demo_001",
        tier="premium",
        video_filename="flight_demo.mp4",
        video_resolution="4096x2160",
        has_gps=True,
    )
    capture.stages = [
        StageRecord(stage=s, title=s.value) 
        for s in StageName
    ]
    
    print(json.dumps(capture.model_dump(mode='json'), indent=2)[:1000])
    print("...")


if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 1 VERIFICATION TEST — VantageCam v1")
    print("=" * 60)
    
    try:
        test_models()
        test_tiers()
        test_storage()
        print_sample_capture()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
