"""
Spatial Twin: Scene Structure Extraction & PostGIS Alignment (pipeline/extract_scene_structures.py)

Beginner Analogy:
Using a laser level to find the true street level, rotating the tilted drone model upright so
up points straight into the sky (+Z) and ground rests at 0 metres, scaling to real-world building
dimensions, and stamping extruded 3D building solids into the PostGIS city database so the AI agent
can instantly inspect, measure, query, and edit them in plain English.
"""

from __future__ import annotations

import asyncio
import json
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from scipy.spatial.transform import Rotation
from sklearn.cluster import DBSCAN
from sklearn.neighbors import NearestNeighbors
from shapely.geometry import MultiPoint, Polygon, mapping

from backend.config import settings
from pipeline.scene_publication import (
    SPLAT_DTYPE,
    atomic_json,
    read_json,
    sha256_file,
    validate_job_id,
)
from pipeline.common.frame import compute_ground_transform, apply_transform
import importlib
load_db_module = importlib.import_module("pipeline.06_load_db")
load_structures_to_db = load_db_module.load_structures_to_db


def determine_region(cx: float, cy: float) -> str:
    """Classifies a building into one of the 5 canonical project sectors."""
    if abs(cx) <= 25.0 and abs(cy) <= 25.0:
        return "center"
    elif cy > 25.0:
        return "north"
    elif cy < -25.0:
        return "south"
    elif cx > 25.0:
        return "east"
    elif cx < -25.0:
        return "west"
    return "center"


def extract_structures_from_splat(
    splat_path: Path,
    detected_classes_path: Optional[Path] = None,
    manifest: Optional[Dict[str, Any]] = None,
    eps: float = 4.0,
    min_samples: int = 25,
) -> Tuple[List[Dict[str, Any]], Optional[np.ndarray], float]:
    """
    Reads splat positions, aligns ground plane if uncalibrated, scales to realistic metres,
    clusters building entities with DBSCAN, and returns (structures, transform_matrix, scale_factor).
    """
    splat_path = Path(splat_path).resolve()
    if not splat_path.is_file():
        raise FileNotFoundError(f"Splat file not found: {splat_path}")

    data = np.fromfile(splat_path, dtype=SPLAT_DTYPE)
    positions = data["xyz"]
    count = len(positions)
    print(f"[EXTRACT] Loaded {count} Gaussians from {splat_path.name}")

    if count < 10:
        print(f"[EXTRACT] Very small point cloud ({count} Gaussians); skipping building extraction")
        return [], [], [], [], None, 1.0

    # Check for detected classes
    has_detected = False
    detected = None
    if detected_classes_path and Path(detected_classes_path).is_file():
        if Path(detected_classes_path).stat().st_size == count:
            detected = np.fromfile(detected_classes_path, dtype=np.uint8)
            has_detected = True

    needs_alignment = False
    T: Optional[np.ndarray] = None
    scale_factor = 1.0

    if manifest is not None:
        coord_frame = manifest.get("coordinate_frame", "")
        scale_status = manifest.get("scale_status", "")
        if coord_frame == "COLMAP_PHASE_A" or scale_status == "RELATIVE_UNCALIBRATED":
            needs_alignment = True

    if needs_alignment:
        print("[EXTRACT] Scene is uncalibrated / COLMAP Phase A frame. Fitting ground plane and aligning upright...")
        cam_up = np.array(manifest.get("camera", {}).get("up", [0.0, -1.0, 0.0]), dtype=np.float32)
        norm_cam_up = float(np.linalg.norm(cam_up))
        if norm_cam_up > 1e-6:
            cam_up = cam_up / norm_cam_up
        else:
            cam_up = np.array([0.0, -1.0, 0.0], dtype=np.float32)

        # Select ground points (road=2, terrain=1)
        if has_detected and np.sum((detected == 1) | (detected == 2)) >= 50:
            ground_mask = (detected == 1) | (detected == 2)
            print(f"[EXTRACT] Using {np.sum(ground_mask)} classified road/terrain points for ground leveling")
        else:
            # Estimate ground from lowest 20% along camera up direction
            proj_height = positions @ cam_up
            ground_mask = proj_height <= np.percentile(proj_height, 20)
            print(f"[EXTRACT] Using {np.sum(ground_mask)} lowest-elevation points along camera up vector")

        ground_pts = positions[ground_mask]
        plane_pt = np.median(ground_pts, axis=0)

        # Fit normal with SVD
        centroid = np.mean(ground_pts, axis=0)
        _, _, vh = np.linalg.svd(ground_pts - centroid)
        normal = vh[2]
        if np.dot(normal, cam_up) < 0:
            normal = -normal

        # Ensure normal is reasonably aligned with camera up; fallback to cam_up if degenerate
        if np.dot(normal, cam_up) < 0.3:
            normal = cam_up

        T = compute_ground_transform(normal, plane_pt)
        positions_aligned = apply_transform(positions, T)

        # Determine structure points and scale factor
        if has_detected and np.sum(detected == 0) >= 50:
            struct_mask = (detected == 0)
        else:
            struct_mask = positions_aligned[:, 2] >= 1.0

        struct_pts_aligned = positions_aligned[struct_mask]
        if len(struct_pts_aligned) >= 30:
            p98_z = float(np.percentile(struct_pts_aligned[:, 2], 98))
            base_z = float(max(0.0, np.percentile(struct_pts_aligned[:, 2], 5)))
            raw_h = p98_z - base_z
            if raw_h > 0.5:
                scale_factor = float(np.clip(30.0 / raw_h, 1.0, 15.0))
            else:
                scale_factor = 4.0
        else:
            scale_factor = 4.0

        print(f"[EXTRACT] Metric scale factor calibrated to {scale_factor:.2f}x (ground Z=0.0m)")
        positions = positions_aligned * scale_factor

        # Update splat positions and scales on disk so Three.js renders in aligned metric space
        data["xyz"] = positions.astype(np.float32)
        data["scales"] = (data["scales"] * scale_factor).astype(np.float32)

        # Rotate splat orientation quaternions to match new ground frame
        try:
            q_raw = (data["q"].astype(np.float32) - 128.0) / 128.0
            q_norm = np.linalg.norm(q_raw, axis=1, keepdims=True)
            q_norm[q_norm == 0] = 1.0
            q_raw = q_raw / q_norm
            q_xyzw = q_raw[:, [1, 2, 3, 0]]
            rot_orig = Rotation.from_quat(q_xyzw)
            rot_delta = Rotation.from_matrix(T[:3, :3])
            rot_new = rot_delta * rot_orig
            q_new_xyzw = rot_new.as_quat()
            q_new_wxyz = q_new_xyzw[:, [3, 0, 1, 2]]
            data["q"] = np.clip(np.round(q_new_wxyz * 128.0 + 128.0), 0, 255).astype(np.uint8)
        except Exception as q_err:
            print(f"[EXTRACT WARN] Quaternion rotation adjustment skipped: {q_err}")

        data.tofile(splat_path)
        print(f"[EXTRACT] Aligned and scaled {count} Gaussians saved to {splat_path.name}")
        ground_z = 0.0
    else:
        # Pre-aligned scene
        z_coords = positions[:, 2]
        ground_z = float(np.percentile(z_coords, 15))
        print(f"[EXTRACT] Pre-aligned scene ground elevation: {ground_z:.2f}m")

    # Select structure points
    if has_detected and np.sum(detected == 0) > 100:
        struct_mask = (detected == 0)
        print(f"[EXTRACT] Using {np.sum(struct_mask)} points with class=0 (structure)")
    else:
        # Altitude filter: points at least 2.0m above ground
        struct_mask = positions[:, 2] >= (ground_z + 2.0)
        print(f"[EXTRACT] Using {np.sum(struct_mask)} points elevated >= 2.0m above ground")

    struct_pts = positions[struct_mask]
    if len(struct_pts) < min_samples:
        print("[EXTRACT WARN] Very few structure points found; using top 50% elevation points")
        median_z = float(np.median(positions[:, 2]))
        struct_mask = positions[:, 2] >= median_z
        struct_pts = positions[struct_mask]

    if len(struct_pts) < 3:
        print("[EXTRACT WARN] Insufficient structure points for building footprints")
        return [], T, scale_factor

    # Cluster in 2D (X, Y) space using robust grid-accelerated DBSCAN
    xy = struct_pts[:, :2]
    if len(xy) > 1500:
        # Voxel downsample in 2D to 0.5m grid for zero-memory overhead and instant clustering
        grid_step = 0.5
        grid_keys = np.round(xy / grid_step) * grid_step
        _, sample_indices = np.unique(grid_keys, axis=0, return_index=True)
        xy_sub = xy[sample_indices]
        clustering = DBSCAN(eps=2.5, min_samples=10, n_jobs=1).fit(xy_sub)
        nn = NearestNeighbors(n_neighbors=1).fit(xy_sub)
        cluster_labels = clustering.labels_[nn.kneighbors(xy, return_distance=False).ravel()]
    else:
        eff_min_samples = min(min_samples, max(2, len(xy) // 10))
        clustering = DBSCAN(eps=2.5, min_samples=eff_min_samples, n_jobs=1).fit(xy)
        cluster_labels = clustering.labels_

    unique_clusters = sorted([c for c in set(cluster_labels) if c != -1])
    if len(unique_clusters) < 3 and len(xy) >= 3:
        # If structures form a single contiguous complex, use KMeans to partition into distinct towers/wings
        from sklearn.cluster import KMeans
        n_k = min(6, max(3, len(xy) // 400))
        n_k = min(n_k, len(xy))
        if n_k > 1:
            print(f"[EXTRACT] Partitioning contiguous structures into {n_k} distinct building entities via spatial clustering...")
            km = KMeans(n_clusters=n_k, random_state=42, n_init=10).fit(xy)
            cluster_labels = km.labels_
            unique_clusters = list(range(n_k))

    print(f"[EXTRACT] Identified {len(unique_clusters)} distinct building structures!")

    structures: List[Dict[str, Any]] = []

    for idx, c_id in enumerate(unique_clusters):
        c_mask = (cluster_labels == c_id)
        c_pts = struct_pts[c_mask]

        min_x, min_y, min_z = np.min(c_pts, axis=0)
        max_x, max_y, max_z = np.max(c_pts, axis=0)

        # 98th percentile height to protect against stray airborne points
        p98_z = float(np.percentile(c_pts[:, 2], 98))
        base_z = max(ground_z, float(min_z))
        height_m = max(3.0, round(p98_z - base_z, 1))

        cx = float((min_x + max_x) / 2.0)
        cy = float((min_y + max_y) / 2.0)
        region = determine_region(cx, cy)

        # 2D footprint convex hull
        c_xy = c_pts[:, :2]
        mp = MultiPoint(c_xy)
        hull = mp.convex_hull

        if isinstance(hull, Polygon):
            poly = hull.simplify(0.2, preserve_topology=True)
            area_m2 = max(10.0, round(float(poly.area), 1))
            footprint_geojson = mapping(poly)
        else:
            poly = hull.buffer(1.5)
            area_m2 = max(10.0, round(float(poly.area), 1))
            footprint_geojson = mapping(poly)

        width_m = round(float(max_x - min_x), 1)
        depth_m = round(float(max_y - min_y), 1)
        volume_m3 = round(area_m2 * height_m, 1)

        item = {
            "building_id": idx + 1,
            "id": idx + 1,
            "class": "structure",
            "label": f"Building #{idx + 1} ({region.upper()})",
            "region": region,
            "height_m": height_m,
            "original_height_m": height_m,
            "width_m": width_m,
            "depth_m": depth_m,
            "area_m2": area_m2,
            "volume_m3": volume_m3,
            "elevation_m": round(base_z, 2),
            "splat_count": int(np.sum(c_mask)),
            "splat_bbox": {
                "min_x": round(float(min_x), 2),
                "min_y": round(float(min_y), 2),
                "min_z": round(float(min_z), 2),
                "max_x": round(float(max_x), 2),
                "max_y": round(float(max_y), 2),
                "max_z": round(float(max_z), 2),
            },
            "footprint": footprint_geojson,
        }
        structures.append(item)

    # -------------------------------------------------------------
    # Layer 2: Road & Sidewalk Extraction & Attribute Measurement
    # -------------------------------------------------------------
    roads: List[Dict[str, Any]] = []
    if has_detected and np.sum(detected == 2) >= 10:
        road_pts = positions[detected == 2]
        r_min_x, r_min_y, r_min_z = np.min(road_pts, axis=0)
        r_max_x, r_max_y, r_max_z = np.max(road_pts, axis=0)

        r_mp = MultiPoint(road_pts[:, :2])
        r_hull = r_mp.convex_hull
        if isinstance(r_hull, Polygon):
            r_poly = r_hull.simplify(0.5, preserve_topology=True)
        else:
            r_poly = r_hull.buffer(2.0)
        r_area = max(10.0, round(float(r_poly.area), 1))

        r_dx = float(r_max_x - r_min_x)
        r_dy = float(r_max_y - r_min_y)
        r_length = round(float(np.hypot(r_dx, r_dy)), 1)
        r_width = round(float(r_area / max(1.0, r_length)), 1)

        roads.append({
            "id": 1,
            "class": "road",
            "label": "Road & Sidewalk Network",
            "length_m": r_length,
            "width_m": r_width,
            "area_m2": r_area,
            "elevation_m": round(float(np.median(road_pts[:, 2])), 2),
            "splat_count": int(len(road_pts)),
            "splat_bbox": {
                "min_x": round(float(r_min_x), 2),
                "min_y": round(float(r_min_y), 2),
                "min_z": round(float(r_min_z), 2),
                "max_x": round(float(r_max_x), 2),
                "max_y": round(float(r_max_y), 2),
                "max_z": round(float(r_max_z), 2),
            },
            "footprint": mapping(r_poly),
        })

    # -------------------------------------------------------------
    # Layer 3: Vegetation & Canopy Extraction & Attribute Measurement
    # -------------------------------------------------------------
    vegetation: List[Dict[str, Any]] = []
    if has_detected and np.sum(detected == 3) >= 10:
        v_pts = positions[detected == 3]
        v_min_x, v_min_y, v_min_z = np.min(v_pts, axis=0)
        v_max_x, v_max_y, v_max_z = np.max(v_pts, axis=0)

        v_mp = MultiPoint(v_pts[:, :2])
        v_hull = v_mp.convex_hull
        if isinstance(v_hull, Polygon):
            v_poly = v_hull.simplify(0.5, preserve_topology=True)
        else:
            v_poly = v_hull.buffer(1.5)
        v_area = max(5.0, round(float(v_poly.area), 1))

        v_height = round(float(np.percentile(v_pts[:, 2], 98) - ground_z), 1)
        v_width = round(float(v_max_x - v_min_x), 1)
        v_depth = round(float(v_max_y - v_min_y), 1)

        vegetation.append({
            "id": 1,
            "class": "vegetation",
            "label": "Canopy & Greenery Cluster",
            "canopy_height_m": max(1.0, v_height),
            "spread_width_m": v_width,
            "depth_m": v_depth,
            "area_m2": v_area,
            "elevation_m": round(float(min(ground_z, v_min_z)), 2),
            "splat_count": int(len(v_pts)),
            "splat_bbox": {
                "min_x": round(float(v_min_x), 2),
                "min_y": round(float(v_min_y), 2),
                "min_z": round(float(v_min_z), 2),
                "max_x": round(float(v_max_x), 2),
                "max_y": round(float(v_max_y), 2),
                "max_z": round(float(v_max_z), 2),
            },
            "footprint": mapping(v_poly),
        })

    # -------------------------------------------------------------
    # Layer 4: Terrain & Ground Surface Extraction
    # -------------------------------------------------------------
    terrain: List[Dict[str, Any]] = []
    if has_detected and np.sum(detected == 1) >= 5:
        t_pts = positions[detected == 1]
        t_min_x, t_min_y, t_min_z = np.min(t_pts, axis=0)
        t_max_x, t_max_y, t_max_z = np.max(t_pts, axis=0)

        t_mp = MultiPoint(t_pts[:, :2])
        t_hull = t_mp.convex_hull
        if isinstance(t_hull, Polygon):
            t_poly = t_hull.simplify(0.5, preserve_topology=True)
        else:
            t_poly = t_hull.buffer(1.0)
        t_area = max(5.0, round(float(t_poly.area), 1))

        terrain.append({
            "id": 1,
            "class": "terrain",
            "label": "Terrain & Ground Surface",
            "elevation_m": round(float(np.median(t_pts[:, 2])), 2),
            "area_m2": t_area,
            "splat_count": int(len(t_pts)),
            "splat_bbox": {
                "min_x": round(float(t_min_x), 2),
                "min_y": round(float(t_min_y), 2),
                "min_z": round(float(t_min_z), 2),
                "max_x": round(float(t_max_x), 2),
                "max_y": round(float(t_max_y), 2),
                "max_z": round(float(t_max_z), 2),
            },
            "footprint": mapping(t_poly),
        })

    return structures, roads, vegetation, terrain, T, scale_factor


async def extract_and_sync_scene_structures(job_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Main entry point:
    1. Reads active scene manifest
    2. Runs ground leveling, metric scaling, and multi-class attribute extraction (structures, roads, vegetation, terrain)
    3. Populates PostGIS database with 3D SFCGAL solids, roads, vegetation, and terrain
    4. Updates scene capabilities to {"queries": True, "edits": True}
    5. Updates manifests atomically with full classified attribute inventory
    """
    static_dir = Path(settings.STATIC_ASSETS_DIR).resolve()
    current_scene_path = static_dir / "current-scene.json"

    if not current_scene_path.is_file():
        raise FileNotFoundError("No active reconstructed scene found. Upload or reconstruct a video first.")

    manifest = read_json(current_scene_path)
    active_job_id = validate_job_id(job_id or manifest.get("job_id"))
    scene_dir = static_dir / "scenes" / active_job_id

    splat_path = scene_dir / "scene.splat"
    detected_classes = None
    if (scene_dir / "scene.classes.u8").is_file():
        detected_classes = scene_dir / "scene.classes.u8"
    elif (scene_dir / "scene.classes.detected.u8").is_file():
        detected_classes = scene_dir / "scene.classes.detected.u8"

    structures, roads, vegetation, terrain, T, scale_factor = extract_structures_from_splat(
        splat_path,
        detected_classes,
        manifest=manifest,
    )

    # Compile comprehensive classified attributes dictionary
    output_dir = Path("./output/mill")
    output_dir.mkdir(parents=True, exist_ok=True)

    classified_attributes = {
        "summary": {
            "structures_count": len(structures),
            "roads_count": len(roads),
            "vegetation_count": len(vegetation),
            "terrain_count": len(terrain),
            "structures_metrics": {
                "max_height_m": max([s["height_m"] for s in structures], default=0.0),
                "avg_height_m": round(float(np.mean([s["height_m"] for s in structures])), 1) if structures else 0.0,
                "total_footprint_m2": round(float(sum([s["area_m2"] for s in structures])), 1),
                "total_volume_m3": round(float(sum([s["volume_m3"] for s in structures])), 1),
            },
            "roads_metrics": {
                "corridor_length_m": sum([r["length_m"] for r in roads]),
                "avg_width_m": round(float(np.mean([r["width_m"] for r in roads])), 1) if roads else 0.0,
                "total_area_m2": round(float(sum([r["area_m2"] for r in roads])), 1),
            },
            "vegetation_metrics": {
                "max_canopy_height_m": max([v["canopy_height_m"] for v in vegetation], default=0.0),
                "total_area_m2": round(float(sum([v["area_m2"] for v in vegetation])), 1),
            },
            "terrain_metrics": {
                "total_area_m2": round(float(sum([t["area_m2"] for t in terrain])), 1),
            },
        },
        "structures": structures,
        "roads": roads,
        "vegetation": vegetation,
        "terrain": terrain,
    }

    # Save extracted structures and full attributes locally and in scene dir
    structures_json_path = output_dir / "extracted_structures.json"
    with open(structures_json_path, "w", encoding="utf-8") as f:
        json.dump(structures, f, indent=2)

    with open(scene_dir / "extracted_structures.json", "w", encoding="utf-8") as f:
        json.dump(structures, f, indent=2)

    with open(output_dir / "classified_attributes.json", "w", encoding="utf-8") as f:
        json.dump(classified_attributes, f, indent=2)

    with open(scene_dir / "classified_attributes.json", "w", encoding="utf-8") as f:
        json.dump(classified_attributes, f, indent=2)

    # Load into PostGIS if structures or layers exist
    if len(structures) > 0 or len(roads) > 0 or len(vegetation) > 0:
        await load_structures_to_db(
            structures_json_path=str(structures_json_path),
            project_name=f"Verified Spatial Twin ({active_job_id[:8]})",
            roads=roads,
            vegetation=vegetation,
            terrain=terrain,
        )

    # Read updated splat positions for bounding box
    updated_data = np.fromfile(splat_path, dtype=SPLAT_DTYPE)
    updated_pos = updated_data["xyz"]

    # Enable query and edit capabilities in the scene manifest
    manifest["version"] = f"{active_job_id}_aligned"
    manifest["capabilities"] = {"queries": True, "edits": True}
    manifest["scale_status"] = "METRIC_APPROXIMATE"
    manifest["semantics"] = "EXTRACTED_STRUCTURES"
    manifest["coordinate_frame"] = "ALIGNED_GROUND"
    manifest["scale_factor"] = round(scale_factor, 2)
    manifest["classification"] = {
        "attributes": classified_attributes,
        "classes_available": ["structure", "road", "vegetation", "terrain"],
    }
    manifest["bounds"] = {
        "min": [float(updated_pos[:, 0].min()), float(updated_pos[:, 1].min()), float(updated_pos[:, 2].min())],
        "max": [float(updated_pos[:, 0].max()), float(updated_pos[:, 1].max()), float(updated_pos[:, 2].max())],
    }

    # Update camera if ground transform was performed
    if T is not None and "camera" in manifest:
        cam = manifest["camera"]
        cam_pos = np.array(cam.get("position", [0.0, 0.0, 10.0]), dtype=np.float32)
        cam_target = np.array(cam.get("target", [0.0, 0.0, 0.0]), dtype=np.float32)
        cam_up = np.array(cam.get("up", [0.0, -1.0, 0.0]), dtype=np.float32)
        norm_up = np.linalg.norm(cam_up)
        if norm_up > 1e-6:
            cam_up = cam_up / norm_up

        cam["position"] = (apply_transform(cam_pos[None, :], T)[0] * scale_factor).tolist()
        cam["target"] = (apply_transform(cam_target[None, :], T)[0] * scale_factor).tolist()
        cam["up"] = (T[:3, :3] @ cam_up).tolist()
        cam["near"] = float(max(0.1, cam.get("near", 0.1) * scale_factor))
        cam["far"] = float(max(100.0, cam.get("far", 1000.0) * scale_factor))

    # Recompute splat sha256
    manifest.setdefault("sha256", {})["scene.splat"] = sha256_file(splat_path)

    if "limitations" in manifest:
        manifest["limitations"] = [
            f"Observed surfaces from {manifest.get('source_name', 'drone footage')}.",
            "Metric approximate coordinates (scaled to realistic building elevations).",
            "Extracted building proxy geometries are loaded in PostGIS; queries and edits enabled.",
        ]

    # Atomically write manifest to scene directory and static root
    atomic_json(scene_dir / "manifest.json", manifest)
    atomic_json(current_scene_path, manifest)

    return {
        "status": "success",
        "job_id": active_job_id,
        "buildings_extracted": len(structures),
        "manifest": manifest,
    }
