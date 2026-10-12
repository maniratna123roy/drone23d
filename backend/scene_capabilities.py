"""Never present legacy seeded database objects as a newly uploaded scene."""
from pathlib import Path
from fastapi import HTTPException
from backend.config import settings
from pipeline.scene_publication import read_current_scene


def require_capability(capability: str) -> None:
    try:
        scene = read_current_scene(Path(settings.STATIC_ASSETS_DIR))
    except (OSError, ValueError, TypeError) as exc:
        raise HTTPException(503, "The verified scene is unavailable; unrelated database objects will not be used.") from exc
    if not scene:
        raise HTTPException(409, "Upload and verify a reconstruction first. Demo database objects are not a substitute for your footage.")
    if not scene.get("capabilities", {}).get(capability):
        raise HTTPException(409, "This scene has relative, uncalibrated scale and unknown semantic labels. Metric queries and building edits are unavailable; old database objects will not be used.")


def require_query_scene() -> None:
    require_capability("queries")


def require_edit_scene() -> None:
    require_capability("edits")
