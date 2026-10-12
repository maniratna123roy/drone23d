"""
Spatial Twin: Master Offline ML Pipeline Orchestrator (pipeline/run_pipeline.py)

Beginner Analogy:
The master factory conveyor belt:
With one single command, it guides the raw drone point cloud through every station:
semantic coloring, ground leveling, building extraction, database filing, and web packaging.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import os
import time
import asyncio
import importlib

generate_mill_scene = importlib.import_module("pipeline.01b_generate_mock_mill").generate_mill_scene
run_segmentation = importlib.import_module("pipeline.03_segment").run_segmentation
label_splats_from_masks = importlib.import_module("pipeline.04_label_splats").label_splats_from_masks
fit_ground_and_align = importlib.import_module("pipeline.05a_fit_ground_frame").fit_ground_and_align
extract_geometries = importlib.import_module("pipeline.05b_extract_geometry").extract_geometries
load_structures_to_db = importlib.import_module("pipeline.06_load_db").load_structures_to_db
export_web_splat = importlib.import_module("pipeline.07_export_splat").export_web_splat

async def run_entire_pipeline():
    start_time = time.time()
    print("=" * 70)
    print("SPATIAL TWIN: FULL OFFLINE ML & GEOMETRY PIPELINE (PHASE 2)")
    print("=" * 70)
    
    # Check if point_cloud.ply exists, if not generate it
    ply_path = Path("./output/mill/point_cloud.ply")
    if not ply_path.exists():
        print("\n[STEP 1/6] Synthesizing initial Mill-19 scene point cloud...")
        generate_mill_scene()
    else:
        print(f"\n[STEP 1/6] Verified scene point cloud: {ply_path} ({os.path.getsize(ply_path):,} bytes)")
        
    # Step 2: Keyframe segmentation
    print("\n[STEP 2/6] Running Stage 03 SegFormer-B0 Keyframe Segmentation...")
    run_segmentation()
    
    # Step 3: Splat labeling
    print("\n[STEP 3/6] Running Stage 04 3D Splat Semantic Labeling...")
    label_splats_from_masks()
    
    # Step 4: Ground plane fitting and alignment
    print("\n[STEP 4/6] Running Stage 05a RANSAC Ground Fitting & Frame Alignment...")
    fit_ground_and_align()
    
    # Step 5: Building extraction
    print("\n[STEP 5/6] Running Stage 05b DBSCAN Clustering & Footprint Extraction...")
    num_buildings = extract_geometries()
    
    # Step 6: Database loading
    print("\n[STEP 6/6a] Running Stage 06 PostGIS Loader...")
    await load_structures_to_db()
    
    # Step 7: Web Splat export
    print("\n[STEP 6/6b] Running Stage 07 Binary Splat & Class Exporter...")
    export_web_splat()
    
    total_time = round(time.time() - start_time, 2)
    print("\n" + "=" * 70)
    print(f"[SUCCESS] PHASE 2 OFFLINE PIPELINE COMPLETE ({total_time}s)")
    print(f"   * Extracted Structures : {num_buildings} buildings")
    print(f"   * PostGIS Status       : Live & Populated with 3D SFCGAL solids")
    print(f"   * Web Splat File       : static/scene.splat")
    print(f"   * Semantic Class File  : static/scene.classes.u8")
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_entire_pipeline())
