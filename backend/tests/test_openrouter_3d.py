"""Unit tests for OpenRouter AI 3D Reconstruction Service."""

import pytest
import struct
from pathlib import Path
from fastapi.testclient import TestClient
import numpy as np

from backend.main import app
from backend.openrouter_3d_engine import (
    synthesize_3d_geometry,
    export_binary_glb,
    export_wavefront_obj,
)

client = TestClient(app)


def test_openrouter_config_endpoint():
    """Verifies config endpoint returns status, masked key, and supported models."""
    res = client.get("/api/openrouter-3d/config")
    assert res.status_code == 200
    data = res.json()
    assert "has_api_key" in data
    assert "masked_key" in data
    assert "supported_models" in data
    assert len(data["supported_models"]) >= 3


def test_geometry_synthesis_and_roof_types():
    """Verifies 3D geometry generator accurately processes buildings and roof types."""
    scene_data = {
        "scene_title": "Test Industrial Twin",
        "terrain": {"size_x": 100.0, "size_y": 100.0, "color_rgb": [80, 110, 70]},
        "roads": [{"start": [-40, 0], "end": [40, 0], "width": 8.0, "color_rgb": [50, 50, 50]}],
        "buildings": [
            {
                "name": "Flat Roof Warehouse",
                "center": [-20, 20, 0],
                "dimensions": [20, 15, 12],
                "rotation_deg": 0,
                "roof_type": "flat",
            },
            {
                "name": "Pitched Roof Hall",
                "center": [20, 20, 0],
                "dimensions": [25, 18, 14],
                "rotation_deg": 15,
                "roof_type": "pitched",
            },
            {
                "name": "Hipped Roof Pavilion",
                "center": [0, -25, 0],
                "dimensions": [16, 16, 10],
                "rotation_deg": 45,
                "roof_type": "hipped",
            },
        ],
        "vegetation": [
            {"center": [-35, -20], "radius": 4.0, "height": 6.0, "color_rgb": [40, 90, 35]}
        ],
    }

    vertices, faces, colors = synthesize_3d_geometry(scene_data)
    assert len(vertices) > 50
    assert len(faces) > 25
    assert len(colors) == len(vertices)
    assert colors.shape[1] == 4  # RGBA


def test_binary_glb_and_obj_export(tmp_path: Path):
    """Verifies binary glTF 2.0 and Wavefront OBJ serialization."""
    v = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0], [0, 0, 1]], dtype=np.float32)
    f = np.array([[0, 1, 2], [0, 2, 3], [0, 1, 4]], dtype=np.uint32)
    c = np.full((len(v), 4), 220, dtype=np.uint8)

    glb_file = tmp_path / "test.glb"
    obj_file = tmp_path / "test.obj"

    export_binary_glb(v, f, c, glb_file)
    export_wavefront_obj(v, f, c, obj_file)

    assert glb_file.exists()
    assert obj_file.exists()

    # Validate GLB binary header
    glb_bytes = glb_file.read_bytes()
    magic, version, length = struct.unpack("<4sII", glb_bytes[:12])
    assert magic == b"glTF"
    assert version == 2
    assert length == len(glb_bytes)

    # Validate OBJ structure
    obj_lines = obj_file.read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("v ") for line in obj_lines)
    assert any(line.startswith("f ") for line in obj_lines)


def test_openrouter_generate_sample_endpoint():
    """Verifies end-to-end 3D model generation in sample mode."""
    res = client.post(
        "/api/openrouter-3d/generate",
        data={"sample_mode": "true", "model": "nvidia/nemotron-3.5-super-vl:free"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "capture_id" in data
    assert "artifacts" in data
    assert "glb_url" in data["artifacts"]
    assert "obj_url" in data["artifacts"]

    cid = data["capture_id"]

    # Verify downloading the generated GLB
    glb_res = client.get(f"/api/openrouter-3d/model/{cid}/glb")
    assert glb_res.status_code == 200
    assert glb_res.headers["content-type"] == "model/gltf-binary"
    assert len(glb_res.content) > 1000

    # Verify downloading the generated OBJ
    obj_res = client.get(f"/api/openrouter-3d/model/{cid}/obj")
    assert obj_res.status_code == 200
    assert "text/plain" in obj_res.headers["content-type"]


def test_openrouter_generate_with_prompt_directive():
    """Verifies that user architectural prompt directive is accepted and recorded in the report."""
    test_prompt = "Exact replica of dual industrial warehouses with central 42m communications tower"
    res = client.post(
        "/api/openrouter-3d/generate",
        data={
            "sample_mode": "true",
            "prompt": test_prompt,
            "model": "nvidia/nemotron-3.5-super-vl:free",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("prompt_used") == test_prompt
    assert "scene_data" in data
    assert "mesh_stats" in data
    assert data["mesh_stats"]["vertex_count"] > 0
    assert data["mesh_stats"]["face_count"] > 0

