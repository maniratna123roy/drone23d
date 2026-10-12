"""
Spatial Twin: Coordinate Frame and Camera Utilities (pipeline/common/frame.py)

Beginner Analogy:
A universal translator between different camera angles and maps:
it translates 3D coordinates (latitude, longitude, elevation) into 2D camera pixels,
and aligns drone coordinates so "up" is always the sky and "down" is the ground.
"""

import numpy as np
from typing import Tuple, Optional

def compute_ground_transform(
    plane_normal: np.ndarray,
    plane_point: np.ndarray,
    force_positive_raw_z: bool = False
) -> np.ndarray:
    """
    Computes a 4x4 rigid transformation matrix that:
    1. Translates the ground plane point to z = 0.
    2. Rotates the ground normal vector to align with +Z [0, 0, 1].
    """
    normal = plane_normal / np.linalg.norm(plane_normal)
    
    # Ensure normal points upwards only if explicitly requested
    if force_positive_raw_z and normal[2] < 0:
        normal = -normal

    target_normal = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    
    # Rotation axis: cross product of current normal and target normal
    axis = np.cross(normal, target_normal)
    axis_len = np.linalg.norm(axis)
    
    if axis_len < 1e-6:
        # Already aligned or antiparallel
        R = np.eye(3, dtype=np.float32)
        if np.dot(normal, target_normal) < 0:
            R[0, 0] = -1.0
            R[2, 2] = -1.0
    else:
        axis = axis / axis_len
        cos_angle = np.clip(np.dot(normal, target_normal), -1.0, 1.0)
        angle = np.arccos(cos_angle)
        
        # Rodrigues' rotation formula
        K = np.array([
            [0.0, -axis[2], axis[1]],
            [axis[2], 0.0, -axis[0]],
            [-axis[1], axis[0], 0.0]
        ], dtype=np.float32)
        
        R = np.eye(3, dtype=np.float32) + np.sin(angle) * K + (1.0 - cos_angle) * (K @ K)
        
    T = np.eye(4, dtype=np.float32)
    T[:3, :3] = R
    # Translate ground point to z = 0 after rotation
    rotated_pt = R @ plane_point
    T[:3, 3] = -rotated_pt
    T[2, 3] = -rotated_pt[2]  # Ensures ground z is exactly 0
    return T

def apply_transform(points: np.ndarray, transform_matrix: np.ndarray) -> np.ndarray:
    """
    Applies a 4x4 transformation matrix to an (N, 3) array of 3D points.
    """
    n = points.shape[0]
    homogeneous = np.hstack([points, np.ones((n, 1), dtype=np.float32)])
    transformed = (transform_matrix @ homogeneous.T).T
    return transformed[:, :3]

def project_points_to_camera(points_3d: np.ndarray, 
                             K: np.ndarray, 
                             c2w: np.ndarray, 
                             img_w: int, 
                             img_h: int) -> Tuple[np.ndarray, np.ndarray]:
    """
    Projects 3D world points into 2D camera pixel coordinates.
    Returns:
      pixels: (N, 2) integer (x, y) coordinates
      visible_mask: (N,) boolean mask of points in front of the camera and within image bounds
    """
    w2c = np.linalg.inv(c2w)
    
    n = points_3d.shape[0]
    pts_hom = np.hstack([points_3d, np.ones((n, 1), dtype=np.float32)])
    cam_pts = (w2c @ pts_hom.T).T[:, :3]
    
    # Points must be in front of the camera (Z > 0.1)
    in_front = cam_pts[:, 2] > 0.1
    
    # Project: u = fx * (x / z) + cx, v = fy * (y / z) + cy
    proj = (K @ cam_pts.T).T
    z = np.maximum(proj[:, 2:3], 1e-6)
    uv = proj[:, :2] / z
    
    x = np.round(uv[:, 0]).astype(int)
    y = np.round(uv[:, 1]).astype(int)
    
    within_bounds = (x >= 0) & (x < img_w) & (y >= 0) & (y < img_h)
    valid_mask = in_front & within_bounds
    
    return np.column_stack([x, y]), valid_mask
