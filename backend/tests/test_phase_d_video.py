"""Tiny codec fixtures test extraction boundaries, not reconstruction quality."""
import av
from PIL import Image
import pytest

from pipeline.video_processor import extract_keyframes_from_video


@pytest.fixture

def video(tmp_path):
    path = tmp_path / "numeric_codec_fixture.mp4"
    with av.open(str(path), "w") as container:
        stream = container.add_stream("mpeg4", rate=30)
        stream.width, stream.height, stream.pix_fmt = 160, 90, "yuv420p"
        for index in range(90):
            frame = av.VideoFrame.from_image(Image.new("RGB", (160, 90), (index * 2, 50, 100)))
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    return path


def test_covers_whole_video_preserves_aspect_and_does_not_claim_overlap(video, tmp_path):
    result = extract_keyframes_from_video(video, tmp_path / "frames", max_frames=8, target_width=96)
    assert result["extracted_frames_count"] == 8
    assert result["timestamps_seconds"][0] == 0
    assert result["timestamps_seconds"][-1] > 2.9
    assert result["overlap_verified"] is False
    assert all(b > a for a, b in zip(result["timestamps_seconds"], result["timestamps_seconds"][1:]))
    for name in result["frames"]:
        with Image.open(name) as image:
            assert image.size == (96, 54)


def test_existing_frames_never_deleted(video, tmp_path):
    output = tmp_path / "frames"
    output.mkdir()
    previous = output / "frame_00000.jpg"
    previous.write_bytes(b"preserve me")
    with pytest.raises(ValueError, match="fresh workspace"):
        extract_keyframes_from_video(video, output)
    assert previous.read_bytes() == b"preserve me"


@pytest.mark.parametrize("payload", [b"", b"not an MP4"])

def test_empty_and_corrupt_video_fails_without_substitute(tmp_path, payload):
    source = tmp_path / "bad.mp4"
    source.write_bytes(payload)
    with pytest.raises(ValueError, match="empty|decoded"):
        extract_keyframes_from_video(source, tmp_path / "frames")
    assert not list((tmp_path / "frames").glob("*.jpg"))


@pytest.mark.parametrize("count,width", [(0, 640), (4, 640), (121, 640), (24, 0), (24, 4096)])

def test_extraction_settings_validated(video, tmp_path, count, width):
    with pytest.raises(ValueError):
        extract_keyframes_from_video(video, tmp_path / "frames", count, width)


def test_explicit_resize_cannot_distort_intrinsics(video, tmp_path):
    with pytest.raises(ValueError, match="aspect ratio"):
        extract_keyframes_from_video(video, tmp_path / "frames", target_size=(100, 100))
