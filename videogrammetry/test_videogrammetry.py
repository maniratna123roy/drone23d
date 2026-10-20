"""Test suite for Videogrammetry Sidecar.
Verifies:
1. Tier configurations
2. Storage manager directory layout
3. Stage 0 through 8 execution
4. Artifact generation (GLB, OBJ, LAZ, Orthomosaic, manifest.json)
5. Model serving endpoint (/v1/captures/{id}/model)
6. Model import endpoint (/v1/captures/{id}/import-model)
"""

import asyncio
import io
import shutil
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from videogrammetry.models import Capture, CreateCaptureRequest, StartCaptureRequest, QualityVerdict, CaptureStatus
from videogrammetry.tiers import TIERS, get_tier
from videogrammetry.storage import StorageManager
from videogrammetry.orchestrator import PipelineOrchestrator
from videogrammetry.api import sidecar_app, captures_db, storage_mgr

client = TestClient(sidecar_app)

def test_tier_definitions():
    assert "lite" in TIERS
    assert "standard" in TIERS
    assert "premium" in TIERS
    assert "premium_advanced" in TIERS
    lite = get_tier("lite")
    assert lite.frame_budget == 200
    assert lite.dynamic_masks is False
    prem = get_tier("premium")
    assert prem.frame_budget == 700
    assert prem.dynamic_masks is True

def test_storage_manager(tmp_path):
    storage = StorageManager(tmp_path)
    subdirs = storage.get_subdirs("cap_test_123")
    assert subdirs["raw"].exists()
    assert subdirs["frames"].exists()
    assert subdirs["work"].exists()
    assert subdirs["out"].exists()

@pytest.mark.asyncio
async def test_orchestrator_pipeline_run(tmp_path):
    import cv2
    import numpy as np

    storage = StorageManager(tmp_path)
    orchestrator = PipelineOrchestrator(storage, base_url="/api/videogrammetry/artifacts")

    capture = Capture(id="cap_unit_test", tier="standard", crs="EPSG:4326")
    orchestrator.initialize_capture_stages(capture)

    # Create dummy video
    raw_dir = storage.get_raw_dir("cap_unit_test")
    test_video = raw_dir / "drone_flight.mp4"
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    out_vid = cv2.VideoWriter(str(test_video), fourcc, 20.0, (640, 480))
    for i in range(30):
        img = np.zeros((480, 640, 3), dtype=np.uint8)
        img[:] = (50 + i * 2, 70, 80)
        cv2.putText(img, f"Frame {i}", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        out_vid.write(img)
    out_vid.release()

    # Run orchestrator
    await orchestrator.run(capture, test_video)

    assert capture.status in ("completed", "degraded")
    assert capture.progress == 100.0
    assert capture.quality_report is not None
    assert capture.quality_report.verdict in (QualityVerdict.PASS, QualityVerdict.DEGRADED)

    # Check generated artifacts
    out_dir = storage.get_out_dir("cap_unit_test")
    work_dir = storage.get_work_dir("cap_unit_test")
    assert (work_dir / "sparse_points.ply").exists()
    assert (work_dir / "dense_point_cloud.ply").exists()
    assert (out_dir / "scene.glb").exists()
    assert (out_dir / "mesh.obj").exists()
    assert (out_dir / "mesh.mtl").exists()
    assert (out_dir / "orthomosaic.png").exists()
    assert (out_dir / "point_cloud.laz").exists()
    assert (out_dir / "manifest.json").exists()
    assert len(capture.artifacts) >= 6

    # Verify no hardcoded mock building labels exist in the generated mesh
    with open(out_dir / "mesh.obj", "r", encoding="utf-8") as f:
        obj_content = f.read()
    assert "Mill-19 North Wing" not in obj_content
    assert "Control Tower & Offices" not in obj_content
    assert "Logistics Depot" not in obj_content

    # Verify scene.glb is a valid glTF 2.0 binary
    with open(out_dir / "scene.glb", "rb") as f:
        glb_magic = f.read(4)
    assert glb_magic == b"glTF"

def test_api_model_serving_and_import():
    cid = "cap_api_test"
    shutil.rmtree(storage_mgr.get_capture_dir(cid), ignore_errors=True)
    captures_db[cid] = Capture(id=cid, tier="standard", status=CaptureStatus.CREATED)

    # 1. Initially 404 before model exists
    res_404 = client.get(f"/v1/captures/{cid}/model")
    assert res_404.status_code == 404

    # 2. Import a model (.glb)
    dummy_glb = b"glTF\x02\x00\x00\x00\x14\x00\x00\x00JSON{}"
    import_res = client.post(
        f"/v1/captures/{cid}/import-model",
        files={"file": ("scene.glb", io.BytesIO(dummy_glb), "model/gltf-binary")}
    )
    assert import_res.status_code == 200
    assert import_res.json()["status"] == "imported"

    # 3. Model serving now succeeds with 200 and proper MIME
    res_200 = client.get(f"/v1/captures/{cid}/model")
    assert res_200.status_code == 200
    assert res_200.headers["content-type"] == "model/gltf-binary"
    assert res_200.content == dummy_glb

    # 4. Import a point cloud (.ply) e.g. from Google Colab
    cid_ply = "cap_api_test_ply"
    shutil.rmtree(storage_mgr.get_capture_dir(cid_ply), ignore_errors=True)
    captures_db[cid_ply] = Capture(id=cid_ply, tier="standard", status=CaptureStatus.CREATED)
    dummy_ply = b"ply\nformat ascii 1.0\nelement vertex 1\nproperty float x\nend_header\n0 0 0\n"
    import_ply = client.post(
        f"/v1/captures/{cid_ply}/import-model",
        files={"file": ("point_cloud.ply", io.BytesIO(dummy_ply), "application/octet-stream")}
    )
    assert import_ply.status_code == 200
    assert import_ply.json()["status"] == "imported"
    assert import_ply.json()["kind"] == "ply"

    # Verify serving point cloud when glb is not yet present
    res_ply = client.get(f"/v1/captures/{cid_ply}/model")
    assert res_ply.status_code == 200
    assert res_ply.headers["content-type"] == "application/octet-stream"
    assert res_ply.content == dummy_ply

def test_stage7_quality_gate_logic(tmp_path):
    import json
    from videogrammetry.stages.stage7_quality_gate import Stage7QualityGate

    work_dir = tmp_path / "work"
    out_dir = tmp_path / "out"
    work_dir.mkdir(parents=True)
    out_dir.mkdir(parents=True)

    # 1. Good metrics -> PASS
    with open(work_dir / "sfm_report.json", "w") as f:
        json.dump({"registration_ratio": 0.95, "mean_reprojection_error_px": 0.65, "sparse_points_count": 2500}, f)
    with open(work_dir / "dense_report.json", "w") as f:
        json.dump({"dense_points_count": 210000, "average_point_spacing_cm": 2.2}, f)
    with open(work_dir / "mesh_report.json", "w") as f:
        json.dump({"triangle_count": 45000, "hole_area_ratio": 0.005}, f)

    gate = Stage7QualityGate(work_dir)
    rep_pass = gate.evaluate("job_1", attempt=1, max_retries=2)
    assert rep_pass.verdict == QualityVerdict.PASS
    assert rep_pass.metrics.registered_frames_ratio == 0.95
    assert rep_pass.metrics.mean_reprojection_error_px == 0.65
    assert rep_pass.metrics.sparse_points_count == 2500
    assert rep_pass.metrics.dense_points_count == 210000

    # 2. High reprojection error -> RETRY with Ladder Step 1
    with open(work_dir / "sfm_report.json", "w") as f:
        json.dump({"registration_ratio": 0.95, "mean_reprojection_error_px": 2.4, "sparse_points_count": 2500}, f)

    rep_retry = gate.evaluate("job_1", attempt=1, max_retries=2)
    assert rep_retry.verdict == QualityVerdict.RETRY
    assert "Ladder Step 1" in rep_retry.retry_strategy

    # 3. Exhausted attempts -> DEGRADED
    rep_deg = gate.evaluate("job_1", attempt=3, max_retries=2)
    assert rep_deg.verdict == QualityVerdict.DEGRADED
    assert "DEGRADED" in rep_deg.retry_strategy

def test_colab_bridge_endpoints():
    # 1. Status when disconnected
    res = client.get("/v1/colab/status")
    assert res.status_code == 200
    assert "connected" in res.json()

    # 2. Connect validation error on empty url
    res_err = client.post("/v1/colab/connect", json={"worker_url": ""})
    assert res_err.status_code == 400

    # 3. Disconnect endpoint
    res_disc = client.post("/v1/colab/disconnect")
    assert res_disc.status_code == 200
    assert res_disc.json()["status"] == "disconnected"

