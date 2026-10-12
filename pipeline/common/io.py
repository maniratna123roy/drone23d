"""
Spatial Twin: I/O Utilities for PLY and Web SPLAT Binary Assets (pipeline/common/io.py)

Beginner Analogy:
A precision packing crate:
It takes ~1.5 million 3D Gaussian splats and tightly packs each one into exactly 32 bytes
so that a web browser can stream and render the 3D scene effortlessly at 60 FPS,
while ensuring not a single splat shifts position or loses its class label.
"""

import os
import struct
import numpy as np
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from plyfile import PlyData, PlyElement

def _numeric_array(name, values, shape):
    """Reject malformed arrays before NumPy can broadcast or silently cast them."""
    values = np.asarray(values)
    if values.ndim != len(shape) or any(
        expected is not None and actual != expected
        for actual, expected in zip(values.shape, shape)
    ):
        raise ValueError(f"{name} must have shape {shape}, matching positions; got {values.shape}")
    if values.dtype.kind not in "iuf" or not np.isfinite(values).all():
        raise ValueError(f"{name} must contain finite real numbers")
    return values


def _float32_array(name, values):
    # A finite float64 can overflow float32; a positive scale can become zero.
    with np.errstate(over="ignore", under="ignore"):
        result = values.astype(np.float32)
    if not np.isfinite(result).all():
        raise ValueError(f"{name} must be representable as finite float32 values")
    if name == "scales" and np.any(result <= 0):
        raise ValueError("scales must remain strictly positive in float32")
    return result


def _normalized_rotations(rotations, n):
    rotations = _numeric_array("rotations", rotations, (n, 4)).astype(np.float64)
    # Scaling first avoids overflow/underflow when squaring finite quaternions.
    magnitude = np.max(np.abs(rotations), axis=1, keepdims=True)
    if np.any(magnitude == 0):
        raise ValueError("rotations must contain nonzero WXYZ quaternions")
    with np.errstate(under="ignore"):
        unit = rotations / magnitude
        return unit / np.linalg.norm(unit, axis=1, keepdims=True)


def _rgba_array(colors, n, allow_rgb=False):
    colors = _numeric_array("colors", colors, (n, None))
    widths = (3, 4) if allow_rgb else (4,)
    if colors.shape[1] not in widths:
        raise ValueError(f"colors must have {widths} channels; .splat requires RGBA")
    if np.any((colors < 0) | (colors > 255)) or np.any(colors != np.floor(colors)):
        raise ValueError("colors must contain integer RGB/RGBA values in [0, 255]")
    colors = colors.astype(np.uint8)
    if colors.shape[1] == 3:
        colors = np.column_stack([colors, np.full(n, 255, dtype=np.uint8)])
    return colors


def load_ply(ply_path: str) -> Dict[str, np.ndarray]:
    """
    Loads 3D Gaussian Splats from a standard .ply file.
    Returns dictionary with:
      - positions: (N, 3) float32
      - scales: (N, 3) float32 (exponentiated or linear)
      - rotations: (N, 4) float32 normalized quaternions (w, x, y, z)
      - colors: (N, 4) uint8 RGBA
      - opacities: (N,) float32 in range [0, 1]
      - normals: (N, 3) float32, only when nx/ny/nz exist (not synthesized)
    Learned opacity logits take precedence over alpha and are also encoded into
    colors[:, 3] (nearest byte), so downstream .splat export retains opacity.
    """
    path = Path(ply_path)
    if not path.exists():
        raise FileNotFoundError(f"PLY file not found: {path}")

    plydata = PlyData.read(str(path))
    v = plydata["vertex"]
    fields = set(v.data.dtype.names)
    # Check complete property groups, not row values, and do not hide partial data.
    for group in (("x", "y", "z"), ("red", "green", "blue"),
                  ("f_dc_0", "f_dc_1", "f_dc_2"), ("nx", "ny", "nz"),
                  ("scale_0", "scale_1", "scale_2"),
                  ("rot_0", "rot_1", "rot_2", "rot_3")):
        if fields.intersection(group) and not fields.issuperset(group):
            raise ValueError(f"Incomplete PLY properties; missing {sorted(set(group) - fields)}")
    if not fields.issuperset(("x", "y", "z")):
        raise ValueError("PLY is missing x/y/z positions")

    positions = np.column_stack([v["x"], v["y"], v["z"]])
    positions = _float32_array("positions", _numeric_array("positions", positions, (None, 3)))
    n = positions.shape[0]

    # Handle colors
    if "red" in fields:
        colors = _rgba_array(np.column_stack([v["red"], v["green"], v["blue"]]), n, allow_rgb=True)
    elif "f_dc_0" in fields:
        # Spherical harmonics DC component to RGB: RGB = 0.5 + C0 * f_dc.
        dc = np.column_stack([v[f"f_dc_{i}"] for i in range(3)])
        dc = _numeric_array("SH colors", dc, (n, 3)).astype(np.float64)
        rgb = (np.clip(0.5 + 0.28209479177387814 * dc, 0, 1) * 255).astype(np.uint8)
        colors = np.column_stack([rgb, np.full(n, 255, dtype=np.uint8)])
    else:
        colors = np.full((n, 4), 200, dtype=np.uint8)
        colors[:, 3] = 255
    if "alpha" in fields:
        colors = _rgba_array(np.column_stack([colors[:, :3], v["alpha"]]), n)

    # Handle scales
    if "scale_0" in fields:
        log_scales = np.column_stack([v[f"scale_{i}"] for i in range(3)])
        log_scales = _numeric_array("log scales", log_scales, (n, 3)).astype(np.float64)
        with np.errstate(over="ignore", under="ignore"):
            scales = _float32_array("scales", np.exp(log_scales))
    else:
        scales = np.full((n, 3), 0.05, dtype=np.float32)

    # Handle rotations (quaternions)
    if "rot_0" in fields:
        rotations = np.column_stack([v[f"rot_{i}"] for i in range(4)])
        rotations = _normalized_rotations(rotations, n).astype(np.float32)
    else:
        rotations = np.zeros((n, 4), dtype=np.float32)
        rotations[:, 0] = 1.0  # Identity quaternion w=1

    # Handle opacity
    if "opacity" in fields:
        logits = v["opacity"].astype(np.float64)
        if np.isnan(logits).any():
            raise ValueError("PLY opacity logits must not contain NaN")
        # Stable sigmoid, including +/- infinity for exactly opaque/transparent.
        with np.errstate(under="ignore"):
            exp_neg_abs = np.exp(-np.abs(logits))
            opacities = np.where(logits >= 0, 1.0 / (1.0 + exp_neg_abs),
                                 exp_neg_abs / (1.0 + exp_neg_abs)).astype(np.float32)
        colors[:, 3] = np.rint(opacities * 255).astype(np.uint8)
    else:
        opacities = colors[:, 3].astype(np.float32) / 255.0

    result = {
        "positions": positions,
        "scales": scales,
        "rotations": rotations,
        "colors": colors,
        "opacities": opacities
    }
    if "nx" in fields:
        normals = np.column_stack([v["nx"], v["ny"], v["nz"]])
        result["normals"] = _float32_array("normals", _numeric_array("normals", normals, (n, 3)))
    return result

def save_ply(filepath: str, 
             positions: np.ndarray, 
             colors: np.ndarray, 
             scales: Optional[np.ndarray] = None, 
             rotations: Optional[np.ndarray] = None, 
             opacities: Optional[np.ndarray] = None):
    """
    Saves a 3D Gaussian Splat point cloud to a standard .ply file.
    Positive scales use natural logs without a size floor. Opacity defaults to
    RGBA alpha (opaque for RGB); exact 0/1 use -/+ infinity logit endpoints.
    """
    positions = _float32_array("positions", _numeric_array("positions", positions, (None, 3)))
    n = positions.shape[0]
    colors = _rgba_array(colors, n, allow_rgb=True)
    if scales is None:
        scales = np.full((n, 3), 0.08, dtype=np.float32)
    scales = _float32_array("scales", _numeric_array("scales", scales, (n, 3)))
    if rotations is None:
        rotations = np.zeros((n, 4), dtype=np.float32)
        rotations[:, 0] = 1.0
    rotations = _normalized_rotations(rotations, n)
    if opacities is None:
        opacities = colors[:, 3].astype(np.float64) / 255.0
    opacities = _numeric_array("opacities", opacities, (n,)).astype(np.float64)
    if np.any((opacities < 0) | (opacities > 1)):
        raise ValueError("opacities must be in [0, 1]")
    colors[:, 3] = np.rint(opacities * 255).astype(np.uint8)
    dtype = [
        ('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
        ('red', 'u1'), ('green', 'u1'), ('blue', 'u1'), ('alpha', 'u1'),
        ('scale_0', 'f4'), ('scale_1', 'f4'), ('scale_2', 'f4'),
        ('rot_0', 'f4'), ('rot_1', 'f4'), ('rot_2', 'f4'), ('rot_3', 'f4'),
        ('opacity', 'f4')
    ]
    v_data = np.empty(n, dtype=dtype)
    v_data['x'] = positions[:, 0].astype(np.float32)
    v_data['y'] = positions[:, 1].astype(np.float32)
    v_data['z'] = positions[:, 2].astype(np.float32)
    
    v_data['red'] = colors[:, 0].astype(np.uint8)
    v_data['green'] = colors[:, 1].astype(np.uint8)
    v_data['blue'] = colors[:, 2].astype(np.uint8)
    v_data['alpha'] = colors[:, 3].astype(np.uint8)
    
    v_data['scale_0'] = np.log(scales[:, 0].astype(np.float64)).astype(np.float32)
    v_data['scale_1'] = np.log(scales[:, 1].astype(np.float64)).astype(np.float32)
    v_data['scale_2'] = np.log(scales[:, 2].astype(np.float64)).astype(np.float32)
    
    v_data['rot_0'] = rotations[:, 0].astype(np.float32)
    v_data['rot_1'] = rotations[:, 1].astype(np.float32)
    v_data['rot_2'] = rotations[:, 2].astype(np.float32)
    v_data['rot_3'] = rotations[:, 3].astype(np.float32)
    
    with np.errstate(divide="ignore"):
        v_data['opacity'] = (np.log(opacities) - np.log1p(-opacities)).astype(np.float32)
    
    el = PlyElement.describe(v_data, 'vertex')
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    PlyData([el]).write(str(filepath))

def save_splat(positions: np.ndarray, 
               scales: np.ndarray, 
               rotations: np.ndarray, 
               colors: np.ndarray, 
               out_path: str):
    """
    Exports 3D Gaussian Splats into the standard web 32-byte .splat binary format.
    Format per splat (32 bytes):
      - position: 3 x float32 (12 bytes)
      - scale:    3 x float32 (12 bytes)
      - color:    4 x uint8 RGBA (4 bytes)
      - rotation: 4 x uint8 (4 bytes, normalized WXYZ quaternion, quantized)
    Rows are never sorted. RGBA bytes, including learned alpha, are preserved.
    All arrays must have the same length; invalid data raises ValueError before
    creating/truncating the output. Quaternion components lose up to 1/128.
    """
    positions = _numeric_array("positions", positions, (None, 3))
    n = positions.shape[0]
    pos_f32 = _float32_array("positions", positions)
    scale_f32 = _float32_array("scales", _numeric_array("scales", scales, (n, 3)))
    rotations = _normalized_rotations(rotations, n)
    rgba_u8 = _rgba_array(colors, n)

    # Standard WXYZ encoding: decode with (byte - 128) / 128, then normalize.
    rot_u8 = np.clip(rotations * 128.0 + 128.0, 0, 255).astype(np.uint8)

    # Pack into buffer
    # Structured array for zero-copy fast writing
    dtype = np.dtype([
        ("pos", "<f4", (3,)),
        ("scale", "<f4", (3,)),
        ("color", "u1", (4,)),
        ("rot", "u1", (4,))
    ])
    
    buffer = np.empty(n, dtype=dtype)
    buffer["pos"] = pos_f32
    buffer["scale"] = scale_f32
    buffer["color"] = rgba_u8
    buffer["rot"] = rot_u8
    
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        f.write(buffer.tobytes())

def save_classes(class_ids: np.ndarray, out_path: str):
    """
    Saves a 1-byte-per-splat class sidecar file (scene.classes.u8).
    Class IDs:
      0: Structure / Building
      1: Terrain / Ground
      2: Road
      3: Vegetation
      255: Unknown
    """
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    u8_data = class_ids.astype(np.uint8)
    with open(out, "wb") as f:
        f.write(u8_data.tobytes())

def load_classes(in_path: str) -> np.ndarray:
    """Loads a 1-byte-per-splat class sidecar file."""
    return np.fromfile(in_path, dtype=np.uint8)
