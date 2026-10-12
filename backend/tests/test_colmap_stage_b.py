"""
Unit and Integration Tests for Stage B COLMAP Photogrammetry & Dense Reconstruction.
Tests:
- COLMAP binary locator
- Rotation conversion (qvec to SO(3) matrix)
- Geometrically grounded depth scale alignment (RANSAC)
- Cross-view consistency filtering
- 3D voxel grid consensus fusion
- Ground plane transform leveling
- COLMAP validation report generation
"""

import pytest
import numpy as np
from pathlib import Path

from pipeline.colmap_reconstructor import (
    find_colmap_executable,
    qvec2rotmat,
    align_depth_to_colmap_geometry,
    cross_view_consistency_filter,
    voxel_grid_fusion,
    compute_ground_transform,
    apply_transform,
    format_colmap_validation_report,
    evaluate_colmap_quality,
)


def test_colmap_binary_discovery():
    """Verifies that the CUDA-enabled COLMAP binary is discovered."""
    colmap_path = find_colmap_executable()
    assert colmap_path is not None, "COLMAP binary should be found on system"
    assert Path(colmap_path).exists(), f"COLMAP path does not exist: {colmap_path}"


def test_qvec2rotmat_properties():
    """Verifies that quaternion to rotation matrix produces a valid SO(3) matrix."""
    # Identity quaternion [1, 0, 0, 0] (w, x, y, z)
    R_id = qvec2rotmat([1.0, 0.0, 0.0, 0.0])
    np.testing.assert_allclose(R_id, np.eye(3), atol=1e-6)

    # 90-degree rotation around Z axis: q = [cos(45°), 0, 0, sin(45°)] = [sqrt(2)/2, 0, 0, sqrt(2)/2]
    val = np.sqrt(2.0) / 2.0
    R_z90 = qvec2rotmat([val, 0.0, 0.0, val])
    # Determinant of proper rotation must be +1.0
    assert np.isclose(np.linalg.det(R_z90), 1.0, atol=1e-5)
    # R * R^T must equal Identity
    np.testing.assert_allclose(R_z90 @ R_z90.T, np.eye(3), atol=1e-5)


def test_align_depth_to_colmap_geometry():
    """Verifies that RANSAC fits scale and offset between Depth Anything disparity and COLMAP metric Z."""
    # Generate synthetic observations
    np.random.seed(42)
    true_scale = 0.25
    true_offset = 0.03

    h, w = 100, 100
    raw_depth = np.random.uniform(20.0, 240.0, size=(h, w)).astype(np.float32)

    # Create 30 tie points
    n_ties = 30
    u_coords = np.random.randint(5, w - 5, size=n_ties)
    v_coords = np.random.randint(5, h - 5, size=n_ties)
    obs_uv = np.column_stack([u_coords, v_coords]).astype(np.float32)

    d_sample = raw_depth[v_coords, u_coords] / 255.0
    inv_z_true = true_scale * d_sample + true_offset
    obs_z_true = 1.0 / inv_z_true

    aligned_z, meta = align_depth_to_colmap_geometry(
        raw_depth=raw_depth,
        obs_uv=obs_uv,
        obs_z_true=obs_z_true
    )

    assert meta["aligned"] is True
    assert meta["inliers"] >= 20
    assert np.isclose(meta["scale"], true_scale, atol=0.05)
    assert np.isclose(meta["offset"], true_offset, atol=0.05)
    assert aligned_z.shape == (h, w)
    assert np.all(aligned_z > 0.0)


def test_cross_view_consistency_filter():
    """Verifies that points contradicting neighboring camera depth maps are pruned."""
    np.random.seed(42)
    # Reference camera at origin
    ref_name = "frame_00.jpg"
    poses = {
        "frame_00.jpg": {
            "cam_center": [0.0, 0.0, 0.0],
            "R_cw": np.eye(3),
            "t_cw": np.zeros(3),
            "camera_id": "1"
        },
        "frame_01.jpg": {
            "cam_center": [1.0, 0.0, 0.0],
            "R_cw": np.eye(3),
            "t_cw": np.array([-1.0, 0.0, 0.0]),
            "camera_id": "1"
        }
    }
    intrinsics = {
        "1": {"model": "PINHOLE", "fx": 500.0, "fy": 500.0, "cx": 250.0, "cy": 250.0}
    }

    # Neighbor depth map: flat plane at Z = 10.0m
    neighbor_depth = np.full((500, 500), 10.0, dtype=np.float32)
    depth_maps = {"frame_01.jpg": neighbor_depth}

    # Candidate 1: Real point at (0, 0, 10) -> projects into frame_01 with Z=10.0 -> CONSISTENT
    # Candidate 2: Hallucinated outlier at (0, 0, 25) -> projects into frame_01 with Z=25.0 != 10.0 -> PRUNED
    pts = np.array([
        [0.0, 0.0, 10.0],
        [0.0, 0.0, 25.0]
    ], dtype=np.float32)
    colors = np.array([[200, 200, 200], [50, 50, 50]], dtype=np.uint8)
    labels = np.array([0, 0], dtype=np.uint8)

    filt_pts, filt_col, filt_lbl = cross_view_consistency_filter(
        candidate_points=pts,
        candidate_colors=colors,
        candidate_labels=labels,
        ref_image_name=ref_name,
        poses=poses,
        depth_maps=depth_maps,
        intrinsics=intrinsics,
        depth_tol=0.08,
        min_consistent_views=1
    )

    # Only candidate 1 should survive
    assert len(filt_pts) == 1
    np.testing.assert_allclose(filt_pts[0], [0.0, 0.0, 10.0], atol=1e-3)


def test_voxel_grid_fusion():
    """Verifies that multi-view overlapping points within a spatial voxel are fused to consensus centroid."""
    # Points clustered near (1.05, 2.05, 3.05) within a 0.1m voxel [1.0, 1.1)
    pts = np.array([
        [1.02, 2.02, 3.02],
        [1.04, 2.04, 3.04],
        [1.06, 2.06, 3.06],
        [10.0, 10.0, 10.0]  # Isolated point in another voxel
    ], dtype=np.float32)

    colors = np.array([
        [255, 0, 0],
        [200, 0, 0],
        [230, 0, 0],
        [0, 255, 0]
    ], dtype=np.uint8)

    labels = np.array([0, 0, 0, 1], dtype=np.uint8)

    fused_pts, fused_col, fused_lbl = voxel_grid_fusion(
        points=pts,
        colors=colors,
        labels=labels,
        voxel_size=0.1
    )

    # Should produce 2 consensus voxels
    assert len(fused_pts) == 2
    # First cluster centroid should be approximately (1.04, 2.04, 3.04)
    assert np.allclose(fused_pts[0], [1.04, 2.04, 3.04], atol=0.05)
    # Color should be averaged (~228, 0, 0)
    assert fused_col[0, 0] > 210
    # Majority label should be 0 (structure)
    assert fused_lbl[0] == 0


def test_compute_ground_transform_leveling():
    """Verifies that ground plane transform rotates a tilted normal to [0, 0, 1] and centers elevation."""
    # Tilted ground normal (30 degrees tilt)
    tilt_normal = np.array([0.5, 0.0, np.sqrt(3)/2], dtype=np.float32)
    tilt_normal /= np.linalg.norm(tilt_normal)
    ground_pt = np.array([10.0, 5.0, 2.0], dtype=np.float32)

    T = compute_ground_transform(tilt_normal, ground_pt)
    assert T.shape == (4, 4)

    # Transforming the ground point should set its Z to 0.0
    aligned_pt = apply_transform(ground_pt.reshape(1, 3), T)
    assert np.isclose(aligned_pt[0, 2], 0.0, atol=1e-4)

    # Transforming a point 5m above the ground point along the normal
    pt_above = ground_pt + 5.0 * tilt_normal
    aligned_above = apply_transform(pt_above.reshape(1, 3), T)
    assert np.isclose(aligned_above[0, 2], 5.0, atol=1e-4)


def test_format_colmap_validation_report():
    """Verifies that the COLMAP validation report formats required metrics correctly."""
    report = {
        "status": "PASSED",
        "registered_images": 11,
        "total_input_images": 11,
        "registration_percentage": "100.0%",
        "sparse_3d_points": 1403,
        "mean_reprojection_error_px": 0.24,
        "median_reprojection_error_px": 0.14,
        "trajectory_continuity": "SMOOTH",
        "trajectory_max_step_m": 1.63,
        "trajectory_median_step_m": 1.45,
    }
    intrinsics = {
        "1": {"model": "OPENCV", "fx": 419.4, "fy": 392.0, "cx": 320.0, "cy": 180.0}
    }

    text = format_colmap_validation_report(report, intrinsics, dense_points_count=16791)
    assert "COLMAP RECONSTRUCTION VALIDATION" in text
    assert "Registered images:        11 / 11  (100.0%)" in text
    assert "Sparse 3D points:         1,403" in text
    assert "Mean reprojection error:  0.24 px" in text
    assert "Camera model:             OPENCV" in text
    assert "Dense Photogrammetry:     16,791 geometrically consistent points" in text
    assert "Cross-View Consistency:   PASSED" in text
