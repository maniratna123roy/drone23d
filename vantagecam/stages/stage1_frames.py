"""Stage 1: Parallax Keyframes — Extract keyframes using parallax-based filtering.

Polycam's key insight: Don't sample frames uniformly. Instead, select frames where
the scene's parallax (depth change due to camera motion) is significant. This avoids
extracting many nearly-identical frames and instead picks diverse views.

Real-world analogy: Like a photographer reviewing rolls of film and keeping only
the shots where the perspective changed the most, not every frame of the video.
"""

import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
import numpy as np
from PIL import Image


class KeyframeExtractionError(Exception):
    """Raised when keyframe extraction fails."""
    pass


def extract_frames_uniform(
    video_path: Path,
    output_dir: Path,
    max_frames: int = 500,
) -> List[Path]:
    """Extract frames uniformly from video.
    
    Args:
        video_path: Input video
        output_dir: Directory to save frames
        max_frames: Maximum frames to extract
        
    Returns:
        List of extracted frame paths
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Get video duration to calculate frame interval
        cmd_probe = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=duration",
            "-of", "default=noprint_wrappers=1:nokey=1:noescapestr=1",
            str(video_path),
        ]
        result = subprocess.run(cmd_probe, capture_output=True, text=True, timeout=10)
        duration = float(result.stdout.strip()) if result.returncode == 0 else 30.0
        
        # Calculate frame rate to extract ~max_frames uniformly
        fps = max_frames / duration if duration > 0 else 1.0
        fps = min(fps, 10)  # Cap at 10 fps
        
        # Extract frames
        pattern = str(output_dir / "frame_%06d.png")
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", f"fps={fps}",
            "-q:v", "2",
            pattern,
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise KeyframeExtractionError(f"ffmpeg failed: {result.stderr}")
        
        frames = sorted(output_dir.glob("frame_*.png"))
        return frames
    
    except subprocess.TimeoutExpired:
        raise KeyframeExtractionError("Frame extraction timeout")
    except Exception as e:
        raise KeyframeExtractionError(f"Frame extraction failed: {e}")


def compute_optical_flow_shift(frame1: np.ndarray, frame2: np.ndarray) -> float:
    """Compute average optical flow magnitude between frames (parallax measure).
    
    Real-world analogy: Parallax = how much objects appear to shift between two viewpoints.
    Larger shifts = more baseline = better for 3D reconstruction.
    
    Args:
        frame1: First frame (H, W, 3) uint8
        frame2: Second frame (H, W, 3) uint8
        
    Returns:
        Average optical flow magnitude (pixels)
    """
    try:
        import cv2
        
        # Convert to grayscale
        gray1 = cv2.cvtColor(frame1, cv2.COLOR_RGB2GRAY)
        gray2 = cv2.cvtColor(frame2, cv2.COLOR_RGB2GRAY)
        
        # Compute dense optical flow (Lucas-Kanade)
        flow = cv2.calcOpticalFlowFarneback(
            gray1, gray2,
            pyr_scale=0.5,
            levels=3,
            winsize=15,
            iterations=3,
            n8=8,
            poly_n=5,
            poly_sigma=1.2,
            flags=0
        )
        
        # Magnitude of flow vectors
        magnitude, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])
        
        # Average non-zero flow
        valid_mag = magnitude[magnitude > 0.5]
        if len(valid_mag) == 0:
            return 0.0
        
        return float(np.mean(valid_mag))
    
    except ImportError:
        raise KeyframeExtractionError("OpenCV not installed; cannot compute optical flow")
    except Exception as e:
        raise KeyframeExtractionError(f"Optical flow computation failed: {e}")


def filter_frames_parallax(
    frames: List[Path],
    min_parallax_threshold: float = 5.0,
    target_frame_count: Optional[int] = None,
    downsample_for_flow: int = 2,
) -> Tuple[List[Path], List[float]]:
    """Filter frames based on parallax (optical flow between consecutive frames).
    
    Selects frames where significant scene motion (parallax) is detected,
    which indicates good baseline for 3D reconstruction.
    
    Args:
        frames: List of frame paths (assumed to be in order)
        min_parallax_threshold: Minimum optical flow to keep a frame (pixels)
        target_frame_count: If set, select top N frames by parallax (None = use threshold)
        downsample_for_flow: Downsampling factor for optical flow computation (speedup)
        
    Returns:
        Tuple of (selected_frames, parallax_scores)
    """
    if len(frames) < 2:
        return frames, [0.0] * len(frames)
    
    print(f"  Computing parallax scores for {len(frames)} frames...")
    
    parallax_scores = [0.0] * len(frames)
    selected_indices = [0]  # Always keep first frame
    
    try:
        for i in range(1, len(frames)):
            # Load frames (downsampled for speed)
            img1 = Image.open(frames[i-1]).convert("RGB")
            img2 = Image.open(frames[i]).convert("RGB")
            
            if downsample_for_flow > 1:
                new_w = img1.width // downsample_for_flow
                new_h = img1.height // downsample_for_flow
                img1 = img1.resize((new_w, new_h), Image.LANCZOS)
                img2 = img2.resize((new_w, new_h), Image.LANCZOS)
            
            # Compute optical flow
            arr1 = np.array(img1)
            arr2 = np.array(img2)
            flow_mag = compute_optical_flow_shift(arr1, arr2)
            parallax_scores[i] = flow_mag
            
            # Keep frame if parallax is above threshold
            if flow_mag >= min_parallax_threshold:
                selected_indices.append(i)
            
            if (i + 1) % max(1, len(frames) // 10) == 0:
                print(f"    {i+1}/{len(frames)} processed")
        
        # Always keep last frame
        if selected_indices[-1] != len(frames) - 1:
            selected_indices.append(len(frames) - 1)
        
        selected_indices = sorted(set(selected_indices))
        
        # If target frame count is set, select the top N frames by parallax
        if target_frame_count and len(selected_indices) > target_frame_count:
            scores_with_idx = [(parallax_scores[i], i) for i in selected_indices]
            scores_with_idx.sort(reverse=True)
            selected_indices = sorted([idx for _, idx in scores_with_idx[:target_frame_count]])
        
        selected_frames = [frames[i] for i in selected_indices]
        selected_scores = [parallax_scores[i] for i in selected_indices]
        
        print(f"  ✓ Selected {len(selected_frames)} keyframes from {len(frames)} total")
        print(f"    Parallax range: {min(selected_scores) if selected_scores else 0:.1f} - {max(selected_scores) if selected_scores else 0:.1f} px")
        
        return selected_frames, selected_scores
    
    except Exception as e:
        print(f"  ⚠ Parallax filtering failed ({e}), using uniform selection instead")
        # Fallback: uniform selection
        if target_frame_count:
            step = max(1, len(frames) // target_frame_count)
            selected = [frames[i] for i in range(0, len(frames), step)]
            return selected, parallax_scores
        else:
            return frames, parallax_scores


def downsample_frames(
    frames: List[Path],
    output_dir: Path,
    max_dimension: int = 1920,
) -> List[Path]:
    """Downsample frames to max dimension while preserving aspect ratio.
    
    Args:
        frames: Input frame paths
        output_dir: Output directory for downsampled frames
        max_dimension: Max width or height (default 1920 for 4K input)
        
    Returns:
        List of downsampled frame paths
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    downsampled = []
    print(f"  Downsampling {len(frames)} frames to max {max_dimension}px...")
    
    for i, frame_path in enumerate(frames):
        try:
            img = Image.open(frame_path).convert("RGB")
            
            # Calculate scale factor
            scale = max_dimension / max(img.width, img.height)
            if scale < 1.0:
                new_w = int(img.width * scale)
                new_h = int(img.height * scale)
                img = img.resize((new_w, new_h), Image.LANCZOS)
            
            # Save downsampled
            output_path = output_dir / f"frame_{i:06d}.png"
            img.save(output_path, quality=95)
            downsampled.append(output_path)
            
            if (i + 1) % max(1, len(frames) // 5) == 0:
                print(f"    {i+1}/{len(frames)} downsampled")
        
        except Exception as e:
            print(f"    ⚠ Failed to downsample {frame_path}: {e}")
    
    return downsampled


def run_stage1_frames(
    video_path: Path,
    output_dir: Path,
    tier_config: "TierConfig",  # From tiers.py
    capture_id: str,
) -> Dict[str, Any]:
    """Run Stage 1: Extract parallax-based keyframes.
    
    Args:
        video_path: Input video file
        output_dir: Output directory (frames/ subdirectory)
        tier_config: Tier configuration with frame_budget, max_dimension
        capture_id: Capture job identifier
        
    Returns:
        Dict with stage results:
        - extracted_frames: list of frame paths
        - frame_count: number of extracted frames
        - parallax_scores: list of parallax scores per frame
        - stage1_complete: whether stage passed
    """
    print(f"[{capture_id}] Stage 1: Parallax Keyframes")
    print(f"  Target frame budget: {tier_config.frame_budget}")
    print(f"  Max dimension: {tier_config.max_dimension}px")
    
    try:
        # Extract all frames uniformly first
        print(f"  Step 1: Extract uniform frames from video...")
        temp_dir = output_dir / "temp_uniform"
        all_frames = extract_frames_uniform(video_path, temp_dir, max_frames=1000)
        print(f"    Extracted {len(all_frames)} frames")
        
        # Filter by parallax
        print(f"  Step 2: Filter by parallax-based motion...")
        keyframes, parallax_scores = filter_frames_parallax(
            all_frames,
            min_parallax_threshold=3.0,
            target_frame_count=tier_config.frame_budget,
            downsample_for_flow=2,
        )
        
        # Downsample to max dimension
        print(f"  Step 3: Downsample keyframes...")
        final_frames = downsample_frames(keyframes, output_dir, tier_config.max_dimension)
        
        print(f"  ✓ Stage 1 complete: {len(final_frames)} keyframes extracted")
        
        return {
            "stage1_complete": True,
            "extracted_frames": [str(f.name) for f in final_frames],
            "frame_count": len(final_frames),
            "parallax_scores": parallax_scores[:len(final_frames)],
            "metrics": {
                "total_frames_in_video": len(all_frames),
                "keyframes_selected": len(final_frames),
                "mean_parallax_px": float(np.mean(parallax_scores)) if parallax_scores else 0.0,
                "max_parallax_px": float(np.max(parallax_scores)) if parallax_scores else 0.0,
            }
        }
    
    except KeyframeExtractionError as e:
        print(f"  ❌ Keyframe extraction error: {e}")
        return {
            "stage1_complete": False,
            "error": str(e),
        }
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "stage1_complete": False,
            "error": str(e),
        }


if __name__ == "__main__":
    # Quick test
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python stage1_frames.py <video_path> [frame_budget] [max_dimension]")
        sys.exit(1)
    
    video = Path(sys.argv[1])
    frame_budget = int(sys.argv[2]) if len(sys.argv) > 2 else 400
    max_dim = int(sys.argv[3]) if len(sys.argv) > 3 else 1920
    
    # Create a mock tier config
    class MockTier:
        def __init__(self, fb, md):
            self.frame_budget = fb
            self.max_dimension = md
    
    tier = MockTier(frame_budget, max_dim)
    output = Path("output/vantagecam/test_stage1/frames")
    
    result = run_stage1_frames(video, output, tier, "test_capture")
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2, default=str))
