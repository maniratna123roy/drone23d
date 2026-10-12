"""
Spatial Twin: PostGIS Database Loader (pipeline/06_load_db.py)

Beginner Analogy:
Filing architectural deeds into the city hall records:
It takes the extracted building polygons, heights, and bounding boxes,
connects to the PostGIS spatial database, and stores each structure as both
a 2D footprint and an extruded 3D solid geometry (PolyhedralSurfaceZ)
so it can be instantly queried in SQL or edited via natural language.
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import json
import asyncio
import asyncpg
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.environ.get("POSTGRES_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("POSTGRES_PORT", 5435))
DB_USER = os.environ.get("POSTGRES_USER", "spatial_user")
DB_PASSWORD = os.environ.get("POSTGRES_PASSWORD", "spatial_password")
DB_NAME = os.environ.get("POSTGRES_DB", "spatial_twin")

async def load_structures_to_db(structures_json_path: str = "./output/mill/extracted_structures.json",
                                transform_json_path: str = "./output/mill/frame_transform.json",
                                project_name: str = "Mill-19 Digital Twin",
                                roads: list = None,
                                vegetation: list = None,
                                terrain: list = None):
    print("=" * 60)
    print("POSTGIS DATABASE LOADER (Pipeline Stage 06)")
    print("=" * 60)
    
    try:
        from backend.config import settings
        db_url = settings.database_url
    except Exception:
        db_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    print(f"[INFO] Connecting to database...")
    conn = await asyncpg.connect(db_url)
    
    try:
        # 1. Load transformation matrix if available
        transform_data = []
        if Path(transform_json_path).exists():
            with open(transform_json_path) as f:
                t_info = json.load(f)
                transform_data = t_info.get("transform_matrix_4x4", [])
                
        # 2. Insert or update project (pinned ID 1 for idempotency)
        project_row = await conn.fetchrow(
            """
            INSERT INTO projects (id, name, scale_factor, frame_transform)
            VALUES (1, $2, 1.0, $1::jsonb)
            ON CONFLICT (id) DO UPDATE SET 
                name = EXCLUDED.name,
                frame_transform = EXCLUDED.frame_transform
            RETURNING id;
            """,
            json.dumps(transform_data),
            project_name
        )
        project_id = project_row["id"]
        print(f"[INFO] Registered Project: '{project_name}' (ID: {project_id})")
        
        # 3. Read extracted structures
        with open(structures_json_path) as f:
            structures = json.load(f)
            
        print(f"[INFO] Read {len(structures)} structures from {structures_json_path}")
        
        # 4. Clean previous records for idempotency
        await conn.execute("DELETE FROM structures WHERE project_id = $1;", project_id)
        
        # 5. Insert each structure with extruded 3D solid geometry
        inserted_count = 0
        for b in structures:
            footprint_geojson = json.dumps(b["footprint"])
            bbox_json = json.dumps(b["splat_bbox"])
            height = float(b["height_m"])
            area = float(b["area_m2"])
            region = b["region"]
            
            # Using ST_Extrude to generate 3D PolyhedralSurfaceZ from 2D footprint
            await conn.execute(
                """
                INSERT INTO structures (
                    project_id, class, footprint, solid, height_m, original_height_m, area_m2, region, splat_bbox
                )
                VALUES (
                    $1, 
                    'structure', 
                    ST_SetSRID(ST_GeomFromGeoJSON($2), 0),
                    ST_Extrude(ST_SetSRID(ST_GeomFromGeoJSON($2), 0), 0, 0, $3),
                    $3, 
                    $3, 
                    $4, 
                    $5, 
                    $6::jsonb
                );
                """,
                project_id, footprint_geojson, height, area, region, bbox_json
            )
            inserted_count += 1
            
        print(f"[SUCCESS] Inserted {inserted_count} structures with 3D SFCGAL solids!")

        # 6. Insert roads if available
        if roads:
            await conn.execute("DELETE FROM roads WHERE project_id = $1;", project_id)
            for r in roads:
                boundary_geojson = json.dumps(r["footprint"])
                bbox_json = json.dumps(r.get("splat_bbox", {}))
                await conn.execute(
                    """
                    INSERT INTO roads (project_id, class, boundary, length_m, width_m, area_m2, splat_bbox)
                    VALUES ($1, 'road', ST_SetSRID(ST_GeomFromGeoJSON($2), 0), $3, $4, $5, $6::jsonb);
                    """,
                    project_id, boundary_geojson, float(r.get("length_m", 0.0)), float(r.get("width_m", 0.0)), float(r.get("area_m2", 0.0)), bbox_json
                )
            print(f"[SUCCESS] Inserted {len(roads)} road corridors into PostGIS!")

        # 7. Insert vegetation if available
        if vegetation:
            await conn.execute("DELETE FROM vegetation WHERE project_id = $1;", project_id)
            for v in vegetation:
                boundary_geojson = json.dumps(v["footprint"])
                bbox_json = json.dumps(v.get("splat_bbox", {}))
                await conn.execute(
                    """
                    INSERT INTO vegetation (project_id, class, boundary, height_m, width_m, area_m2, splat_bbox)
                    VALUES ($1, 'vegetation', ST_SetSRID(ST_GeomFromGeoJSON($2), 0), $3, $4, $5, $6::jsonb);
                    """,
                    project_id, boundary_geojson, float(v.get("canopy_height_m", 0.0)), float(v.get("spread_width_m", 0.0)), float(v.get("area_m2", 0.0)), bbox_json
                )
            print(f"[SUCCESS] Inserted {len(vegetation)} vegetation clusters into PostGIS!")

        # 8. Insert terrain if available
        if terrain:
            await conn.execute("DELETE FROM terrain WHERE project_id = $1;", project_id)
            for t in terrain:
                boundary_geojson = json.dumps(t["footprint"])
                bbox_json = json.dumps(t.get("splat_bbox", {}))
                await conn.execute(
                    """
                    INSERT INTO terrain (project_id, class, boundary, elevation_m, area_m2, splat_bbox)
                    VALUES ($1, 'terrain', ST_SetSRID(ST_GeomFromGeoJSON($2), 0), $3, $4, $5::jsonb);
                    """,
                    project_id, boundary_geojson, float(t.get("elevation_m", 0.0)), float(t.get("area_m2", 0.0)), bbox_json
                )
            print(f"[SUCCESS] Inserted {len(terrain)} terrain zones into PostGIS!")
        
        # 6. Verification query
        stats = await conn.fetchrow(
            """
            SELECT 
                COUNT(*) as total_count,
                ROUND(AVG(height_m)::numeric, 1) as avg_height,
                ROUND(MIN(height_m)::numeric, 1) as min_height,
                ROUND(MAX(height_m)::numeric, 1) as max_height,
                ROUND(SUM(area_m2)::numeric, 1) as total_footprint_area
            FROM structures
            WHERE project_id = $1;
            """,
            project_id
        )
        
        print("-" * 60)
        print("DATABASE SUMMARY (Live PostGIS Verification):")
        print(f"  • Total Buildings Stored : {stats['total_count']}")
        print(f"  • Height Range           : {stats['min_height']}m to {stats['max_height']}m (Avg: {stats['avg_height']}m)")
        print(f"  • Total Footprint Area   : {stats['total_footprint_area']} m²")
        print("-" * 60)
        
        # Query taller than 20m check (The core hackathon demo query!)
        tall_buildings = await conn.fetch(
            """
            SELECT id, region, height_m, area_m2 
            FROM structures 
            WHERE height_m > 20.0 AND project_id = $1
            ORDER BY height_m DESC;
            """,
            project_id
        )
        print(f"[VERIFY] Test Query: 'Which buildings are taller than 20 metres?'")
        print(f"         Returned {len(tall_buildings)} matching buildings:")
        for tb in tall_buildings:
            print(f"         - ID #{tb['id']:02d} [{tb['region'].upper()}]: {tb['height_m']}m tall ({tb['area_m2']}m²)")
            
        return stats['total_count']
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(load_structures_to_db())
