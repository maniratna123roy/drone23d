"""Stage 2: Dynamic Masking — Remove dynamic objects using semantic segmentation.

Polycam insight: Some objects in drone video are transient — people, vehicles, clouds.
If we include them in 3D reconstruction, they create "ghosts" or artifacts. By masking
them out during reconstruction, we get cleaner geometry.

Real-world analogy: Like removing the scratches from old photographs before scanning,
or airbrushing out a bird that flew through the shot.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
import numpy as np
from PIL import Image


class MaskingError(Exception):
    """Raised when masking fails."""
    pass


def load_segformer_model(device: str = "cpu") -> Any:
    """Load SegFormer-B0 model from HuggingFace.
    
    SegFormer-B0 is a lightweight semantic segmentation model trained on Cityscapes.
    Classes: road, sidewalk, building, wall, fence, pole, traffic_light, traffic_sign,
    vegetation, terrain, sky, person, rider, car, truck, bus, train, motorcycle, bicycle, etc.
    
    Args:
        device: 'cpu' or 'cuda'
        
    Returns:
        Initialized pipeline object
    """
    try:
        from transformers import pipeline
        
        print(f"  Loading SegFormer-B0 on {device}...")
        
        seg_pipeline = pipeline(
            "image-segmentation",
            model="nvidia/segformer-b0-finetuned-cityscapes-1024-1024",
            device=0 if device == "cuda" else -1,  # -1 for CPU
        )
        
        print(f"  ✓ SegFormer-B0 loaded")
        return seg_pipeline
    
    except ImportError:
        raise MaskingError("transformers library not installed")
    except Exception as e:
        raise MaskingError(f"Failed to load SegFormer: {e}")


def segment_image(
    image_path: Path,
    seg_pipeline: Any,
    device: str = "cpu",
) -> Tuple[np.ndarray, List[str]]:
    """Run semantic segmentation on an image.
    
    Args:
        image_path: Input image
        seg_pipeline: SegFormer pipeline
        device: Device used ('cpu' or 'cuda')
        
    Returns:
        Tuple of (segmentation_map [H,W] with class IDs, class_names)
    """
    try:
        # Load image
        img = Image.open(image_path).convert("RGB")
        
        # Run segmentation
        results = seg_pipeline(img)
        
        # Convert results to numpy array
        # Results typically come as a list of dicts with 'mask' and 'label'
        if isinstance(results, list) and len(results) > 0:
            # Multi-class output
            seg_map = np.zeros((img.height, img.width), dtype=np.uint8)
            class_names = []
            
            for idx, result in enumerate(results):
                if "mask" in result:
                    mask = np.array(result["mask"])
                    label = result.get("label", f"class_{idx}")
                    class_names.append(label)
                    seg_map[mask > 0] = idx
            
            return seg_map, class_names
        else:
            raise MaskingError("Unexpected segmentation output format")
    
    except Exception as e:
        raise MaskingError(f"Segmentation failed: {e}")


def create_dynamic_mask(
    seg_map: np.ndarray,
    class_names: List[str],
    remove_classes: Optional[List[str]] = None,
) -> np.ndarray:
    """Create a binary mask removing dynamic object classes.
    
    Args:
        seg_map: Segmentation map (H, W) with class IDs
        class_names: List of class names corresponding to IDs
        remove_classes: Classes to remove (None = use default dynamic classes)
        
    Returns:
        Binary mask [H, W] uint8: 255 = keep, 0 = remove
    """
    if remove_classes is None:
        # Default: remove people, vehicles, animals, etc.
        remove_classes = [
            "person",
            "rider",
            "car",
            "truck",
            "bus",
            "train",
            "motorcycle",
            "bicycle",
            "animal",
        ]
    
    mask = np.ones_like(seg_map, dtype=np.uint8) * 255
    
    # Find indices of classes to remove
    for remove_class in remove_classes:
        for idx, class_name in enumerate(class_names):
            if remove_class.lower() in class_name.lower():
                mask[seg_map == idx] = 0
                break
    
    return mask


def apply_mask_to_image(
    image_path: Path,
    mask: np.ndarray,
    output_path: Path,
    fill_value: int = 128,
) -> None:
    """Apply mask to image (set masked regions to fill_value).
    
    Args:
        image_path: Input image
        mask: Binary mask (255 = keep, 0 = remove)
        output_path: Output image path
        fill_value: Value to fill masked regions (0-255)
    """
    img = Image.open(image_path).convert("RGB")
    img_array = np.array(img)
    
    # Apply mask
    mask_3ch = np.stack([mask, mask, mask], axis=2)
    masked_img = np.where(
        mask_3ch == 255,
        img_array,
        fill_value
    ).astype(np.uint8)
    
    # Save
    Image.fromarray(masked_img).save(output_path)


def run_stage2_masking(
    frames_dir: Path,
    output_dir: Path,
    tier_config: "TierConfig",
    capture_id: str,
    device: str = "cpu",
    enable_masking: bool = True,
) -> Dict[str, Any]:
    """Run Stage 2: Dynamic object masking using SegFormer.
    
    Args:
        frames_dir: Directory with input keyframes
        output_dir: Directory for output (masked frames)
        tier_config: Tier configuration (dynamic_masks flag)
        capture_id: Capture job identifier
        device: 'cpu' or 'cuda'
        enable_masking: Override to disable masking (for testing)
        
    Returns:
        Dict with masking results:
        - masked_frames: list of output frame paths
        - frame_count: number of frames processed
        - removed_classes: classes that were masked out
        - stage2_complete: whether stage passed
    """
    print(f"[{capture_id}] Stage 2: Dynamic Masking")
    print(f"  Enable masking: {tier_config.dynamic_masks and enable_masking}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # If masking is disabled for this tier, just copy frames
    if not tier_config.dynamic_masks or not enable_masking:
        print(f"  ⚠ Masking disabled (lite tier or user setting) — copying frames as-is")
        
        frames = sorted(frames_dir.glob("frame_*.png"))
        masked_frames = []
        
        for i, frame in enumerate(frames):
            output_path = output_dir / frame.name
            img = Image.open(frame).convert("RGB")
            img.save(output_path)
            masked_frames.append(str(output_path.name))
        
        return {
            "stage2_complete": True,
            "masked_frames": masked_frames,
            "frame_count": len(masked_frames),
            "removed_classes": [],
            "masking_enabled": False,
        }
    
    # Load SegFormer model
    try:
        seg_pipeline = load_segformer_model(device)
    except MaskingError as e:
        print(f"  ⚠ SegFormer loading failed ({e}) — proceeding without masking")
        frames = sorted(frames_dir.glob("frame_*.png"))
        masked_frames = []
        
        for frame in frames:
            output_path = output_dir / frame.name
            img = Image.open(frame).convert("RGB")
            img.save(output_path)
            masked_frames.append(str(output_path.name))
        
        return {
            "stage2_complete": True,
            "masked_frames": masked_frames,
            "frame_count": len(masked_frames),
            "removed_classes": [],
            "masking_enabled": False,
            "warning": str(e),
        }
    
    # Process frames
    frames = sorted(frames_dir.glob("frame_*.png"))
    masked_frames = []
    removed_classes_set = set()
    
    print(f"  Processing {len(frames)} frames...")
    
    try:
        for i, frame_path in enumerate(frames):
            try:
                # Segment image
                seg_map, class_names = segment_image(frame_path, seg_pipeline, device)
                
                # Create dynamic mask
                mask = create_dynamic_mask(seg_map, class_names)
                
                # Track removed classes
                for idx, class_name in enumerate(class_names):
                    if np.any(seg_map == idx) and np.any(mask[seg_map == idx] == 0):
                        removed_classes_set.add(class_name)
                
                # Apply mask to image
                output_path = output_dir / frame_path.name
                apply_mask_to_image(frame_path, mask, output_path, fill_value=128)
                masked_frames.append(str(output_path.name))
                
                if (i + 1) % max(1, len(frames) // 5) == 0:
                    print(f"    {i+1}/{len(frames)} processed")
            
            except Exception as e:
                print(f"    ⚠ Failed to mask frame {i}: {e} — copying as-is")
                output_path = output_dir / frame_path.name
                img = Image.open(frame_path).convert("RGB")
                img.save(output_path)
                masked_frames.append(str(output_path.name))
        
        removed_classes = sorted(list(removed_classes_set))
        
        print(f"  ✓ Stage 2 complete: {len(masked_frames)} frames masked")
        if removed_classes:
            print(f"    Removed classes: {', '.join(removed_classes)}")
        
        return {
            "stage2_complete": True,
            "masked_frames": masked_frames,
            "frame_count": len(masked_frames),
            "removed_classes": removed_classes,
            "masking_enabled": True,
            "metrics": {
                "frames_processed": len(masked_frames),
            }
        }
    
    except Exception as e:
        print(f"  ❌ Masking error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "stage2_complete": False,
            "error": str(e),
        }


if __name__ == "__main__":
    # Quick test
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python stage2_masking.py <frames_dir> [enable_masking]")
        sys.exit(1)
    
    frames_input = Path(sys.argv[1])
    enable = sys.argv[2].lower() == "true" if len(sys.argv) > 2 else True
    
    class MockTier:
        def __init__(self):
            self.dynamic_masks = enable
    
    tier = MockTier()
    output = Path("output/vantagecam/test_stage2/masked_frames")
    
    result = run_stage2_masking(frames_input, output, tier, "test_capture", device="cpu", enable_masking=enable)
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2, default=str))
