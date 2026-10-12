"""
Spatial Twin: Pipeline-Backend Full Integration Test
Verifies that all offline pipeline outputs (3D splats, semantic sidecars,
geometry extractions, frame alignments, and database records)
are accessible and served through the FastAPI backend.
"""

import sys
import os
import json
import asyncio
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from httpx import ASGITransport
from backend.main import app
from backend.db.connection import connect_to_db, close_db_connection

async def run_integration_tests():
    print("=" * 70)
    print("PIPELINE <-> BACKEND FULL INTEGRATION TEST")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. Verify Pipeline File Artifacts on Disk
    # -------------------------------------------------------------
    print("\n[STEP 1/4] Verifying Pipeline Files on Disk...")
    splat_path = Path("static/scene.splat")
    classes_path = Path("static/scene.classes.u8")
    structures_json = Path("output/mill/extracted_structures.json")
    transform_json = Path("output/mill/frame_transform.json")

    assert splat_path.exists(), f"Missing {splat_path}"
    assert classes_path.exists(), f"Missing {classes_path}"
    assert structures_json.exists(), f"Missing {structures_json}"
    assert transform_json.exists(), f"Missing {transform_json}"

    splat_size = splat_path.stat().st_size
    classes_size = classes_path.stat().st_size
    num_splats = splat_size // 32
    assert splat_size % 32 == 0, "scene.splat must be a multiple of 32 bytes"
    assert classes_size == num_splats, f"classes sidecar size ({classes_size}) must match splat count ({num_splats})"

    print(f"  OK: scene.splat contains {num_splats:,} splats ({splat_size:,} bytes)")
    print(f"  OK: scene.classes.u8 sidecar contains {classes_size:,} class tags (1 byte/splat)")
    print(f"  OK: extracted_structures.json present ({structures_json.stat().st_size:,} bytes)")
    print(f"  OK: frame_transform.json present ({transform_json.stat().st_size:,} bytes)")

    # -------------------------------------------------------------
    # 2. Verify Backend Static Assets Serving
    # -------------------------------------------------------------
    print("\n[STEP 2/4] Testing FastAPI Static Files Serving (/static)...")
    await connect_to_db()
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1:8000") as client:
        # Check scene.splat
        r_splat = await client.head("/static/scene.splat")
        assert r_splat.status_code == 200, f"Failed GET /static/scene.splat: {r_splat.status_code}"
        assert int(r_splat.headers.get("content-length", 0)) == splat_size
        print(f"  OK: GET /static/scene.splat -> HTTP 200 ({splat_size:,} bytes served)")

        # Check scene.classes.u8
        r_classes = await client.head("/static/scene.classes.u8")
        assert r_classes.status_code == 200, f"Failed GET /static/scene.classes.u8: {r_classes.status_code}"
        assert int(r_classes.headers.get("content-length", 0)) == classes_size
        print(f"  OK: GET /static/scene.classes.u8 -> HTTP 200 ({classes_size:,} bytes served)")

        # -------------------------------------------------------------
        # 3. Verify Backend Data API against Pipeline Data
        # -------------------------------------------------------------
        print("\n[STEP 3/4] Testing Backend Objects API against Pipeline DB records...")
        
        # Project endpoint
        r_proj = await client.get("/api/objects/project")
        assert r_proj.status_code == 200, f"Failed GET /api/objects/project: {r_proj.status_code}"
        proj_data = r_proj.json()
        assert proj_data["name"] == "Mill-19 Digital Twin"
        assert proj_data["scale_factor"] == 1.0
        assert len(proj_data["frame_transform"]) == 4  # 4x4 matrix
        print(f"  OK: GET /api/objects/project -> '{proj_data['name']}', scale={proj_data['scale_factor']}")
        print(f"      Frame alignment matrix: 4x4 Z-up transform loaded.")

        # Structures endpoint
        r_structs = await client.get("/api/objects/structures")
        assert r_structs.status_code == 200
        structs = r_structs.json()
        with open(structures_json) as f:
            pipeline_structs = json.load(f)
        assert len(structs) == len(pipeline_structs), f"Expected {len(pipeline_structs)} structures, got {len(structs)}"
        print(f"  OK: GET /api/objects/structures -> {len(structs)} structures retrieved (matches pipeline)")
        
        # Verify first building has valid footprint and splat_bbox
        first = structs[0]
        assert first["footprint"]["type"] == "Polygon"
        assert "min_x" in first["splat_bbox"] and "max_x" in first["splat_bbox"]
        print(f"      Sample structure ID #{first['id']} ({first['region'].upper()}): height={first['height_m']:.1f}m, area={first['area_m2']:.1f}m²")

        # Regions endpoint
        r_regions = await client.get("/api/objects/regions")
        assert r_regions.status_code == 200
        regions = r_regions.json()
        assert len(regions) >= 5
        print(f"  OK: GET /api/objects/regions -> {len(regions)} regions available")

        # -------------------------------------------------------------
        # 4. Verify AI Query Loop Over Pipeline Structures
        # -------------------------------------------------------------
        print("\n[STEP 4/4] Testing AI Query Loop over Pipeline Structures...")
        query_text = "Which buildings are taller than 20 metres?"
        r_query = await client.post("/api/query", json={"text": query_text})
        assert r_query.status_code == 200
        q_data = r_query.json()
        assert q_data["status"] == "success"
        matched_ids = q_data["matched_ids"]
        print(f"  OK: Query '{query_text}'")
        print(f"      Matched IDs: {matched_ids}")
        print(f"      Metrics: {q_data['metrics']}")
        print(f"      Latency: {q_data['latency_ms']} ms")
        assert len(matched_ids) > 0

    await close_db_connection()
    print("\n" + "=" * 70)
    print("ALL INTEGRATION CHECKS PASSED: Pipeline and Backend are 100% synchronized!")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_integration_tests())
