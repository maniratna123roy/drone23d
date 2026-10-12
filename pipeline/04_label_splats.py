"""Stage 04: label actual points using camera-aligned masks and geometric depth.

Like several slide projectors painting the same statue: only visible, agreeing
views count. Height, array length and old labels are never evidence of a class.
For the verified upload flow use pipeline.semantic_classification instead.
"""
import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from PIL import Image

from pipeline.common.io import load_ply
from pipeline.colmap_reconstructor import parse_colmap_reconstruction
from pipeline.dense_reconstruction import read_colmap_depth
from pipeline.semantic_classification import add_visible_votes, consensus_labels


def label_splats_from_masks(ply_path="./output/mill/point_cloud.ply", masks_dir="./output/masks",
                            output_labels_path="./output/mill/labels.npy", force_recompute=False,
                            phase_b_workspace=None):
    if phase_b_workspace is None:
        raise ValueError("Splat classification needs matching undistorted cameras and geometric depth; provide phase_b_workspace. Elevation guesses are disabled.")
    root = Path(phase_b_workspace)
    points = load_ply(ply_path)["positions"]
    poses, cameras, _, _ = parse_colmap_reconstruction(root / "undistorted_sparse_txt")
    if len(poses) < 2 or not np.isfinite(points).all():
        raise ValueError("Classification requires finite points and at least two registered cameras")
    votes = np.zeros((len(points), 4), dtype=np.uint32)
    visible = np.zeros(len(points), dtype=np.uint32)
    for name, pose in poses.items():
        with Image.open(Path(masks_dir) / f"{Path(name).stem}_mask.png") as image:
            mask = np.array(image)
        depth = read_colmap_depth(root / "dense/stereo/depth_maps" / f"{name}.geometric.bin")
        add_visible_votes(points, pose, cameras[pose["camera_id"]], depth, mask, votes, visible)
    labels, _ = consensus_labels(votes, visible)
    output = Path(output_labels_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    np.save(output, labels)
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ply", required=True)
    parser.add_argument("--masks", required=True)
    parser.add_argument("--phase-b", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    label_splats_from_masks(args.ply, args.masks, args.output, phase_b_workspace=args.phase_b)
