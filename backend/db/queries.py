import json
from backend.db.connection import get_pool

async def fetch_project(project_id: int = 1):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, name, scale_factor, frame_transform FROM projects WHERE id = $1;", project_id)
        if not row:
            return None
        ft = row["frame_transform"]
        if isinstance(ft, str):
            ft = json.loads(ft)
        return {
            "id": row["id"],
            "name": row["name"],
            "scale_factor": row["scale_factor"],
            "frame_transform": ft
        }

async def fetch_all_regions():
    pool = get_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch("SELECT id, name, ST_AsGeoJSON(boundary) as boundary FROM regions;")
        return [{"id": r["id"], "name": r["name"], "boundary": json.loads(r["boundary"])} for r in records]

async def fetch_all_structures():
    pool = get_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch("""
            SELECT id, project_id, class as class_name, ST_AsGeoJSON(footprint) as footprint,
                   height_m, area_m2, region, splat_bbox, original_height_m, version
            FROM structures;
        """)
        results = []
        for r in records:
            bbox = json.loads(r["splat_bbox"]) if r["splat_bbox"] and isinstance(r["splat_bbox"], str) else r["splat_bbox"]
            width_m = None
            depth_m = None
            elevation_m = None
            if bbox and isinstance(bbox, dict):
                min_x = bbox.get("min_x")
                max_x = bbox.get("max_x")
                min_y = bbox.get("min_y")
                max_y = bbox.get("max_y")
                min_z = bbox.get("min_z")
                if min_x is not None and max_x is not None:
                    width_m = round(float(max_x - min_x), 1)
                if min_y is not None and max_y is not None:
                    depth_m = round(float(max_y - min_y), 1)
                if min_z is not None:
                    elevation_m = round(float(min_z), 2)
            
            h = float(r["height_m"]) if r["height_m"] is not None else 0.0
            a = float(r["area_m2"]) if r["area_m2"] is not None else 0.0
            vol = round(a * h, 1) if (a and h) else None
            reg = (r["region"] or "center").upper()
            
            results.append({
                "id": r["id"],
                "project_id": r["project_id"],
                "class_name": r["class_name"],
                "label": f"Building #{r['id']} ({reg})",
                "footprint": json.loads(r["footprint"]) if r["footprint"] else None,
                "height_m": r["height_m"],
                "width_m": width_m,
                "depth_m": depth_m,
                "area_m2": r["area_m2"],
                "volume_m3": vol,
                "elevation_m": elevation_m,
                "region": r["region"],
                "splat_bbox": bbox,
                "original_height_m": r["original_height_m"],
                "version": r["version"],
            })
        return results

async def execute_compiled_query(sql: str, params: list):
    pool = get_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch(sql, *params)
        objects = [
            {
                "id": r["id"],
                "project_id": r["project_id"],
                "class_name": r["class_name"],
                "footprint": json.loads(r["footprint"]) if r["footprint"] else None,
                "height_m": r["height_m"],
                "area_m2": r["area_m2"],
                "region": r["region"],
                "splat_bbox": json.loads(r["splat_bbox"]) if r["splat_bbox"] and isinstance(r["splat_bbox"], str) else r["splat_bbox"],
                "original_height_m": r["original_height_m"],
                "version": r["version"]
            }
            for r in records
        ]

        count = len(objects)
        matched_ids = [obj["id"] for obj in objects]
        
        if count > 0:
            heights = [obj["height_m"] for obj in objects if obj["height_m"] is not None]
            areas = [obj["area_m2"] for obj in objects if obj["area_m2"] is not None]
            avg_height = round(sum(heights) / len(heights), 2) if heights else 0.0
            total_area = round(sum(areas), 2) if areas else 0.0
            min_height = round(min(heights), 2) if heights else 0.0
            max_height = round(max(heights), 2) if heights else 0.0
        else:
            avg_height = 0.0
            total_area = 0.0
            min_height = 0.0
            max_height = 0.0

        metrics = {
            "count": count,
            "avg_height_m": avg_height,
            "total_area_m2": total_area,
            "min_height_m": min_height,
            "max_height_m": max_height
        }

        return {
            "matched_ids": matched_ids,
            "objects": objects,
            "metrics": metrics
        }


async def fetch_structures_by_ids(ids: list):
    if not ids:
        return []
    pool = get_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch("""
            SELECT id, project_id, class as class_name, ST_AsGeoJSON(footprint) as footprint,
                   height_m, area_m2, region, splat_bbox, original_height_m, version
            FROM structures
            WHERE id = ANY($1::int[])
            ORDER BY id ASC;
        """, ids)
        return [
            {
                "id": r["id"],
                "project_id": r["project_id"],
                "class_name": r["class_name"],
                "footprint": json.loads(r["footprint"]) if r["footprint"] else None,
                "height_m": r["height_m"],
                "area_m2": r["area_m2"],
                "region": r["region"],
                "splat_bbox": json.loads(r["splat_bbox"]) if r["splat_bbox"] and isinstance(r["splat_bbox"], str) else r["splat_bbox"],
                "original_height_m": r["original_height_m"],
                "version": r["version"]
            }
            for r in records
        ]


async def apply_extrude_edit(session_id: str, command: str, intent_dict: dict, object_ids: list, delta_height_m: float):
    """
    Applies an extrusion modification atomically:
    1. Records session in edit_sessions
    2. Snapshots current state of objects into geometry_history
    3. Updates height_m and increments version in structures
    Returns list of updated structure records.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. Insert into edit_sessions
            await conn.execute("""
                INSERT INTO edit_sessions (id, command, intent)
                VALUES ($1, $2, $3::jsonb)
                ON CONFLICT (id) DO UPDATE SET command = EXCLUDED.command, intent = EXCLUDED.intent;
            """, session_id, command, json.dumps(intent_dict))

            # 2. Snapshot current state into geometry_history
            await conn.execute("""
                INSERT INTO geometry_history (object_id, session_id, operation, footprint, solid, height_m, version)
                SELECT id, $1, 'EXTRUDE', footprint, solid, height_m, version
                FROM structures
                WHERE id = ANY($2::int[]);
            """, session_id, object_ids)

            # 3. Update structures with new height and increment version
            await conn.execute("""
                UPDATE structures
                SET height_m = height_m + $1,
                    version = version + 1
                WHERE id = ANY($2::int[]);
            """, delta_height_m, object_ids)

    return await fetch_structures_by_ids(object_ids)


async def rollback_last_edit_session(session_id: str = None):
    """
    Rolls back an edit session using geometry_history.
    If session_id is not specified, rolls back the most recent session.
    Returns (session_id, list of restored structure ids).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            if not session_id:
                row = await conn.fetchrow("""
                    SELECT id FROM edit_sessions ORDER BY created_at DESC LIMIT 1;
                """)
                if not row:
                    return None, []
                session_id = row["id"]

            history_rows = await conn.fetch("""
                SELECT object_id, height_m, version
                FROM geometry_history
                WHERE session_id = $1;
            """, session_id)

            if not history_rows:
                return session_id, []

            affected_ids = []
            for h in history_rows:
                obj_id = h["object_id"]
                prev_height = h["height_m"]
                prev_version = h["version"]
                await conn.execute("""
                    UPDATE structures
                    SET height_m = $1,
                        version = $2
                    WHERE id = $3;
                """, prev_height, prev_version, obj_id)
                affected_ids.append(obj_id)

            # Clean up rolled back history and session
            await conn.execute("DELETE FROM geometry_history WHERE session_id = $1;", session_id)
            await conn.execute("DELETE FROM edit_sessions WHERE id = $1;", session_id)

            return session_id, affected_ids

