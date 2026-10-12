"""Extract actual frames across a video into a fresh per-upload workspace.

Sampling is a film contact sheet, not a promise of image overlap: only COLMAP's
subsequent feature tracks can establish whether the footage reconstructs.
"""
from pathlib import Path
from typing import Any, Dict, Optional
import math

import av
from PIL import Image


def extract_keyframes_from_video(
    video_path: str | Path,
    output_dir: str | Path = "./data/mill/images",
    max_frames: int = 24,
    target_width: int = 640,
    target_size: Optional[tuple[int, int]] = None,
) -> Dict[str, Any]:
    source, destination = Path(video_path), Path(output_dir)
    if not source.is_file() or source.stat().st_size == 0:
        raise ValueError("The uploaded video is empty or missing. Please choose a readable video.")
    if not 5 <= max_frames <= 120 or not 64 <= target_width <= 1920:
        raise ValueError("Use 5..120 keyframes and a width of 64..1920 pixels")
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("Frame extraction requires a fresh workspace; existing images are preserved")
    destination.mkdir(parents=True, exist_ok=True)
    try:
        with av.open(str(source)) as container:
            videos = list(container.streams.video)
            if not videos:
                raise ValueError("No video stream found. Please upload a camera recording.")
            stream = videos[0]
            width, height = stream.width, stream.height
            fps = float(stream.average_rate) if stream.average_rate else 0.
            duration = (float(stream.duration * stream.time_base) if stream.duration is not None
                        else float(container.duration or 0) / av.time_base)
            if (not math.isfinite(duration) or not 0 < duration <= 600
                    or not math.isfinite(fps) or not 0 < fps <= 240
                    or min(width, height) < 64 or width * height > 40_000_000):
                raise ValueError("Use a readable video up to 10 minutes, at least 64px, and at most 240fps / 40MP.")
            if target_size:
                if (len(target_size) != 2 or min(target_size) < 64 or max(target_size) > 1920
                        or abs(target_size[0] / target_size[1] - width / height) > 0.01):
                    raise ValueError("Keyframe dimensions must preserve the camera aspect ratio")
                size = target_size
            else:
                scale = min(1., target_width / width)
                size = (round(width * scale), round(height * scale))
            # Cover the whole recording, including its last decodable image. A cap
            # on frame count must not silently use only the first seconds of a flight.
            last_time = max(0., duration - 1 / fps)
            targets = [index * last_time / (max_frames - 1) for index in range(max_frames)]
            extracted, timestamps = [], []
            first_time = None
            decoded = 0
            for frame in container.decode(stream):
                timestamp = float(frame.time) if frame.time is not None else decoded / fps
                decoded += 1
                if first_time is None:
                    first_time = timestamp
                timestamp -= first_time
                if len(extracted) >= max_frames:
                    break
                if timestamp + 0.5 / fps < targets[len(extracted)]:
                    continue
                if (frame.width, frame.height) != (width, height):
                    raise ValueError("Video dimensions change mid-recording; upload one continuous camera shot")
                image = frame.to_image().convert("RGB")
                if image.size != size:
                    image = image.resize(size, Image.Resampling.LANCZOS)
                path = destination / f"frame_{len(extracted):05d}.jpg"
                image.save(path, quality=95)
                extracted.append(str(path))
                timestamps.append(round(timestamp, 6))
            if len(extracted) < 5:
                raise ValueError("Fewer than five usable frames were decoded; upload a longer continuous camera shot")
            return {
                "video_name": source.name, "width": width, "height": height,
                "fps": fps, "duration_seconds": duration,
                "extracted_frames_count": len(extracted), "output_directory": str(destination),
                "frames": extracted, "timestamps_seconds": timestamps,
                "frame_width": size[0], "frame_height": size[1],
                "overlap_verified": False,
            }
    except av.error.FFmpegError as exc:
        raise ValueError("The video could not be decoded. Please try a non-corrupted MP4 or MOV camera recording.") from exc
