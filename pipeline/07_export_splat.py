"""
Spatial Twin: Binary SPLAT & Semantic Class Exporter (pipeline/07_export_splat.py)

Beginner Analogy:
Packaging a video game cartridge:
It takes the 3D Gaussian splat positions, colors, scales, and rotations,
and serializes them into a ultra-compact 32-byte-per-splat binary file (`scene.splat`)
plus a 1-byte-per-splat class sidecar (`scene.classes.u8`).
This allows the browser's GPU to stream the photorealistic 3D scene instantaneously
while maintaining a 1-to-1 index lock with every building's database ID.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import json
import argparse
import numpy as np

from pipeline.common.io import load_ply, save_splat, save_classes
from pipeline.common.frame import apply_transform

def export_web_splat(ply_path: str = "./output/mill/point_cloud.ply",
                     labels_path: str = "./output/mill/labels.npy",
                     transform_path: str = "./output/mill/frame_transform.json",
                     static_dir: str = "./static"):
    print("=" * 60)
    print("BINARY WEB SPLAT & CLASS EXPORTER (Pipeline Stage 07)")
    print("=" * 60)
    
    out_dir = Path(static_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Load raw PLY data
    print(f"[INFO] Reading point cloud: {ply_path}...")
    ply_data = load_ply(ply_path)
    positions = ply_data["positions"]
    scales = ply_data["scales"]
    rotations = ply_data["rotations"]
    colors = ply_data["colors"]
    
    n_splats = positions.shape[0]
    print(f"       Total Splats to Export: {n_splats:,}")
    
    # 2. Apply coordinate frame transformation
    if Path(transform_path).exists():
        with open(transform_path) as f:
            t_record = json.load(f)
            T = np.array(t_record["transform_matrix_4x4"], dtype=np.float32)
            print("[INFO] Applying ground frame transformation matrix (Z-up, ground at z=0)...")
            positions = apply_transform(positions, T)
    else:
        print("[WARN] No frame_transform.json found; exporting untransformed positions.")
        
    # 3. Load semantic class labels
    labels = np.load(labels_path)
    assert len(labels) == n_splats, f"Mismatch: {len(labels)} labels vs {n_splats} splats!"
    
    # 4. Export binary .splat (32 bytes per splat)
    splat_file = out_dir / "scene.splat"
    print(f"[INFO] Writing web-optimized binary splat: {splat_file}...")
    save_splat(positions, scales, rotations, colors, str(splat_file))
    splat_size_mb = os.path.getsize(splat_file) / (1024 * 1024)
    print(f"       -> Size: {splat_size_mb:.2f} MB ({os.path.getsize(splat_file):,} bytes)")
    
    # 5. Export binary .classes.u8 (1 byte per splat sidecar)
    classes_file = out_dir / "scene.classes.u8"
    print(f"[INFO] Writing semantic class sidecar: {classes_file}...")
    save_classes(labels, str(classes_file))
    classes_size_kb = os.path.getsize(classes_file) / 1024
    print(f"       -> Size: {classes_size_kb:.2f} KB ({os.path.getsize(classes_file):,} bytes)")
    
    # 6. Verify 1:1 order preservation and integrity
    expected_splat_bytes = n_splats * 32
    actual_splat_bytes = os.path.getsize(splat_file)
    assert actual_splat_bytes == expected_splat_bytes, f"Corrupted splat size! Expected {expected_splat_bytes}, got {actual_splat_bytes}"
    
    actual_classes_bytes = os.path.getsize(classes_file)
    assert actual_classes_bytes == n_splats, f"Corrupted classes size! Expected {n_splats}, got {actual_classes_bytes}"
    
    print("-" * 60)
    print("[SUCCESS] EXPORT VERIFIED:")
    print(f"  • scene.splat      : {splat_file.resolve()} (Exact {n_splats} points x 32 bytes)")
    print(f"  • scene.classes.u8 : {classes_file.resolve()} (Exact 1:1 matching index)")
    print("-" * 60)
    return True

if __name__ == "__main__":
    export_web_splat()
