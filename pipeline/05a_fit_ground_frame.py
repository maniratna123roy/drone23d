"""
Spatial Twin: Ground Plane Fitting & Frame Alignment (pipeline/05a_fit_ground_frame.py)

Beginner Analogy:
Adjusting the leveling feet on a heavy pool table:
Drone camera coordinates are often tilted and float at arbitrary elevations.
This script uses RANSAC (Random Sample Consensus) to find the flat ground,
rotates the entire digital twin so that "up" points straight into the sky (+Z),
and sets the ground surface to exactly elevation 0.0 meters.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import argparse
import numpy as np
from sklearn.linear_model import RANSACRegressor

from pipeline.common.io import load_ply
from pipeline.common.frame import compute_ground_transform, apply_transform

def fit_ground_and_align(ply_path: str = "./output/mill/point_cloud.ply",
                         labels_path: str = "./output/mill/labels.npy",
                         output_dir: str = "./output/mill"):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    
    print("[INFO] Loading scene point cloud and semantic labels...")
    data = load_ply(ply_path)
    positions = data["positions"]
    labels = np.load(labels_path)
    
    print(f"       Loaded {len(positions)} splats.")
    
    # Select terrain (1) and road (2) splats to define the ground plane
    ground_mask = (labels == 1) | (labels == 2)
    if np.sum(ground_mask) < 100:
        print("[WARN] Few terrain/road splats found; using lowest 20% of points.")
        z_threshold = np.percentile(positions[:, 2], 20)
        ground_mask = positions[:, 2] <= z_threshold
        
    ground_pts = positions[ground_mask]
    print(f"[INFO] Using {len(ground_pts)} ground splats for RANSAC plane fitting...")
    
    # Fit plane: z = a*x + b*y + c using RANSACRegressor
    X = ground_pts[:, :2]  # x, y
    y = ground_pts[:, 2]   # z
    
    ransac = RANSACRegressor(residual_threshold=0.3, random_state=42)
    ransac.fit(X, y)
    
    a, b = ransac.estimator_.coef_
    c = ransac.estimator_.intercept_
    
    # Plane equation: a*x + b*y - 1*z + c = 0
    # Normal is [a, b, -1] -> make upward pointing [-a, -b, 1]
    normal = np.array([-a, -b, 1.0], dtype=np.float32)
    normal = normal / np.linalg.norm(normal)
    
    # Ground point at center (x=0, y=0, z=c)
    ground_center = np.array([0.0, 0.0, c], dtype=np.float32)
    
    print(f"[INFO] Fitted Ground Normal: [{normal[0]:.4f}, {normal[1]:.4f}, {normal[2]:.4f}]")
    print(f"       Raw Ground Elevation at origin: {c:.2f} m")
    
    # Compute 4x4 rigid transformation
    T = compute_ground_transform(normal, ground_center)
    
    # Apply transformation to all splats
    aligned_positions = apply_transform(positions, T)
    
    # Verify alignment
    aligned_ground_z = aligned_positions[ground_mask, 2]
    print(f"[INFO] Aligned ground mean z: {np.mean(aligned_ground_z):.3f} m (std: {np.std(aligned_ground_z):.3f})")
    
    # Save transformed positions and metadata
    np.save(out / "aligned_positions.npy", aligned_positions)
    
    transform_record = {
        "plane_normal": normal.tolist(),
        "ground_intercept": float(c),
        "transform_matrix_4x4": T.tolist()
    }
    with open(out / "frame_transform.json", "w") as f:
        json.dump(transform_record, f, indent=2)
        
    print(f"[SUCCESS] Aligned scene saved to {out / 'aligned_positions.npy'}")
    print(f"[SUCCESS] Frame transformation saved to {out / 'frame_transform.json'}")
    return True

if __name__ == "__main__":
    fit_ground_and_align()
