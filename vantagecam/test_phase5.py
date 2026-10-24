"""Phase 5 verification test — Export & Orchestrator (Stage 8 + State Machine)."""

import json
from pathlib import Path
import tempfile
import shutil
import numpy as np
from PIL import Image
from stages.stage8_export import run_stage8_export, collect_artifacts, create_manifest
from orchestrator import PipelineOrchestrator
from tiers import get_tier


def create_test_artifacts_dir(tmpdir: Path) -> Path:
    """Create a temporary work directory with synthetic artifacts."""
    work_dir = tmpdir / "work"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    # Create synthetic mesh file (OBJ)
    mesh_path = work_dir / "mesh.obj"
    with open(mesh_path, "w") as f:
        f.write("# Test mesh\n")
        f.write("v 0.0 0.0 0.0\n")
        f.write("v 1.0 0.0 0.0\n")
        f.write("v 0.0 1.0 0.0\n")
        f.write("f 1 2 3\n")
    
    # Create synthetic point cloud (PLY)
    ply_path = work_dir / "splats.ply"
    with open(ply_path, "w") as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write("element vertex 10\n")
        f.write("property float x\n")
        f.write("property float y\n")
        f.write("property float z\n")
        f.write("end_header\n")
        for i in range(10):
            f.write(f"{i*0.1} {i*0.1} {i*0.1}\n")
    
    # Create synthetic splat file (binary)
    splat_path = work_dir / "scene.splat"
    with open(splat_path, "wb") as f:
        f.write(b"SPLAT" * 100)  # Dummy splat data
    
    # Create synthetic image (orthomosaic)
    ortho_path = work_dir / "orthomosaic.tif"
    img = Image.new("RGB", (100, 100), color=(100, 150, 200))
    img.save(ortho_path)
    
    # Create stage result metadata
    metadata_path = work_dir / "sfm_result.json"
    with open(metadata_path, "w") as f:
        json.dump({"sparse_points": 1000}, f)
    
    return work_dir


def test_stage8_export():
    """Test Stage 8: Export."""
    print("\n=== TEST: Stage 8 Export ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        work_dir = create_test_artifacts_dir(tmpdir)
        out_dir = tmpdir / "out"
        
        capture_data = {
            "id": "test_export_001",
            "tier": "standard",
            "source_system": "vantage_spatial_twin",
            "created_at": "2026-10-21T16:00:00Z",
        }
        
        quality_report = {
            "verdict": "pass",
            "attempt": 1,
        }
        
        result = run_stage8_export(
            "test_export_001",
            capture_data,
            work_dir,
            out_dir,
            quality_report=quality_report
        )
        
        assert result["stage8_complete"] == True
        assert result["artifact_count"] > 0
        assert result["total_size_bytes"] > 0
        
        # Verify manifest exists
        manifest_path = out_dir / "manifest.json"
        assert manifest_path.exists()
        
        manifest = json.load(open(manifest_path))
        assert manifest["capture"]["id"] == "test_export_001"
        assert len(manifest["artifacts"]) == result["artifact_count"]
        
        print(f"  ✓ Export complete: {result['artifact_count']} artifacts")
        print(f"    Total size: {result['total_size_bytes']/1000:.1f} KB")
        print(f"✓ Stage 8 test PASSED")


def test_artifact_collection():
    """Test artifact collection and hashing."""
    print("\n=== TEST: Artifact Collection ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        work_dir = create_test_artifacts_dir(tmpdir)
        out_dir = tmpdir / "out"
        out_dir.mkdir()
        
        artifacts = collect_artifacts(work_dir, out_dir)
        
        assert len(artifacts) > 0
        
        # Check artifact structure
        for art in artifacts:
            assert "id" in art
            assert "filename" in art
            assert "kind" in art
            assert "size_bytes" in art
            assert "sha256" in art
            
            # Verify SHA256 is 64 hex chars
            assert len(art["sha256"]) == 64
            
            print(f"  ✓ {art['filename']} ({art['size_bytes']} bytes)")
            print(f"    SHA256: {art['sha256'][:16]}...")
        
        print(f"✓ Artifact collection test PASSED")


def test_manifest_creation():
    """Test manifest creation."""
    print("\n=== TEST: Manifest Creation ===")
    
    capture_data = {
        "id": "test_manifest_001",
        "tier": "premium",
        "source_system": "vantage_spatial_twin",
        "crs": "EPSG:32644",
    }
    
    artifacts = [
        {
            "id": "art_000001",
            "filename": "mesh.obj",
            "kind": "mesh",
            "size_bytes": 1000,
            "sha256": "abc123" + "0"*58,
        },
        {
            "id": "art_000002",
            "filename": "scene.splat",
            "kind": "splat",
            "size_bytes": 5000,
            "sha256": "def456" + "0"*58,
        }
    ]
    
    quality_report = {
        "verdict": "pass",
        "attempt": 1,
        "metrics": {
            "registered_frames_ratio": 0.85,
            "mean_reprojection_error_px": 0.8,
        }
    }
    
    manifest = create_manifest(capture_data, artifacts, quality_report)
    
    assert manifest["capture"]["id"] == "test_manifest_001"
    assert manifest["capture"]["tier"] == "premium"
    assert len(manifest["artifacts"]) == 2
    assert manifest["metadata"]["total_artifacts"] == 2
    assert manifest["quality_gate"]["verdict"] == "pass"
    
    print(f"  ✓ Manifest created")
    print(f"    Capture: {manifest['capture']['id']}")
    print(f"    Artifacts: {manifest['metadata']['total_artifacts']}")
    print(f"    Total size: {manifest['metadata']['total_size_bytes']} bytes")
    
    print(f"✓ Manifest creation test PASSED")


def test_orchestrator_creation():
    """Test orchestrator initialization."""
    print("\n=== TEST: Orchestrator Creation ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        orchestrator = PipelineOrchestrator(tmpdir)
        
        capture = orchestrator.create_capture(
            source_id="test_source_001",
            tier="standard"
        )
        
        assert capture.id is not None
        assert capture.tier == "standard"
        assert capture.status.value == "created"
        assert capture.max_attempts == get_tier("standard").qa_max_retries + 1
        
        print(f"  ✓ Orchestrator created")
        print(f"    Capture ID: {capture.id}")
        print(f"    Tier: {capture.tier}")
        print(f"    Max attempts: {capture.max_attempts}")
        
        print(f"✓ Orchestrator creation test PASSED")


def test_stages_imports():
    """Test that Stage 8 and orchestrator modules can be imported."""
    print("\n=== TEST: Stage & Orchestrator Imports ===")
    
    try:
        from stages import stage8_export
        import orchestrator
        
        print(f"  ✓ stage8_export imported")
        print(f"  ✓ orchestrator imported")
        
        assert hasattr(stage8_export, 'run_stage8_export')
        assert hasattr(orchestrator, 'PipelineOrchestrator')
        assert hasattr(orchestrator, 'run_full_pipeline')
        
        print("✓ Imports test PASSED")
    
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        raise


def print_summary():
    """Print Phase 5 summary."""
    print("\n" + "=" * 60)
    print("PHASE 5 SUMMARY — Export & Orchestrator")
    print("=" * 60)
    print("""
Created files:
  - vantagecam/stages/stage8_export.py (Export artifacts & manifest)
  - vantagecam/orchestrator.py (Pipeline state machine)

Key features:
  Stage 8: Artifact collection, SHA256 hashing, manifest generation,
           web manifest creation, export summary
  Orchestrator: 10-stage state machine, retry loop, stage sequencing,
                quality gate integration, capture state tracking

Pipeline flow (with retry):
  0: Probe (validate video) → 1: Keyframes (parallax) → 2: Masking
  → 3: SfM (GPS) → 4: Dense → 5a: Mesh || 5b: Splats
  → 6: Georef → 7: Quality Gate (retry if needed) → 8: Export

Capture states:
  - CREATED: Initial state
  - PROCESSING: Pipeline running
  - COMPLETED: Success
  - FAILED: Max retries exceeded
  - DEGRADED: Quality compromised but exported

Manifest structure:
  - schema_version: "1.0.0"
  - capture: metadata (ID, tier, CRS, etc.)
  - artifacts: list of all outputs with SHA256 hashes
  - quality_gate: quality verdict and metrics
  - metadata: summary (artifact count, total size)

Retry loop:
  - Max attempts per tier: Lite (0), Standard (1), Premium (2), Advanced (3)
  - Retry strategies escalate based on failure reason
  - Quality gate verdict determines retry (PASS → export, RETRY → redo)

Artifact types:
  - Mesh (OBJ, GLB)
  - Splats (binary .splat format)
  - Point cloud (PLY, LAZ)
  - Orthomosaic (GeoTIFF)
  - DSM (GeoTIFF)
  - Metadata (JSON manifests)

Next: Phase 6 — FastAPI Sidecar Server (Port 8002)
""")


if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 5 VERIFICATION TEST — VantageCam v1")
    print("=" * 60)
    
    try:
        test_stages_imports()
        test_artifact_collection()
        test_manifest_creation()
        test_orchestrator_creation()
        test_stage8_export()
        
        print_summary()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
