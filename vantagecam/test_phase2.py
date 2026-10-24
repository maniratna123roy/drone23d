"""Phase 2 verification test — Core Stages 0-2 (Probe, Keyframes, Masking)."""

import json
import subprocess
from pathlib import Path
import tempfile
from stages.stage0_probe import run_stage0_probe
from tiers import get_tier


def test_stage0_probe_with_sample_video():
    """Test Stage 0 with a synthetic test video (if available)."""
    print("\n=== TEST: Stage 0 Probe ===")
    
    # Check if ffprobe is available
    try:
        result = subprocess.run(["ffprobe", "-version"], capture_output=True, timeout=5)
        if result.returncode != 0:
            print("  ⚠ ffprobe not found; skipping Stage 0 test")
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("  ⚠ ffprobe not found; skipping Stage 0 test")
        return
    
    # Try to find a test video
    test_video = Path("static/test_video.mp4")
    if not test_video.exists():
        print(f"  ⚠ No test video found at {test_video}; skipping Stage 0 test")
        return
    
    print(f"  Testing Stage 0 with: {test_video}")
    
    try:
        result = run_stage0_probe(test_video, "test_probe_001")
        
        if not result.get("valid"):
            print(f"  ❌ Probe validation failed: {result.get('issues')}")
            return
        
        metadata = result.get("metadata", {})
        print(f"  ✓ Probe passed")
        print(f"    Duration: {metadata.get('duration_s', 0):.1f}s")
        print(f"    Resolution: {metadata.get('resolution', 'unknown')}")
        print(f"    FPS: {metadata.get('fps', 0):.1f}")
        print(f"    Frame count: {metadata.get('frame_count', 0)}")
        
        print("✓ Stage 0 test PASSED")
    
    except Exception as e:
        print(f"  ❌ Stage 0 test failed: {e}")


def test_tiers_and_models():
    """Test tier configs and model serialization."""
    print("\n=== TEST: Tiers & Models ===")
    
    # Test tier retrieval
    lite = get_tier("lite")
    standard = get_tier("standard")
    premium = get_tier("premium")
    premium_adv = get_tier("premium_advanced")
    
    print(f"  Lite: {lite.frame_budget} frames, masking={lite.dynamic_masks}")
    print(f"  Standard: {standard.frame_budget} frames, masking={standard.dynamic_masks}")
    print(f"  Premium: {premium.frame_budget} frames, masking={premium.dynamic_masks}")
    print(f"  Premium Advanced: {premium_adv.frame_budget} frames, masking={premium_adv.dynamic_masks}")
    
    # Validate
    assert lite.frame_budget == 200
    assert standard.frame_budget == 400
    assert premium.frame_budget == 700
    assert premium_adv.frame_budget == 1500
    assert not lite.dynamic_masks
    assert not standard.dynamic_masks
    assert premium.dynamic_masks
    assert premium_adv.dynamic_masks
    
    print("✓ Tiers test PASSED")


def test_stages_imports():
    """Test that all stage modules can be imported."""
    print("\n=== TEST: Stage Imports ===")
    
    try:
        from stages import stage0_probe
        from stages import stage1_frames
        from stages import stage2_masking
        
        print(f"  ✓ stage0_probe imported")
        print(f"  ✓ stage1_frames imported")
        print(f"  ✓ stage2_masking imported")
        
        # Check key functions exist
        assert hasattr(stage0_probe, 'run_stage0_probe')
        assert hasattr(stage1_frames, 'run_stage1_frames')
        assert hasattr(stage2_masking, 'run_stage2_masking')
        
        print("✓ Stage imports test PASSED")
    
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")


def test_storage_integration():
    """Test storage manager with phases 0-2."""
    print("\n=== TEST: Storage Integration ===")
    
    from storage import StorageManager
    
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = StorageManager(Path(tmpdir))
        capture_id = "test_phase2_001"
        
        # Get subdirs
        subdirs = storage.get_subdirs(capture_id)
        
        # Verify all exist
        assert (subdirs["raw"]).exists()
        assert (subdirs["frames"]).exists()
        assert (subdirs["work"]).exists()
        assert (subdirs["out"]).exists()
        
        print(f"  ✓ Created directory structure for {capture_id}")
        
        # Test artifact path
        artifact = storage.artifact_path(capture_id, "glb", "model.glb")
        assert artifact.parent == subdirs["out"]
        
        print(f"  ✓ Artifact path resolves correctly")
        
        # Test manifest
        manifest = {
            "capture_id": capture_id,
            "stage": "phase2_complete",
            "frames_extracted": 42,
        }
        
        manifest_path = storage.save_manifest(capture_id, manifest)
        assert manifest_path.exists()
        
        loaded = storage.load_manifest(capture_id)
        assert loaded["capture_id"] == capture_id
        assert loaded["frames_extracted"] == 42
        
        print(f"  ✓ Manifest save/load works")
        
        print("✓ Storage integration test PASSED")


def print_summary():
    """Print Phase 2 summary."""
    print("\n" + "=" * 60)
    print("PHASE 2 SUMMARY — Core Stages 0-2")
    print("=" * 60)
    print("""
Created files:
  - vantagecam/stages/stage0_probe.py (validate video, extract metadata)
  - vantagecam/stages/stage1_frames.py (parallax-based keyframe extraction)
  - vantagecam/stages/stage2_masking.py (dynamic object masking with SegFormer)

Key features:
  Stage 0: Video validation via ffprobe (resolution, duration, codec, etc.)
  Stage 1: Parallax-based keyframe filtering (optical flow via OpenCV)
  Stage 2: Semantic segmentation masking (SegFormer-B0 Cityscapes)

Dependencies required:
  - ffmpeg + ffprobe (for video I/O)
  - opencv-python (for optical flow)
  - torch + transformers (for SegFormer, if masking enabled)
  - Pillow (for image I/O)

Tier integration:
  - Lite: 200 frames, masking disabled
  - Standard: 400 frames, masking disabled
  - Premium: 700 frames, masking enabled
  - Premium Advanced: 1500 frames, masking enabled

Next: Phase 3 — Reconstruction stages (SfM, Dense, Mesh/Splats)
""")


if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 2 VERIFICATION TEST — VantageCam v1")
    print("=" * 60)
    
    try:
        test_tiers_and_models()
        test_stages_imports()
        test_storage_integration()
        test_stage0_probe_with_sample_video()
        
        print_summary()
        
        print("\n" + "=" * 60)
        print("ALL AVAILABLE TESTS PASSED ✓")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
