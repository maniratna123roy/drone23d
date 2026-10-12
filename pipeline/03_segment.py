"""
Spatial Twin: Semantic Segmentation with SegFormer-B0 (pipeline/03_segment.py)

Beginner Analogy:
An instant digital coloring book:
It scans drone aerial photos and assigns a class to every single pixel:
buildings are assigned class 0, terrain is class 1, roads are class 2, and vegetation is class 3.
Zero custom neural network training required—it uses an optimized, pretrained vision transformer.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import argparse
import numpy as np
from PIL import Image
import torch

# Cityscapes to Spatial Twin Class Mapping:
# 0: Structure (building, wall, fence)
# 1: Terrain (terrain)
# 2: Road (road, sidewalk)
# 3: Vegetation (vegetation)
# 255: Unknown (sky, car, person, etc.)
CITYSCAPES_MAP = {
    0: 2,   # road -> Road
    1: 2,   # sidewalk -> Road
    2: 0,   # building -> Structure
    3: 0,   # wall -> Structure
    4: 0,   # fence -> Structure
    8: 3,   # vegetation -> Vegetation
    9: 1,   # terrain -> Terrain
}

def segment_keyframe(image_path: str, model, processor, device: str = "cpu") -> np.ndarray:
    """Runs SegFormer inference on an image and returns a (H, W) uint8 class mask."""
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt").to(device)
    
    with torch.no_grad():
        outputs = model(**inputs)
        logits = outputs.logits  # shape (1, num_classes, H/4, W/4)
        
        # Upsample logits to original image size
        upsampled_logits = torch.nn.functional.interpolate(
            logits,
            size=image.size[::-1], # (H, W)
            mode="bilinear",
            align_corners=False
        )
        pred_cityscapes = upsampled_logits.argmax(dim=1)[0].cpu().numpy()
        
    # Remap to Spatial Twin classes
    h, w = pred_cityscapes.shape
    twin_mask = np.full((h, w), 255, dtype=np.uint8)
    for c_id, twin_id in CITYSCAPES_MAP.items():
        twin_mask[pred_cityscapes == c_id] = twin_id
        
    return twin_mask

def run_segmentation(images_dir: str = "./data/mill/images", 
                     output_dir: str = "./output/masks",
                     device: str = None):
    print("=" * 60)
    print("SEMANTIC SEGMENTATION WITH SEGFORMER-B0 (Pipeline Stage 03)")
    print("=" * 60)
    
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"[INFO] Using Device: {device.upper()}")
    
    src = Path(images_dir)
    out = Path(output_dir)
    image_files = sorted([f for f in src.iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png"}]) if src.exists() else []
    if not image_files:
        raise ValueError(f"No camera images found in {src}; provide real images before segmentation")
    out.mkdir(parents=True, exist_ok=True)
    
    # Clear old masks to prevent stale data from previous uploads
    for old_mask in out.glob("*_mask.png"):
        try:
            old_mask.unlink()
        except Exception:
            pass
    
    print(f"[INFO] Loading SegFormer-B0 model from Hugging Face (~14 MB)...")
    from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation
    
    model_name = "nvidia/segformer-b0-finetuned-cityscapes-1024-1024"
    processor = SegformerImageProcessor.from_pretrained(model_name)
    model = SegformerForSemanticSegmentation.from_pretrained(model_name).to(device)
    model.eval()
    print("[INFO] Model loaded successfully!")
    
    for idx, img_path in enumerate(image_files):  # process all keyframes
        mask = segment_keyframe(str(img_path), model, processor, device)
        mask_img = Image.fromarray(mask, mode="L")
        out_path = out / f"{img_path.stem}_mask.png"
        mask_img.save(out_path)
        print(f"  [{idx+1}/{len(image_files)}] Saved mask: {out_path.name} ({mask.shape[1]}x{mask.shape[0]})")
        
    print(f"\n[SUCCESS] Completed keyframe segmentation in {out}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run SegFormer-B0 semantic segmentation on keyframes.")
    parser.add_argument("--images", default="./data/mill/images", help="Path to input images directory")
    parser.add_argument("--output", default="./output/masks", help="Path to output masks directory")
    parser.add_argument("--device", default=None, help="Device to run on (cuda or cpu)")
    args = parser.parse_args()
    run_segmentation(images_dir=args.images, output_dir=args.output, device=args.device)
