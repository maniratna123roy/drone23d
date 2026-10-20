"""OpenRouter AI 3D Reconstruction Engine.

Converts drone video footage into a complete 3D digital twin (.glb and .obj)
using OpenRouter Multimodal Vision models (e.g. Nemotron VL, Gemini, GPT-4o).
"""

import os
import json
import base64
import math
import struct
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import cv2
import numpy as np
import httpx

from backend.config import settings

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"


def extract_video_keyframes(video_path: Path, max_frames: int = 6, max_dim: int = 720) -> List[Tuple[np.ndarray, str]]:
    """Extracts sharpest, evenly spaced keyframes from a video file and encodes them to base64 JPEG."""
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise ValueError(f"Unable to open video file at {video_path}")

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    if total_frames <= 0:
        total_frames = 100

    # Distribute frame candidate windows across the middle 85% of the video
    start_frame = int(total_frames * 0.08)
    end_frame = int(total_frames * 0.92)
    step = max(1, (end_frame - start_frame) // max_frames)
    
    frames_b64 = []

    for i in range(max_frames):
        target_idx = start_frame + i * step
        # Look around target_idx (+- 3 frames) to pick the sharpest frame (highest Laplacian variance)
        best_frame = None
        best_score = -1.0

        for offset in (-3, 0, 3):
            cand_idx = max(0, min(total_frames - 1, target_idx + offset))
            cap.set(cv2.CAP_PROP_POS_FRAMES, cand_idx)
            ret, frame = cap.read()
            if not ret or frame is None:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if score > best_score:
                best_score = score
                best_frame = frame

        if best_frame is None:
            continue

        h, w = best_frame.shape[:2]
        scale = min(1.0, max_dim / max(h, w))
        if scale < 1.0:
            best_frame = cv2.resize(best_frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

        _, buf = cv2.imencode(".jpg", best_frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        b64 = base64.b64encode(buf.tobytes()).decode("utf-8")
        frames_b64.append((best_frame, b64))

    cap.release()
    return frames_b64


async def call_openrouter_vision(
    keyframes_b64: List[str],
    user_prompt: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """Sends extracted drone keyframes to OpenRouter Vision model and retrieves structured 3D spatial layout."""
    active_key = api_key or settings.OPENROUTER_API_KEY
    if not active_key:
        raise ValueError("Missing OpenRouter API Key. Please provide an API key or configure OPENROUTER_API_KEY in .env.")

    active_model = model or settings.OPENROUTER_DEFAULT_MODEL or "nvidia/nemotron-3.5-super-vl:free"

    # Assemble multimodal system directive
    directive_lines = [
        "You are an expert 3D Architectural Photogrammetry AI.",
        "Analyze these drone aerial survey keyframes and deduce the exact physical 3D scene layout.",
    ]
    if user_prompt and user_prompt.strip():
        directive_lines.append(
            f"\nCRITICAL USER ARCHITECTURAL DIRECTIVE:\n\"{user_prompt.strip()}\"\n"
            "You MUST strictly follow this directive when sizing, positioning, coloring, and detailing the 3D structures.\n"
        )

    directive_lines.append(
        "Output STRICTLY valid JSON (no markdown formatting, no code fences, just JSON) with the following structure:\n\n"
        "{\n"
        '  "scene_title": "Descriptive scene name",\n'
        '  "confidence_score": 95,\n'
        '  "architectural_summary": "Comprehensive summary of visible buildings, heights, road network, and layout",\n'
        '  "terrain": {\n'
        '    "size_x": 140.0,\n'
        '    "size_y": 140.0,\n'
        '    "color_rgb": [85, 115, 80]\n'
        "  },\n"
        '  "roads": [\n'
        '    {"start": [-60, -20], "end": [60, -20], "width": 8.0, "color_rgb": [55, 55, 60], "has_markings": true, "has_sidewalk": true}\n'
        "  ],\n"
        '  "buildings": [\n'
        "    {\n"
        '      "name": "Central Highrise Tower",\n'
        '      "center": [0.0, 10.0, 0.0],\n'
        '      "dimensions": [24.0, 18.0, 42.0],\n'
        '      "rotation_deg": 15.0,\n'
        '      "roof_type": "flat",\n'
        '      "floors": 12,\n'
        '      "facade_color_rgb": [210, 215, 225],\n'
        '      "roof_color_rgb": [70, 75, 85],\n'
        '      "window_color_rgb": [55, 80, 110],\n'
        '      "features": ["glass curtain wall", "mechanical penthouse", "roof parapet"]\n'
        "    }\n"
        "  ],\n"
        '  "vegetation": [\n'
        '    {"center": [-25.0, 20.0], "radius": 5.0, "height": 7.0, "color_rgb": [40, 95, 35]}\n'
        "  ]\n"
        "}\n"
        "Ground plane is at Z=0. All dimensions and coordinates must be in meters."
    )

    content_parts: List[Dict[str, Any]] = [
        {"type": "text", "text": "\n".join(directive_lines)}
    ]

    for b64 in keyframes_b64:
        content_parts.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
        })

    headers = {
        "Authorization": f"Bearer {active_key}",
        "HTTP-Referer": "https://spatial-twin.local",
        "X-Title": "Spatial Twin AI 3D",
        "Content-Type": "application/json",
    }

    payload = {
        "model": active_model,
        "messages": [{"role": "user", "content": content_parts}],
        "temperature": 0.2,
    }

    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(OPENROUTER_API_URL, headers=headers, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"OpenRouter API returned status {resp.status_code}: {resp.text}")

        res_json = resp.json()
        raw_text = res_json["choices"][0]["message"]["content"].strip()

        # Clean any potential markdown code fences from LLM response
        if raw_text.startswith("```"):
            raw_text = raw_text.split("\n", 1)[1]
            if raw_text.endswith("```"):
                raw_text = raw_text.rsplit("```", 1)[0]
        raw_text = raw_text.strip()

        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            # Fallback heuristic: search for the first '{' and last '}'
            start = raw_text.find("{")
            end = raw_text.rfind("}")
            if start != -1 and end != -1:
                return json.loads(raw_text[start:end + 1])
            raise ValueError(f"Could not parse valid JSON from OpenRouter vision output: {raw_text[:200]}")


def compute_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Computes per-vertex surface normals from triangular mesh faces."""
    normals = np.zeros_like(vertices, dtype=np.float32)
    if len(vertices) == 0 or len(faces) == 0:
        return normals

    v0 = vertices[faces[:, 0]]
    v1 = vertices[faces[:, 1]]
    v2 = vertices[faces[:, 2]]
    cross = np.cross(v1 - v0, v2 - v0)
    norm = np.linalg.norm(cross, axis=1, keepdims=True)
    norm[norm < 1e-8] = 1.0
    face_normals = cross / norm

    for i in range(3):
        normals[faces[:, i]] = face_normals
    return normals


def synthesize_3d_geometry(scene_data: Dict[str, Any]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Takes structured architectural vision output and generates clean 3D vertices, faces, and vertex colors."""
    vertices: List[List[float]] = []
    faces: List[List[int]] = []
    colors: List[List[int]] = []

    def add_quad(v0, v1, v2, v3, rgb):
        base_idx = len(vertices)
        vertices.extend([v0, v1, v2, v3])
        colors.extend([[*rgb, 255]] * 4)
        faces.append([base_idx, base_idx + 1, base_idx + 2])
        faces.append([base_idx, base_idx + 2, base_idx + 3])

    def add_tri(v0, v1, v2, rgb):
        base_idx = len(vertices)
        vertices.extend([v0, v1, v2])
        colors.extend([[*rgb, 255]] * 3)
        faces.append([base_idx, base_idx + 1, base_idx + 2])

    # 1. Terrain Ground Plane
    terrain = scene_data.get("terrain", {})
    t_sx = float(terrain.get("size_x", 140.0)) / 2.0
    t_sy = float(terrain.get("size_y", 140.0)) / 2.0
    t_col = terrain.get("color_rgb", [82, 112, 75])

    # Ground quad at Z = 0.0
    add_quad(
        [-t_sx, -t_sy, 0.0],
        [t_sx, -t_sy, 0.0],
        [t_sx, t_sy, 0.0],
        [-t_sx, t_sy, 0.0],
        t_col,
    )

    # 2. Roads & Sidewalk Infrastructure
    for road in scene_data.get("roads", []):
        p1 = road.get("start", [-50, -15])
        p2 = road.get("end", [50, -15])
        width = float(road.get("width", 8.0))
        r_col = road.get("color_rgb", [50, 50, 55])
        has_markings = road.get("has_markings", True)
        has_sidewalk = road.get("has_sidewalk", True)

        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        length = math.hypot(dx, dy)
        if length < 1e-4:
            continue
        nx = -dy / length * (width / 2.0)
        ny = dx / length * (width / 2.0)

        # Sidewalk verges on both sides
        if has_sidewalk:
            sw_w = 1.4
            sw_col = [165, 170, 175]
            snx = -dy / length * ((width / 2.0) + sw_w)
            sny = dx / length * ((width / 2.0) + sw_w)
            # Left sidewalk
            add_quad(
                [p1[0] + snx, p1[1] + sny, 0.03],
                [p1[0] + nx, p1[1] + ny, 0.03],
                [p2[0] + nx, p2[1] + ny, 0.03],
                [p2[0] + snx, p2[1] + sny, 0.03],
                sw_col,
            )
            # Right sidewalk
            add_quad(
                [p1[0] - nx, p1[1] - ny, 0.03],
                [p1[0] - snx, p1[1] - sny, 0.03],
                [p2[0] - snx, p2[1] - sny, 0.03],
                [p2[0] - nx, p2[1] - ny, 0.03],
                sw_col,
            )

        # Asphalt Road Surface (Elevated slightly to Z = 0.04 to prevent Z-fighting)
        add_quad(
            [p1[0] + nx, p1[1] + ny, 0.04],
            [p1[0] - nx, p1[1] - ny, 0.04],
            [p2[0] - nx, p2[1] - ny, 0.04],
            [p2[0] + nx, p2[1] + ny, 0.04],
            r_col,
        )

        # Dashed White Center Line Markings
        if has_markings and length > 6.0:
            dash_len = 3.0
            gap_len = 2.0
            cur_dist = 1.0
            line_w = 0.25
            lnx = -dy / length * (line_w / 2.0)
            lny = dx / length * (line_w / 2.0)
            white_col = [235, 235, 240]

            while cur_dist + dash_len <= length:
                t_start = cur_dist / length
                t_end = (cur_dist + dash_len) / length
                d1 = [p1[0] + dx * t_start, p1[1] + dy * t_start]
                d2 = [p1[0] + dx * t_end, p1[1] + dy * t_end]
                add_quad(
                    [d1[0] + lnx, d1[1] + lny, 0.05],
                    [d1[0] - lnx, d1[1] - lny, 0.05],
                    [d2[0] - lnx, d2[1] - lny, 0.05],
                    [d2[0] + lnx, d2[1] + lny, 0.05],
                    white_col,
                )
                cur_dist += dash_len + gap_len

    # 3. Buildings & Architectural Structures
    buildings = scene_data.get("buildings", [])
    if not buildings:
        buildings = [{
            "name": "Survey Structure",
            "center": [0, 0, 0],
            "dimensions": [22, 16, 24],
            "rotation_deg": 0,
            "roof_type": "flat",
            "floors": 6,
            "facade_color_rgb": [200, 205, 215],
            "roof_color_rgb": [65, 70, 80],
            "window_color_rgb": [55, 80, 110],
            "features": ["glass curtain wall", "mechanical penthouse"],
        }]

    for bldg in buildings:
        cx, cy, _ = bldg.get("center", [0, 0, 0])
        wx, wy, wz = bldg.get("dimensions", [15, 15, 20])
        rot = math.radians(float(bldg.get("rotation_deg", 0.0)))
        roof_type = bldg.get("roof_type", "flat").lower()
        floors = int(bldg.get("floors", max(1, int(wz / 3.5))))
        f_col = bldg.get("facade_color_rgb", [195, 205, 215])
        r_col = bldg.get("roof_color_rgb", [65, 70, 80])
        w_col = bldg.get("window_color_rgb", [55, 80, 110])
        features = [f.lower() for f in bldg.get("features", [])]

        hx, hy = wx / 2.0, wy / 2.0
        cos_r, sin_r = math.cos(rot), math.sin(rot)

        def rot_pt(lx, ly, lz):
            rx = lx * cos_r - ly * sin_r + cx
            ry = lx * sin_r + ly * cos_r + cy
            return [rx, ry, lz]

        # Multi-Story Facade Subdivision (Floor & Glass Curtain Bands)
        if floors > 1 and wz >= 6.0:
            floor_h = wz / floors
            for fl in range(floors):
                z_bot = fl * floor_h
                z_top = (fl + 1) * floor_h
                z_spandrel = z_bot + floor_h * 0.35  # lower 35% solid spandrel, upper 65% window glass

                # 4 bottom corners for this floor level
                fb0 = rot_pt(-hx, -hy, z_bot)
                fb1 = rot_pt(hx, -hy, z_bot)
                fb2 = rot_pt(hx, hy, z_bot)
                fb3 = rot_pt(-hx, hy, z_bot)

                # Spandrel division line
                fs0 = rot_pt(-hx, -hy, z_spandrel)
                fs1 = rot_pt(hx, -hy, z_spandrel)
                fs2 = rot_pt(hx, hy, z_spandrel)
                fs3 = rot_pt(-hx, hy, z_spandrel)

                # Top corners for this floor level
                ft0 = rot_pt(-hx, -hy, z_top)
                ft1 = rot_pt(hx, -hy, z_top)
                ft2 = rot_pt(hx, hy, z_top)
                ft3 = rot_pt(-hx, hy, z_top)

                # Spandrel bands (Facade solid color)
                add_quad(fb0, fb1, fs1, fs0, f_col)  # Front
                add_quad(fb1, fb2, fs2, fs1, f_col)  # Right
                add_quad(fb2, fb3, fs3, fs2, f_col)  # Back
                add_quad(fb3, fb0, fs0, fs3, f_col)  # Left

                # Window glass bands (Curtain wall glass tint)
                add_quad(fs0, fs1, ft1, ft0, w_col)  # Front
                add_quad(fs1, fs2, ft2, ft1, w_col)  # Right
                add_quad(fs2, fs3, ft3, ft2, w_col)  # Back
                add_quad(fs3, fs0, ft0, ft3, w_col)  # Left
        else:
            # Single solid wall volume
            b0 = rot_pt(-hx, -hy, 0.0)
            b1 = rot_pt(hx, -hy, 0.0)
            b2 = rot_pt(hx, hy, 0.0)
            b3 = rot_pt(-hx, hy, 0.0)

            t0 = rot_pt(-hx, -hy, wz)
            t1 = rot_pt(hx, -hy, wz)
            t2 = rot_pt(hx, hy, wz)
            t3 = rot_pt(-hx, hy, wz)

            add_quad(b0, b1, t1, t0, f_col)
            add_quad(b1, b2, t2, t1, f_col)
            add_quad(b2, b3, t3, t2, f_col)
            add_quad(b3, b0, t0, t3, f_col)

        # 4 Eaves / Top wall corners for roof attachment
        t0 = rot_pt(-hx, -hy, wz)
        t1 = rot_pt(hx, -hy, wz)
        t2 = rot_pt(hx, hy, wz)
        t3 = rot_pt(-hx, hy, wz)

        # Roof Geometry Styles
        if roof_type in ("pitched", "gable"):
            ridge_h = wz + wz * 0.25
            r_left = rot_pt(-hx, 0.0, ridge_h)
            r_right = rot_pt(hx, 0.0, ridge_h)
            add_quad(t0, t1, r_right, r_left, r_col)
            add_quad(t2, t3, r_left, r_right, r_col)
            add_tri(t3, t0, r_left, f_col)
            add_tri(t1, t2, r_right, f_col)
        elif roof_type == "hipped":
            peak_h = wz + wz * 0.22
            peak = rot_pt(0.0, 0.0, peak_h)
            add_tri(t0, t1, peak, r_col)
            add_tri(t1, t2, peak, r_col)
            add_tri(t2, t3, peak, r_col)
            add_tri(t3, t0, peak, r_col)
        elif roof_type in ("mansard", "curved"):
            m_h = wz + wz * 0.18
            mhx, mhy = hx * 0.7, hy * 0.7
            m0 = rot_pt(-mhx, -mhy, m_h)
            m1 = rot_pt(mhx, -mhy, m_h)
            m2 = rot_pt(mhx, mhy, m_h)
            m3 = rot_pt(-mhx, mhy, m_h)
            add_quad(t0, t1, m1, m0, r_col)
            add_quad(t1, t2, m2, m1, r_col)
            add_quad(t2, t3, m3, m2, r_col)
            add_quad(t3, t0, m0, m3, r_col)
            add_quad(m0, m3, m2, m1, r_col)
        elif roof_type == "shed":
            s_h = wz + wz * 0.20
            s2 = rot_pt(hx, hy, s_h)
            s3 = rot_pt(-hx, hy, s_h)
            add_quad(t0, t1, s2, s3, r_col)
            add_tri(t1, t2, s2, f_col)
            add_tri(t3, t0, s3, f_col)
        else:
            # Standard flat roof cap
            add_quad(t0, t3, t2, t1, r_col)

            # Roof Parapet Lip (0.6m high perimeter edge)
            p_h = wz + 0.6
            p0 = rot_pt(-hx, -hy, p_h)
            p1 = rot_pt(hx, -hy, p_h)
            p2 = rot_pt(hx, hy, p_h)
            p3 = rot_pt(-hx, hy, p_h)
            trim_col = [min(255, c + 15) for c in r_col]
            add_quad(t0, t1, p1, p0, trim_col)
            add_quad(t1, t2, p2, p1, trim_col)
            add_quad(t2, t3, p3, p2, trim_col)
            add_quad(t3, t0, p0, p3, trim_col)

        # Rooftop Mechanical Penthouse / HVAC Unit
        if any("penthouse" in f or "hvac" in f or "mechanical" in f for f in features) or wz >= 18.0:
            pw, pd, ph = wx * 0.35, wy * 0.35, 2.5
            phx, phy = pw / 2.0, pd / 2.0
            pent_base_z = wz + 0.05
            pent_top_z = pent_base_z + ph
            p_col = [max(0, c - 15) for c in r_col]

            pb0 = rot_pt(-phx, -phy, pent_base_z)
            pb1 = rot_pt(phx, -phy, pent_base_z)
            pb2 = rot_pt(phx, phy, pent_base_z)
            pb3 = rot_pt(-phx, phy, pent_base_z)

            pt0 = rot_pt(-phx, -phy, pent_top_z)
            pt1 = rot_pt(phx, -phy, pent_top_z)
            pt2 = rot_pt(phx, phy, pent_top_z)
            pt3 = rot_pt(-phx, phy, pent_top_z)

            add_quad(pb0, pb1, pt1, pt0, p_col)
            add_quad(pb1, pb2, pt2, pt1, p_col)
            add_quad(pb2, pb3, pt3, pt2, p_col)
            add_quad(pb3, pb0, pt0, pt3, p_col)
            add_quad(pt0, pt3, pt2, pt1, p_col)

    # 4. Vegetation / Trees with Foliage Crowns and Trunks
    for veg in scene_data.get("vegetation", []):
        vx, vy = veg.get("center", [0, 0])
        rad = float(veg.get("radius", 4.5))
        vh = float(veg.get("height", 6.5))
        v_col = veg.get("color_rgb", [42, 98, 38])
        v_col_top = [min(255, c + 20) for c in v_col]
        trunk_col = [88, 62, 42]

        # Trunk (4-sided rectangular pillar)
        tw = rad * 0.2
        tb = vh * 0.38
        add_quad([vx - tw, vy - tw, 0], [vx + tw, vy - tw, 0], [vx + tw, vy - tw, tb], [vx - tw, vy - tw, tb], trunk_col)
        add_quad([vx + tw, vy - tw, 0], [vx + tw, vy + tw, 0], [vx + tw, vy + tw, tb], [vx + tw, vy - tw, tb], trunk_col)
        add_quad([vx + tw, vy + tw, 0], [vx - tw, vy + tw, 0], [vx - tw, vy + tw, tb], [vx + tw, vy + tw, tb], trunk_col)
        add_quad([vx - tw, vy + tw, 0], [vx - tw, vy - tw, 0], [vx - tw, vy - tw, tb], [vx - tw, vy + tw, tb], trunk_col)

        # Conical Foliage Crown (8 radial sectors)
        segments = 8
        crown_top = [vx, vy, vh]
        for s in range(segments):
            a1 = 2.0 * math.pi * s / segments
            a2 = 2.0 * math.pi * (s + 1) / segments
            p_a1 = [vx + math.cos(a1) * rad, vy + math.sin(a1) * rad, tb]
            p_a2 = [vx + math.cos(a2) * rad, vy + math.sin(a2) * rad, tb]
            add_tri(p_a1, p_a2, crown_top, v_col_top)
            # Bottom crown closure
            add_tri([vx, vy, tb], p_a2, p_a1, v_col)

    return (
        np.array(vertices, dtype=np.float32),
        np.array(faces, dtype=np.uint32),
        np.array(colors, dtype=np.uint8),
    )


def export_binary_glb(vertices: np.ndarray, faces: np.ndarray, colors: np.ndarray, out_path: Path):
    """Exports 3D mesh into standard compliant binary glTF 2.0 (.glb) with vertex colors and surface normals."""
    v_f32 = vertices.astype(np.float32)
    f_u32 = faces.astype(np.uint32)
    n_f32 = compute_normals(v_f32, f_u32)

    if colors is not None and len(colors) == len(vertices):
        if colors.shape[1] == 3:
            c_u8 = np.hstack([colors[:, :3].astype(np.uint8), np.full((len(colors), 1), 255, dtype=np.uint8)])
        else:
            c_u8 = colors.astype(np.uint8)
    else:
        c_u8 = np.full((len(vertices), 4), 210, dtype=np.uint8)

    v_bytes = v_f32.tobytes()
    n_bytes = n_f32.tobytes()
    f_bytes = f_u32.tobytes()
    c_bytes = c_u8.tobytes()

    def pad(b):
        r = len(b) % 4
        return b + (b"\x00" * (4 - r) if r else b"")

    v_pad = pad(v_bytes)
    n_pad = pad(n_bytes)
    f_pad = pad(f_bytes)
    c_pad = pad(c_bytes)

    bin_data = v_pad + n_pad + f_pad + c_pad

    v_offset = 0
    n_offset = len(v_pad)
    f_offset = len(v_pad) + len(n_pad)
    c_offset = len(v_pad) + len(n_pad) + len(f_pad)

    min_v = v_f32.min(axis=0).tolist() if len(v_f32) > 0 else [0, 0, 0]
    max_v = v_f32.max(axis=0).tolist() if len(v_f32) > 0 else [1, 1, 1]
    min_n = n_f32.min(axis=0).tolist() if len(n_f32) > 0 else [-1, -1, -1]
    max_n = n_f32.max(axis=0).tolist() if len(n_f32) > 0 else [1, 1, 1]

    gltf = {
        "asset": {"version": "2.0", "generator": "SpatialTwin-OpenRouter-AI-3D/1.1"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0, "name": "AIReconstructedSpatialTwin"}],
        "meshes": [{
            "name": "OpenRouterGeneratedSurface",
            "primitives": [{
                "attributes": {
                    "POSITION": 0,
                    "NORMAL": 1,
                    "COLOR_0": 3,
                },
                "indices": 2,
                "mode": 4,
            }],
        }],
        "accessors": [
            {
                "bufferView": 0,
                "byteOffset": 0,
                "componentType": 5126,
                "count": len(v_f32),
                "type": "VEC3",
                "min": min_v,
                "max": max_v,
            },
            {
                "bufferView": 1,
                "byteOffset": 0,
                "componentType": 5126,
                "count": len(n_f32),
                "type": "VEC3",
                "min": min_n,
                "max": max_n,
            },
            {
                "bufferView": 2,
                "byteOffset": 0,
                "componentType": 5125,
                "count": len(f_u32) * 3,
                "type": "SCALAR",
            },
            {
                "bufferView": 3,
                "byteOffset": 0,
                "componentType": 5121,
                "count": len(c_u8),
                "type": "VEC4",
                "normalized": True,
            },
        ],
        "bufferViews": [
            {"buffer": 0, "byteOffset": v_offset, "byteLength": len(v_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": n_offset, "byteLength": len(n_bytes), "target": 34962},
            {"buffer": 0, "byteOffset": f_offset, "byteLength": len(f_bytes), "target": 34963},
            {"buffer": 0, "byteOffset": c_offset, "byteLength": len(c_bytes), "target": 34962},
        ],
        "buffers": [{"byteLength": len(bin_data)}],
    }

    json_bytes = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(json_bytes) % 4 != 0:
        json_bytes += b" "

    total_len = 12 + 8 + len(json_bytes) + 8 + len(bin_data)
    header = struct.pack("<4sII", b"glTF", 2, total_len)
    json_chunk = struct.pack("<II", len(json_bytes), 0x4E4F534A) + json_bytes
    bin_chunk = struct.pack("<II", len(bin_data), 0x004E4942) + bin_data

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(header + json_chunk + bin_chunk)


def export_wavefront_obj(vertices: np.ndarray, faces: np.ndarray, colors: np.ndarray, out_path: Path):
    """Exports 3D mesh into Wavefront OBJ format with vertex colors and normals."""
    v_f32 = vertices.astype(np.float32)
    f_u32 = faces.astype(np.uint32)
    n_f32 = compute_normals(v_f32, f_u32)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# OpenRouter AI 3D Model Export (Spatial Twin)\n")
        for i, v in enumerate(v_f32):
            if colors is not None and i < len(colors):
                c = colors[i]
                f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f} {c[0]/255:.3f} {c[1]/255:.3f} {c[2]/255:.3f}\n")
            else:
                f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")
        for n in n_f32:
            f.write(f"vn {n[0]:.4f} {n[1]:.4f} {n[2]:.4f}\n")
        for face in f_u32:
            i0, i1, i2 = face[0] + 1, face[1] + 1, face[2] + 1
            f.write(f"f {i0}//{i0} {i1}//{i1} {i2}//{i2}\n")

