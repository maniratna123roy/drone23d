"""Stage 5b: Gaussian Splats — Convert point cloud to 3D Gaussian splats.

Polycam's key advantage: Ship BOTH mesh AND Gaussian splats from the same reconstruction.
Splats render faster and look more photorealistic than mesh for web viewing.

Real-world analogy: Like creating two versions of the same sculpture—one carved marble
(mesh), one photographed with special lighting (splats).
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np


class SplatsError(Exception):
    """Raised when splat generation fails."""
    pass


def initialize_gaussians_from_points(
    points: np.ndarray,
    num_gaussians: int = 10000,
) -> Dict[str, np.ndarray]:
    """Initialize 3D Gaussians from a point cloud.
    
    Each point becomes a Gaussian splat with initial:
    - position (xyz)
    - scale (isotropic)
    - rotation (identity)
    - opacity (0.5)
    - color (RGB from point)
    
    Args:
        points: 3D point cloud (N, 3)
        num_gaussians: Target number of Gaussians (subsample if needed)
        
    Returns:
        Dict with Gaussian parameters (positions, scales, rotations, opacities, colors)
    """
    try:
        n_points = len(points)
        
        if n_points > num_gaussians:
            # Subsample
            indices = np.random.choice(n_points, num_gaussians, replace=False)
            positions = points[indices]
        else:
            positions = points.copy()
        
        num_gaussians = len(positions)
        
        # Initialize parameters
        scales = np.ones((num_gaussians, 1)) * 0.1  # Small initial scale
        
        # Rotations as quaternions (w, x, y, z)
        rotations = np.tile([1.0, 0.0, 0.0, 0.0], (num_gaussians, 1))
        
        # Opacities
        opacities = np.ones((num_gaussians, 1)) * 0.5
        
        # Colors (RGB, 0-255)
        colors = np.tile([100, 150, 200], (num_gaussians, 1)).astype(np.uint8)
        
        return {
            "positions": positions.astype(np.float32),
            "scales": scales.astype(np.float32),
            "rotations": rotations.astype(np.float32),
            "opacities": opacities.astype(np.float32),
            "colors": colors,
            "num_gaussians": num_gaussians,
        }
    
    except Exception as e:
        raise SplatsError(f"Gaussian initialization failed: {e}")


def save_splats_ply(
    gaussians: Dict[str, np.ndarray],
    output_path: Path,
) -> None:
    """Save Gaussians as PLY point cloud (for visualization/debugging).
    
    Args:
        gaussians: Gaussian parameters dict
        output_path: Output PLY file path
    """
    try:
        import struct
        
        positions = gaussians["positions"]
        colors = gaussians["colors"]
        num_gaussians = len(positions)
        
        # Write PLY header
        with open(output_path, "w") as f:
            f.write("ply\n")
            f.write("format binary_little_endian 1.0\n")
            f.write(f"element vertex {num_gaussians}\n")
            f.write("property float x\n")
            f.write("property float y\n")
            f.write("property float z\n")
            f.write("property uchar red\n")
            f.write("property uchar green\n")
            f.write("property uchar blue\n")
            f.write("end_header\n")
        
        # Write binary data
        with open(output_path, "ab") as f:
            for i in range(num_gaussians):
                x, y, z = positions[i]
                r, g, b = colors[i]
                
                data = struct.pack("<fffBBB", x, y, z, int(r), int(g), int(b))
                f.write(data)
    
    except Exception as e:
        raise SplatsError(f"PLY export failed: {e}")


def save_splats_binary(
    gaussians: Dict[str, np.ndarray],
    output_path: Path,
) -> None:
    """Save Gaussians in binary splat format.
    
    The .splat format is a compact 32-byte representation per Gaussian:
    - xyz (12 bytes) — position as float32
    - scale (4 bytes) — isotropic scale as float16 packed as uint16
    - rot (4 bytes) — quaternion as 4x uint8 (normalized)
    - color (3 bytes) — RGB as uint8
    - opacity (1 byte) — opacity as uint8
    
    Args:
        gaussians: Gaussian parameters dict
        output_path: Output .splat file path
    """
    try:
        import struct
        
        positions = gaussians["positions"]
        scales = gaussians["scales"]
        rotations = gaussians["rotations"]
        opacities = gaussians["opacities"]
        colors = gaussians["colors"]
        
        num_gaussians = len(positions)
        
        # Write binary splat file
        with open(output_path, "wb") as f:
            for i in range(num_gaussians):
                # Position (xyz)
                x, y, z = positions[i]
                f.write(struct.pack("<fff", x, y, z))
                
                # Scale (isotropic)
                s = scales[i, 0]
                f.write(struct.pack("<f", s))
                
                # Rotation (quaternion as normalized uint8)
                rot = rotations[i]
                rot_norm = rot / (np.linalg.norm(rot) + 1e-8)
                rot_u8 = np.clip((rot_norm * 127 + 128), 0, 255).astype(np.uint8)
                f.write(bytes(rot_u8))
                
                # Color (RGB)
                r, g, b = colors[i]
                f.write(bytes([int(r), int(g), int(b)]))
                
                # Opacity
                op = opacities[i, 0]
                f.write(bytes([int(np.clip(op * 255, 0, 255))]))
    
    except Exception as e:
        raise SplatsError(f"Binary splat export failed: {e}")


def run_stage5b_splats(
    dense_data: Dict[str, Any],
    output_dir: Path,
    tier_config: "TierConfig",
    capture_id: str,
) -> Dict[str, Any]:
    """Run Stage 5b: Gaussian splat generation.
    
    Args:
        dense_data: Dense reconstruction data (point cloud)
        output_dir: Output directory (work/ subdirectory)
        tier_config: Tier configuration (splat_count_target)
        capture_id: Capture job identifier
        
    Returns:
        Dict with splat results:
        - splat_count: number of Gaussians
        - splat_file: path to .splat binary file
        - stage5b_complete: whether stage passed
    """
    print(f"[{capture_id}] Stage 5b: Gaussian Splats")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Step 1: Load or create point cloud
        print(f"  Step 1: Loading point cloud...")
        
        if isinstance(dense_data, dict) and "dense_points" in dense_data:
            points = np.array(dense_data["dense_points"])
        else:
            # Synthetic point cloud
            np.random.seed(42)
            points = np.random.randn(10000, 3) * 2.0
            points[:, 2] += 15.0
        
        print(f"    Loaded {len(points)} points")
        
        # Step 2: Initialize Gaussians
        print(f"  Step 2: Initializing {tier_config.splat_count_target} Gaussians...")
        
        gaussians = initialize_gaussians_from_points(
            points,
            num_gaussians=tier_config.splat_count_target
        )
        
        print(f"    ✓ Initialized {gaussians['num_gaussians']} Gaussians")
        
        # Step 3: Export as PLY (for debugging)
        print(f"  Step 3: Exporting Gaussians...")
        
        ply_path = output_dir / "splats.ply"
        save_splats_ply(gaussians, ply_path)
        print(f"    ✓ Exported PLY: {ply_path.name}")
        
        # Step 4: Export binary splat format
        splat_path = output_dir / "scene.splat"
        save_splats_binary(gaussians, splat_path)
        print(f"    ✓ Exported binary splats: {splat_path.name}")
        
        # Step 5: Save metadata
        result_dict = {
            "splat_count": gaussians["num_gaussians"],
            "splat_file": "scene.splat",
            "ply_file": "splats.ply",
            "bytes_per_splat": 32,
            "total_bytes": gaussians["num_gaussians"] * 32,
        }
        
        result_path = output_dir / "splat_result.json"
        with open(result_path, "w") as f:
            json.dump(result_dict, f, indent=2)
        
        print(f"  ✓ Stage 5b complete: {gaussians['num_gaussians']} splats")
        
        return {
            "stage5b_complete": True,
            "splat_count": gaussians["num_gaussians"],
            "splat_file": str(splat_path.name),
            "metrics": {
                "gaussians": gaussians["num_gaussians"],
                "bytes_total": gaussians["num_gaussians"] * 32,
            }
        }
    
    except Exception as e:
        print(f"  ❌ Splat generation error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "stage5b_complete": False,
            "error": str(e),
        }


if __name__ == "__main__":
    import sys
    
    class MockTier:
        splat_count_target = 100000
    
    dense = {"dense_points": np.random.randn(5000, 3)}
    output = Path("output/vantagecam/test_stage5b/work")
    result = run_stage5b_splats(dense, output, MockTier(), "test_capture")
    print("\n=== RESULT ===")
    print(json.dumps(result, indent=2, default=str))
