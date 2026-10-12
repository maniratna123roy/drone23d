"""
Spatial Twin: Building Geometry Extraction (pipeline/05b_extract_geometry.py)

Beginner Analogy:
Using a cookie cutter to stamp out each building footprint from above:
Drone Gaussian Splats are just millions of colored points floating in space.
This script isolates the building splats, groups points that belong to the same building
using DBSCAN clustering, draws a tight 2D polygon boundary around each footprint,
and measures its true physical height and ground area.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
import argparse
import numpy as np
from sklearn.cluster import DBSCAN
from shapely.geometry import MultiPoint, mapping, Polygon

def determine_region(cx: float, cy: float) -> str:
    """Classifies a building into one of the 5 project sectors."""
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

def extract_geometries(positions_path: str = "./output/mill/aligned_positions.npy",
                       labels_path: str = "./output/mill/labels.npy",
                       output_path: str = "./output/mill/extracted_structures.json",
                       eps: float = 4.0,
                       min_samples: int = 30):
    print("[INFO] Loading aligned positions and semantic labels...")
    positions = np.load(positions_path)
    labels = np.load(labels_path)
    
    # Filter only structure splats (class 0)
    structure_mask = (labels == 0)
    struct_pts = positions[structure_mask]
    print(f"[INFO] Found {len(struct_pts)} structure splats to cluster.")
    
    # Run DBSCAN on 2D coordinates (X, Y)
    print(f"[INFO] Running DBSCAN clustering (eps={eps}m, min_samples={min_samples})...")
    xy = struct_pts[:, :2]
    clustering = DBSCAN(eps=eps, min_samples=min_samples, n_jobs=-1).fit(xy)
    cluster_labels = clustering.labels_
    
    unique_clusters = sorted([c for c in set(cluster_labels) if c != -1])
    if len(unique_clusters) == 0 and len(struct_pts) > 0:
        print("[WARN] No dense clusters found at min_samples=30, falling back to all structure points as 1 building.")
        cluster_labels = np.zeros(len(struct_pts), dtype=int)
        unique_clusters = [0]
    print(f"[INFO] Discovered {len(unique_clusters)} distinct building structures!")
    
    extracted = []
    
    for idx, c_id in enumerate(unique_clusters):
        c_mask = (cluster_labels == c_id)
        c_pts = struct_pts[c_mask]
        
        # 3D Bounding Box
        min_x, min_y, min_z = np.min(c_pts, axis=0)
        max_x, max_y, max_z = np.max(c_pts, axis=0)
        
        # 95th percentile height (robust against stray airborne splats)
        ground_z = max(0.0, float(min_z))
        p95_z = float(np.percentile(c_pts[:, 2], 98))
        height_m = round(p95_z - ground_z, 1)
        
        # Centroid
        cx = float((min_x + max_x) / 2.0)
        cy = float((min_y + max_y) / 2.0)
        region = determine_region(cx, cy)
        
        # 2D Convex Hull footprint
        c_xy = c_pts[:, :2]
        mp = MultiPoint(c_xy)
        hull = mp.convex_hull
        
        # Simplify geometry slightly for clean storage
        if isinstance(hull, Polygon):
            poly = hull.simplify(0.2, preserve_topology=True)
            area_m2 = round(float(poly.area), 1)
            geojson_geom = mapping(poly)
        else:
            # Fallback if points were collinear
            poly = hull.buffer(1.0)
            area_m2 = round(float(poly.area), 1)
            geojson_geom = mapping(poly)
            
        building_info = {
            "building_id": idx + 1,
            "class": "structure",
            "region": region,
            "height_m": height_m,
            "original_height_m": height_m,
            "area_m2": area_m2,
            "splat_count": int(np.sum(c_mask)),
            "splat_bbox": {
                "min_x": round(float(min_x), 2),
                "min_y": round(float(min_y), 2),
                "min_z": round(float(min_z), 2),
                "max_x": round(float(max_x), 2),
                "max_y": round(float(max_y), 2),
                "max_z": round(float(max_z), 2)
            },
            "footprint": geojson_geom
        }
        extracted.append(building_info)
        print(f"  • Building #{idx+1:02d} [{region.upper()}]: Height={height_m}m, Area={area_m2}m², Splats={building_info['splat_count']}")
        
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(extracted, f, indent=2)
        
    print(f"\n[SUCCESS] Extracted {len(extracted)} building geometries -> {out_file}")
    return len(extracted)

if __name__ == "__main__":
    extract_geometries()
