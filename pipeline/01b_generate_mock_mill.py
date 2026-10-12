"""
Spatial Twin: Realistic Mill-19 Scene Generator (pipeline/01b_generate_mock_mill.py)

Beginner Analogy:
A high-precision 3D flight simulator test-bed:
It synthesizes a photorealistic 3D Gaussian point cloud of an industrial mill complex
with 10 distinct buildings, paved roads, undulating terrain, and vegetation.
This allows full offline ML pipeline verification (RANSAC, DBSCAN, PostGIS loader, and Splat exporter)
without waiting 35 minutes for a remote cloud GPU run.
"""

import os
import json
import numpy as np
from pathlib import Path
from plyfile import PlyData, PlyElement

def generate_mill_scene(output_dir: str = "./output/mill", num_splats: int = 60000):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    
    np.random.seed(42)
    positions = []
    colors = []
    scales = []
    rotations = []
    opacities = []
    classes = []
    
    # 1. Ground Terrain & Roads (class 1: terrain, class 2: road)
    n_ground = int(num_splats * 0.40)
    gx = np.random.uniform(-60, 60, n_ground)
    gy = np.random.uniform(-60, 60, n_ground)
    # Give ground a slight tilt and undulation (to prove RANSAC leveling works!)
    gz = 0.05 * gx - 0.02 * gy + np.random.normal(0, 0.15, n_ground) + 1.2
    
    # Road network (a crossroad at x ≈ 0 and y ≈ 0)
    is_road = (np.abs(gx) < 4.0) | (np.abs(gy) < 4.0)
    
    for i in range(n_ground):
        positions.append([gx[i], gy[i], gz[i]])
        scales.append([0.3, 0.3, 0.05])
        rotations.append([1.0, 0.0, 0.0, 0.0])
        opacities.append(0.85)
        if is_road[i]:
            classes.append(2)  # Road
            colors.append([70, 70, 75, 255])
        else:
            classes.append(1)  # Terrain
            colors.append([120, 115, 95, 255])
            
    # 2. 10 Distinct Industrial Buildings (class 0: structure)
    # Define building centers, sizes (width_x, length_y, height_z)
    buildings = [
        {"id": 1, "cx": -12.0, "cy": -10.0, "wx": 14.0, "wy": 16.0, "h": 28.0, "name": "Main Mill Plant A"},
        {"id": 2, "cx": 12.0, "cy": 10.0, "wx": 15.0, "wy": 14.0, "h": 36.0, "name": "Blast Furnace Tower"},
        {"id": 3, "cx": -14.0, "cy": 12.0, "wx": 12.0, "wy": 12.0, "h": 22.0, "name": "Rolling Mill B"},
        {"id": 4, "cx": 14.0, "cy": -12.0, "wx": 10.0, "wy": 12.0, "h": 18.0, "name": "Cooling Bed Warehouse"},
        {"id": 5, "cx": 0.0, "cy": 38.0, "wx": 22.0, "wy": 12.0, "h": 44.0, "name": "Northern Smelter"},
        {"id": 6, "cx": -38.0, "cy": 0.0, "wx": 14.0, "wy": 20.0, "h": 32.0, "name": "Western Assembly Hall"},
        {"id": 7, "cx": 38.0, "cy": 0.0, "wx": 12.0, "wy": 18.0, "h": 25.0, "name": "Eastern Machine Shop"},
        {"id": 8, "cx": 0.0, "cy": -40.0, "wx": 20.0, "wy": 14.0, "h": 16.0, "name": "Southern Storage Unit"},
        {"id": 9, "cx": -35.0, "cy": 35.0, "wx": 12.0, "wy": 10.0, "h": 15.0, "name": "Northwest Substation"},
        {"id": 10, "cx": 35.0, "cy": 35.0, "wx": 10.0, "wy": 12.0, "h": 48.0, "name": "Northeast High-Bay Silo"}
    ]
    
    n_bldg_splats = int(num_splats * 0.45)
    splats_per_bldg = n_bldg_splats // len(buildings)
    
    for b in buildings:
        cx, cy = b["cx"], b["cy"]
        wx, wy, h = b["wx"], b["wy"], b["h"]
        ground_at_bldg = 0.05 * cx - 0.02 * cy + 1.2
        
        # Distribute points on walls and roof
        bx = np.random.uniform(cx - wx/2, cx + wx/2, splats_per_bldg)
        by = np.random.uniform(cy - wy/2, cy + wy/2, splats_per_bldg)
        bz = np.random.uniform(ground_at_bldg, ground_at_bldg + h, splats_per_bldg)
        
        # Concentrate half on roof, half on exterior walls
        roof_idx = np.random.choice(splats_per_bldg, splats_per_bldg // 3, replace=False)
        bz[roof_idx] = ground_at_bldg + h + np.random.normal(0, 0.2, len(roof_idx))
        
        for j in range(splats_per_bldg):
            positions.append([bx[j], by[j], bz[j]])
            scales.append([0.25, 0.25, 0.25])
            rotations.append([1.0, 0.0, 0.0, 0.0])
            opacities.append(0.95)
            classes.append(0)  # Structure
            colors.append([180, 75, 60, 255] if b["h"] > 30 else [140, 140, 150, 255])
            
    # 3. Surrounding Vegetation / Trees (class 3: vegetation)
    n_trees = num_splats - len(positions)
    tx = np.random.uniform(-55, 55, n_trees)
    ty = np.random.uniform(-55, 55, n_trees)
    # Place trees along outskirts or between buildings
    tz = 0.05 * tx - 0.02 * ty + 1.2 + np.random.uniform(0.5, 6.0, n_trees)
    
    for k in range(n_trees):
        positions.append([tx[k], ty[k], tz[k]])
        scales.append([0.35, 0.35, 0.35])
        rotations.append([1.0, 0.0, 0.0, 0.0])
        opacities.append(0.9)
        classes.append(3)  # Vegetation
        colors.append([45, 130, 50, 255])
        
    pos_arr = np.array(positions, dtype=np.float32)
    col_arr = np.array(colors, dtype=np.uint8)
    scale_arr = np.array(scales, dtype=np.float32)
    rot_arr = np.array(rotations, dtype=np.float32)
    op_arr = np.array(opacities, dtype=np.float32)
    cls_arr = np.array(classes, dtype=np.uint8)
    
    # Save standard PLY
    vertex_dtype = [
        ('x', 'f4'), ('y', 'f4'), ('z', 'f4'),
        ('red', 'u1'), ('green', 'u1'), ('blue', 'u1'), ('alpha', 'u1'),
        ('scale_0', 'f4'), ('scale_1', 'f4'), ('scale_2', 'f4'),
        ('rot_0', 'f4'), ('rot_1', 'f4'), ('rot_2', 'f4'), ('rot_3', 'f4'),
        ('opacity', 'f4')
    ]
    
    v_data = np.empty(len(pos_arr), dtype=vertex_dtype)
    v_data['x'] = pos_arr[:, 0]
    v_data['y'] = pos_arr[:, 1]
    v_data['z'] = pos_arr[:, 2]
    v_data['red'] = col_arr[:, 0]
    v_data['green'] = col_arr[:, 1]
    v_data['blue'] = col_arr[:, 2]
    v_data['alpha'] = col_arr[:, 3]
    v_data['scale_0'] = np.log(scale_arr[:, 0])
    v_data['scale_1'] = np.log(scale_arr[:, 1])
    v_data['scale_2'] = np.log(scale_arr[:, 2])
    v_data['rot_0'] = rot_arr[:, 0]
    v_data['rot_1'] = rot_arr[:, 1]
    v_data['rot_2'] = rot_arr[:, 2]
    v_data['rot_3'] = rot_arr[:, 3]
    v_data['opacity'] = np.log(op_arr / (1.0 - op_arr + 1e-6))
    
    ply_el = PlyElement.describe(v_data, 'vertex')
    ply_path = out / "point_cloud.ply"
    PlyData([ply_el]).write(str(ply_path))
    
    # Save labels.npy
    np.save(out / "labels.npy", cls_arr)
    
    # Save metadata
    meta = {
        "num_splats": len(pos_arr),
        "buildings_count": len(buildings),
        "buildings": buildings,
        "classes_distribution": {
            "structures": int(np.sum(cls_arr == 0)),
            "terrain": int(np.sum(cls_arr == 1)),
            "roads": int(np.sum(cls_arr == 2)),
            "vegetation": int(np.sum(cls_arr == 3))
        }
    }
    with open(out / "metadata.json", "w") as f:
        json.dump(meta, f, indent=2)
        
    print(f"[SUCCESS] Generated Mill-19 scene point cloud: {ply_path}")
    print(f"          Total Splats: {len(pos_arr)}")
    print(f"          Structures  : {meta['classes_distribution']['structures']} splats across 10 buildings")
    print(f"          Terrain/Road: {meta['classes_distribution']['terrain'] + meta['classes_distribution']['roads']} splats")
    print(f"          Vegetation  : {meta['classes_distribution']['vegetation']} splats")
    return True

if __name__ == "__main__":
    generate_mill_scene()
