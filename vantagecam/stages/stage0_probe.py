"""Stage 0: Probe — Validate video input and extract metadata.

Real-world analogy: Like a customs agent — check the package exists, has the right label,
isn't corrupt, and copy down the serial numbers for the manifest.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Any
import subprocess


class ProbeError(Exception):
    """Raised when video validation fails."""
    pass


def get_video_metadata(video_path: Path) -> Dict[str, Any]:
    """Extract video metadata using ffprobe.
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dict with duration_s, fps, resolution (WxH), codec, bitrate_mbps, frame_count
        
    Raises:
        ProbeError: If ffprobe fails or file is invalid
    """
    if not video_path.exists():
        raise ProbeError(f"Video file not found: {video_path}")
    
    try:
        # Run ffprobe to get video metadata
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=duration,r_frame_rate,width,height,codec_name,bit_rate",
            "-of", "json",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            raise ProbeError(f"ffprobe failed: {result.stderr}")
        
        data = json.loads(result.stdout)
        if not data.get("streams"):
            raise ProbeError("No video stream found in file")
        
        stream = data["streams"][0]
        
        # Parse frame rate (e.g., "30/1" or "60000/1001")
        fps_str = stream.get("r_frame_rate", "30/1")
        fps_parts = fps_str.split("/")
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 30.0
        
        # Extract values
        duration = float(stream.get("duration", 0))
        width = int(stream.get("width", 0))
        height = int(stream.get("height", 0))
        codec = stream.get("codec_name", "unknown")
        bitrate_bits = int(stream.get("bit_rate", 0))
        bitrate_mbps = bitrate_bits / 1_000_000 if bitrate_bits > 0 else 0
        frame_count = int(duration * fps) if duration > 0 else 0
        
        return {
            "duration_s": duration,
            "fps": fps,
            "resolution": f"{width}x{height}",
            "width": width,
            "height": height,
            "codec": codec,
            "bitrate_mbps": bitrate_mbps,
            "frame_count": frame_count,
            "file_size_bytes": video_path.stat().st_size,
        }
    
    except subprocess.TimeoutExpired:
        raise ProbeError("ffprobe timeout (video may be corrupt)")
    except json.JSONDecodeError as e:
        raise ProbeError(f"ffprobe output parsing failed: {e}")
    except Exception as e:
        raise ProbeError(f"Unexpected ffprobe error: {e}")


def validate_video(video_path: Path, min_frames: int = 10, max_frames: int = 10000) -> Dict[str, Any]:
    """Validate video meets minimum requirements.
    
    Args:
        video_path: Path to video file
        min_frames: Minimum frame requirement (default: 10)
        max_frames: Maximum frame requirement (default: 10000)
        
    Returns:
        Dict with metadata + validation results (valid: bool, issues: list)
        
    Raises:
        ProbeError: On critical errors
    """
    metadata = get_video_metadata(video_path)
    
    issues = []
    
    # Check frame count
    if metadata["frame_count"] < min_frames:
        issues.append(f"Too few frames: {metadata['frame_count']} < {min_frames}")
    
    if metadata["frame_count"] > max_frames:
        issues.append(f"Too many frames: {metadata['frame_count']} > {max_frames}")
    
    # Check resolution (must be at least 640x480)
    if metadata["width"] < 640 or metadata["height"] < 480:
        issues.append(f"Resolution too low: {metadata['resolution']} (minimum 640x480)")
    
    # Check duration
    if metadata["duration_s"] < 1.0:
        issues.append(f"Video too short: {metadata['duration_s']:.1f}s (minimum 1s)")
    
    # Check codec (warn if unusual)
    allowed_codecs = ["h264", "h265", "hevc", "vp8", "vp9", "av1", "mpeg4", "prores"]
    if metadata["codec"].lower() not in allowed_codecs:
        issues.append(f"Unusual codec: {metadata['codec']} (will still try to process)")
    
    is_valid = len(issues) == 0
    
    return {
        **metadata,
        "valid": is_valid,
        "issues": issues,
    }


def extract_keyframes_ffmpeg(
    video_path: Path,
    output_dir: Path,
    max_keyframes: int = 500,
) -> Dict[str, Any]:
    """Extract keyframes from video using ffmpeg.
    
    Real-world analogy: Like taking snapshots at key moments during a walk-through,
    rather than capturing every step.
    
    Args:
        video_path: Input video file
        output_dir: Directory to save extracted frames
        max_keyframes: Maximum number of keyframes to extract
        
    Returns:
        Dict with frame_count, extracted_frames, fps, and timing info
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Use ffmpeg to extract keyframes (scene changes) or regular intervals
        # The 'fps=1/<interval>' filter extracts N frames uniformly
        metadata = get_video_metadata(video_path)
        
        # Calculate frame interval to get approximately max_keyframes
        target_fps = max(1, metadata["frame_count"] // max_keyframes)
        
        # Extract frames
        pattern = str(output_dir / "frame_%06d.png")
        cmd = [
            "ffmpeg",
            "-i", str(video_path),
            "-vf", f"fps=1/{target_fps}",
            "-q:v", "2",  # Quality 2 (high quality)
            pattern,
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode != 0:
            raise ProbeError(f"ffmpeg frame extraction failed: {result.stderr}")
        
        # Count extracted frames
        extracted_frames = sorted(output_dir.glob("frame_*.png"))
        
        return {
            "frame_count": len(extracted_frames),
            "extracted_frames": [f.name for f in extracted_frames],
            "fps": metadata["fps"],
            "resolution": metadata["resolution"],
            "duration_s": metadata["duration_s"],
            "extraction_method": "uniform_interval",
        }
    
    except subprocess.TimeoutExpired:
        raise ProbeError("Frame extraction timeout")
    except Exception as e:
        raise ProbeError(f"Frame extraction failed: {e}")


def run_stage0_probe(video_path: Path, capture_id: str) -> Dict[str, Any]:
    """Run Stage 0: Probe — validate video and extract basic metadata.
    
    Args:
        video_path: Path to input video
        capture_id: Capture job identifier (for logging/status)
        
    Returns:
        Dict with probe results:
        - metadata: video properties (fps, resolution, duration, frame_count, etc.)
        - valid: whether video passes validation
        - issues: list of validation warnings/errors
        - stage0_complete: whether stage can proceed
    """
    print(f"[{capture_id}] Stage 0: Probe — Validating input video")
    print(f"  Video: {video_path}")
    
    try:
        # Validate video
        validation = validate_video(video_path, min_frames=10, max_frames=10000)
        
        if not validation["valid"]:
            print(f"  ❌ Video validation FAILED:")
            for issue in validation["issues"]:
                print(f"     - {issue}")
            return {
                "valid": False,
                "issues": validation["issues"],
                "stage0_complete": False,
                "metadata": validation,
            }
        
        # All checks passed
        print(f"  ✓ Video validation PASSED")
        print(f"    - Resolution: {validation['resolution']}")
        print(f"    - Duration: {validation['duration_s']:.1f}s")
        print(f"    - FPS: {validation['fps']:.1f}")
        print(f"    - Frame count: {validation['frame_count']}")
        print(f"    - Codec: {validation['codec']}")
        print(f"    - File size: {validation['file_size_bytes'] / 1_000_000:.1f} MB")
        
        return {
            "valid": True,
            "issues": [],
            "stage0_complete": True,
            "metadata": validation,
        }
    
    except ProbeError as e:
        print(f"  ❌ Probe error: {e}")
        return {
            "valid": False,
            "issues": [str(e)],
            "stage0_complete": False,
            "error": str(e),
        }
    except Exception as e:
        print(f"  ❌ Unexpected error: {e}")
        return {
            "valid": False,
            "issues": [f"Unexpected error: {str(e)}"],
            "stage0_complete": False,
            "error": str(e),
        }


if __name__ == "__main__":
    # Quick test
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python stage0_probe.py <video_path>")
        sys.exit(1)
    
    video = Path(sys.argv[1])
    result = run_stage0_probe(video, "test_capture")
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2, default=str))
