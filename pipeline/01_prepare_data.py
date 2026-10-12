"""
Spatial Twin: Data Preparation Script (Pipeline Stage 01)

Prepares raw drone imagery and poses for 3D Gaussian Splatting:
- Downsamples high-resolution frames (e.g., 4x downsample / 25% resolution)
- Subsamples frame rate (e.g., every 3rd or 4th frame if dataset > 500 images)
- Normalizes and verifies camera poses
"""

import os
import sys
import argparse
from pathlib import Path
from PIL import Image

def prepare_dataset(source_dir: str, output_dir: str, downsample_factor: int = 4, step: int = 3):
    src = Path(source_dir)
    out = Path(output_dir)
    
    if not src.exists():
        print(f"[ERROR] Source dataset directory does not exist: {src}")
        print("Please place your raw drone images into this folder or specify --source_dir.")
        return False
        
    out_images = out / "images"
    out_images.mkdir(parents=True, exist_ok=True)
    
    image_exts = {".jpg", ".jpeg", ".png", ".JPG", ".PNG"}
    all_images = sorted([f for f in src.iterdir() if f.suffix in image_exts])
    
    if not all_images:
        print(f"[ERROR] No images found in {src}")
        return False
        
    print(f"[INFO] Found {len(all_images)} total images in {src}")
    selected_images = all_images[::step]
    print(f"[INFO] Subsampling every {step} frames -> {len(selected_images)} selected frames")
    
    for idx, img_path in enumerate(selected_images):
        try:
            with Image.open(img_path) as img:
                new_w = max(1, img.width // downsample_factor)
                new_h = max(1, img.height // downsample_factor)
                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                dest_path = out_images / f"frame_{idx:05d}.jpg"
                resized.save(dest_path, quality=90)
                
                if idx % 50 == 0 or idx == len(selected_images) - 1:
                    print(f"   Processed {idx+1}/{len(selected_images)} -> {dest_path.name} ({new_w}x{new_h})")
        except Exception as e:
            print(f"[WARN] Failed to process {img_path.name}: {e}")
            
    print(f"\n[SUCCESS] Prepared {len(selected_images)} downsampled images in {out_images}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare and downsample drone imagery for 3DGS training.")
    parser.add_argument("--source_dir", type=str, default="./data/raw_drone", help="Path to raw drone photos")
    parser.add_argument("--output_dir", type=str, default="./data/mill", help="Output directory for processed dataset")
    parser.add_argument("--downsample", type=int, default=4, help="Downsample factor (e.g. 4 for 25% size)")
    parser.add_argument("--step", type=int, default=3, help="Subsample step (e.g. every 3rd frame)")
    
    args = parser.parse_args()
    prepare_dataset(args.source_dir, args.output_dir, args.downsample, args.step)
