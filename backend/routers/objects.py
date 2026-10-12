from fastapi import APIRouter, Response, Depends
from backend.scene_capabilities import require_query_scene
from typing import List, Optional
from backend.schemas.core import Structure, Region, Project
from backend.db.queries import fetch_all_structures, fetch_all_regions, fetch_project

router = APIRouter(prefix="/api/objects", dependencies=[Depends(require_query_scene)])

@router.get("/project", response_model=Optional[Project])
async def get_project(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return await fetch_project(1)

@router.get("/structures", response_model=List[Structure])
async def get_structures(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return await fetch_all_structures()

@router.get("/regions", response_model=List[Region])
async def get_regions(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return await fetch_all_regions()

@router.get("/classified-attributes")
async def get_classified_attributes(response: Response):
    """Returns classified attributes for structures, roads, vegetation, and terrain."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    import json
    from pathlib import Path
    from backend.config import settings

    static_dir = Path(settings.STATIC_ASSETS_DIR).resolve()
    current_scene_path = static_dir / "current-scene.json"
    if current_scene_path.is_file():
        try:
            with open(current_scene_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            if "classification" in manifest and "attributes" in manifest["classification"]:
                return manifest["classification"]["attributes"]
        except Exception:
            pass

    local_path = Path("output/mill/classified_attributes.json")
    if local_path.is_file():
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass

    return {
        "summary": {
            "structures_count": 0,
            "roads_count": 0,
            "vegetation_count": 0,
            "terrain_count": 0,
            "structures_metrics": {},
            "roads_metrics": {},
            "vegetation_metrics": {},
            "terrain_metrics": {},
        },
        "structures": [],
        "roads": [],
        "vegetation": [],
        "terrain": [],
    }
