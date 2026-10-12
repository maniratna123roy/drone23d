from fastapi import APIRouter
from backend.schemas.core import SystemStatus
from backend.db.connection import get_pool

router = APIRouter(prefix="/api")

@router.get("/status", response_model=SystemStatus)
async def get_status():
    try:
        pool = get_pool()
        db_connected = not pool.is_closing()
    except Exception:
        db_connected = False
        
    return SystemStatus(
        status="OK",
        db_connected=db_connected
    )
