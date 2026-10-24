"""Phase 3 verification test — Reconstruction Stages 3-5 (SfM, Dense, Mesh/Splats)."""

import json
from pathlib import Path
import tempfile
import numpy as np
from stages.stage3_sfm import run_stage3_sfm
from stages.stage4_dense import run_stage4_dense
from stages.stage5a_mesh import run_stage5a_mesh
from stages.stage5b_splats import run_stage5b_splats
from tiers import get_tier


def create_test_frames_dir(tmpdir: Path, num_frames: int = 10) -> Path:
    """Create a temporary directory with synthetic test frames."""
    frames_dir = tmpdir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    
    from PIL import Image
    
    for i in range(num_frames):
        # Create synthetic frame (100x100 RGB)
        img_array = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
        img = Image.fromarray(img_array)
        img.save(frames_dir / f"frame_{i:06d}.png")
    
    return frames_dir


def test_stage3_sfm():
    """Test Stage 3: SfM."""
    print("\n=== TEST: Stage 3 SfM ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        frames_dir = create_test_frames_dir(tmpdir, num_frames=10)
        output_dir = tmpdir / "stage3"
        
        metadata = {
            "width": 100,
            "height": 100,
            "fps": 30.0,
        }
        
        result = run_stage3_sfm(frames_dir, output_dir, None, metadata, "test_sfm")
        
        assert result["stage3_complete"] == True
        assert result["sparse_points_count"] > 0
        assert result["camera_poses_count"] > 0
        assert "intrinsics" in result
        assert "scale_factor" in result
        
        print(f"  ✓ SfM complete: {result['sparse_points_count']} sparse points")
        print(f"✓ Stage 3 test PASSED")


def test_stage4_dense():
    """Test Stage 4: Dense."""
    print("\n=== TEST: Stage 4 Dense ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        frames_dir = create_test_frames_dir(tmpdir, num_frames=5)
        output_dir = tmpdir / "stage4"
        
        sfm_data = {
            "camera_poses": [
                {"R": [[1,0,0],[0,1,0],[0,0,1]], "t": [i*0.1, 0, 0]}
                for i in range(5)
            ],
            "intrinsics": {
                "fx": 50, "fy": 50, "cx": 50, "cy": 50,
                "width": 100, "height": 100
            },
            "scale_factor": 1.0,
        }
        
        result = run_stage4_dense(
            frames_dir, output_dir, sfm_data, "test_dense",
            use_neural_depth=False
        )
        
        assert result["stage4_complete"] == True
        assert result["dense_points_count"] > 0
        assert result["depth_maps_count"] > 0
        
        print(f"  ✓ Dense complete: {result['dense_points_count']} dense points")
        print(f"✓ Stage 4 test PASSED")


def test_stage5a_mesh():
    """Test Stage 5a: Mesh."""
    print("\n=== TEST: Stage 5a Mesh ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        output_dir = tmpdir / "stage5a"
        
        # Create synthetic dense data
        dense_points = np.random.randn(100, 3) * 2.0
        dense_data = {"dense_points": dense_points}
        
        tier = get_tier("standard")
        
        result = run_stage5a_mesh(dense_data, output_dir, tier, "test_mesh")
        
        assert result["stage5a_complete"] == True
        assert result["mesh_vertices_count"] > 0
        assert result["mesh_triangles_count"] > 0
        
        print(f"  ✓ Mesh complete: {result['mesh_vertices_count']} vertices, {result['mesh_triangles_count']} triangles")
        print(f"✓ Stage 5a test PASSED")


def test_stage5b_splats():
    """Test Stage 5b: Splats."""
    print("\n=== TEST: Stage 5b Splats ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        output_dir = tmpdir / "stage5b"
        
        # Create synthetic dense data
        dense_points = np.random.randn(100, 3) * 2.0
        dense_data = {"dense_points": dense_points}
        
        tier = get_tier("standard")
        
        result = run_stage5b_splats(dense_data, output_dir, tier, "test_splats")
        
        assert result["stage5b_complete"] == True
        assert result["splat_count"] > 0
        assert "splat_file" in result
        
        # Verify binary file was created
        splat_file = output_dir / result["splat_file"]
        assert splat_file.exists()
        
        print(f"  ✓ Splats complete: {result['splat_count']} Gaussians")
        print(f"  ✓ Binary file: {result['splat_file']} ({splat_file.stat().st_size} bytes)")
        print(f"✓ Stage 5b test PASSED")


def test_stages_imports():
    """Test that all reconstruction stage modules can be imported."""
    print("\n=== TEST: Stage Imports ===")
    
    try:
        from stages import stage3_sfm
        from stages import stage4_dense
        from stages import stage5a_mesh
        from stages import stage5b_splats
        
        print(f"  ✓ stage3_sfm imported")
        print(f"  ✓ stage4_dense imported")
        print(f"  ✓ stage5a_mesh imported")
        print(f"  ✓ stage5b_splats imported")
        
        # Check key functions exist
        assert hasattr(stage3_sfm, 'run_stage3_sfm')
        assert hasattr(stage4_dense, 'run_stage4_dense')
        assert hasattr(stage5a_mesh, 'run_stage5a_mesh')
        assert hasattr(stage5b_splats, 'run_stage5b_splats')
        
        print("✓ Stage imports test PASSED")
    
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        raise


def test_tiers_reconstruction():
    """Test tier configs for reconstruction stages."""
    print("\n=== TEST: Tiers for Reconstruction ===")
    
    lite = get_tier("lite")
    standard = get_tier("standard")
    premium = get_tier("premium")
    premium_adv = get_tier("premium_advanced")
    
    # Verify mesh budgets
    print(f"  Lite: {lite.mesh_triangle_budget:,} triangles, {lite.splat_count_target:,} splats")
    print(f"  Standard: {standard.mesh_triangle_budget:,} triangles, {standard.splat_count_target:,} splats")
    print(f"  Premium: {premium.mesh_triangle_budget:,} triangles, {premium.splat_count_target:,} splats")
    print(f"  Premium Advanced: {premium_adv.mesh_triangle_budget:,} triangles, {premium_adv.splat_count_target:,} splats")
    
    assert lite.mesh_triangle_budget == 50_000
    assert standard.mesh_triangle_budget == 250_000
    assert premium.mesh_triangle_budget == 750_000
    assert premium_adv.mesh_triangle_budget == 2_000_000
    
    assert lite.splat_count_target == 50_000
    assert standard.splat_count_target == 250_000
    assert premium.splat_count_target == 750_000
    assert premium_adv.splat_count_target == 2_000_000
    
    print("✓ Tiers test PASSED")


def print_summary():
    """Print Phase 3 summary."""
    print("\n" + "=" * 60)
    print("PHASE 3 SUMMARY — Reconstruction Stages 3-5")
    print("=" * 60)
    print("""
Created files:
  - vantagecam/stages/stage3_sfm.py (SfM with GPS Umeyama)
  - vantagecam/stages/stage4_dense.py (Dense reconstruction)
  - vantagecam/stages/stage5a_mesh.py (Mesh generation)
  - vantagecam/stages/stage5b_splats.py (Gaussian splats)

Key features:
  Stage 3: Camera intrinsics estimation, GPS trajectory loading,
           Umeyama alignment, synthetic sparse point triangulation
  Stage 4: Neural depth estimation (Depth Anything V2), depth map fusion,
           3D point cloud generation
  Stage 5a: Poisson surface reconstruction, mesh simplification, OBJ export
  Stage 5b: Gaussian initialization, binary .splat format, PLY export

Dual output path:
  - Mesh: Traditional 3D surface (OBJ format)
  - Splats: Gaussian splatting (binary .splat format for WebGL)

Both outputs generated from same point cloud = consistent reconstruction

Tier integration:
  - Lite: 50k triangles, 50k splats
  - Standard: 250k triangles, 250k splats
  - Premium: 750k triangles, 750k splats
  - Premium Advanced: 2M triangles, 2M splats

Next: Phase 4 — Georeferencing & Quality Gate (Stages 6-7)
""")


if __name__ == "__main__":
    print("=" * 60)
    print("PHASE 3 VERIFICATION TEST — VantageCam v1")
    print("=" * 60)
    
    try:
        test_stages_imports()
        test_tiers_reconstruction()
        test_stage3_sfm()
        test_stage4_dense()
        test_stage5a_mesh()
        test_stage5b_splats()
        
        print_summary()
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED ✓")
        print("=" * 60)
    
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
