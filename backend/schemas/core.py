from pydantic import BaseModel
from typing import Any

class Region(BaseModel):
    id: str
    name: str
    boundary: Any

class Project(BaseModel):
    id: int
    name: str
    scale_factor: float
    frame_transform: Any

class Structure(BaseModel):
    id: int
    project_id: int
    class_name: str
    label: str | None = None
    footprint: Any
    height_m: float
    width_m: float | None = None
    depth_m: float | None = None
    area_m2: float
    volume_m3: float | None = None
    elevation_m: float | None = None
    region: str | None = None
    splat_bbox: dict | None = None
    original_height_m: float | None = None
    version: int

class SystemStatus(BaseModel):
    status: str
    db_connected: bool
