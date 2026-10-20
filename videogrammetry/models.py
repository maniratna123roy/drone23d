"""Data models for Videogrammetry Sidecar.
Implements the sidecar data schemas defined in Section 7 & 8 of the architecture:
- captures
- jobs
- job_stages
- artifacts
- quality_reports
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

class CaptureStatus(str, Enum):
    CREATED = "created"
    UPLOADING = "uploading"
    QUEUED = "queued"
    PROCESSING = "processing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    DEGRADED = "degraded"
    FAILED = "failed"

class StageName(str, Enum):
    STAGE_0_PROBE = "stage0_probe"
    STAGE_1_FRAMES = "stage1_frames"
    STAGE_2_MASKING = "stage2_masking"
    STAGE_3_SFM = "stage3_sfm"
    STAGE_4_DENSE = "stage4_dense"
    STAGE_5_MESH = "stage5_mesh"
    STAGE_6_GEOREF = "stage6_georef"
    STAGE_7_QUALITY_GATE = "stage7_quality_gate"
    STAGE_8_EXPORT = "stage8_export"

class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"

class QualityVerdict(str, Enum):
    PASS = "pass"
    RETRY = "retry"
    DEGRADED = "degraded"
    FAIL = "fail"

class QualityMetrics(BaseModel):
    registered_frames_ratio: float = 0.0
    mean_reprojection_error_px: float = 0.0
    sparse_points_count: int = 0
    dense_points_count: int = 0
    mesh_triangles_count: int = 0
    mesh_hole_area_ratio: float = 0.0
    held_out_ssim: float = 0.0
    outlier_geometry_ratio: float = 0.0
    ground_sample_distance_cm: float = 2.5
    scale_accuracy_note: str = "Metric scale estimated via GPS prior Umeyama alignment (relative error ~1-2%, absolute error subject to GPS accuracy)"

class QualityReport(BaseModel):
    job_id: str
    attempt: int
    metrics: QualityMetrics
    verdict: QualityVerdict
    retry_strategy: Optional[str] = None
    evaluated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ArtifactRef(BaseModel):
    id: str
    capture_id: str
    kind: str  # glb, obj, usdz, laz, cog_geotiff, orthomosaic_png, dsm, manifest_json
    filename: str
    uri: str
    sha256: str = ""
    bytes: int = 0
    mime_type: str = "application/octet-stream"
    produced_by_stage: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class StageRecord(BaseModel):
    stage: StageName
    title: str
    status: StageStatus = StageStatus.PENDING
    progress: float = 0.0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration_s: float = 0.0
    metrics: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

class Capture(BaseModel):
    id: str
    source_system: str = "vantage_spatial_twin"
    source_id: Optional[str] = None
    content_hash: Optional[str] = None
    tier: str = "standard"
    status: CaptureStatus = CaptureStatus.CREATED
    crs: str = "EPSG:4326"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    current_stage: Optional[StageName] = None
    progress: float = 0.0
    attempt: int = 1
    max_attempts: int = 2
    video_filename: Optional[str] = None
    video_size_bytes: int = 0
    video_duration_s: float = 0.0
    video_resolution: str = ""
    video_fps: float = 0.0
    has_gps: bool = False
    stages: List[StageRecord] = Field(default_factory=list)
    artifacts: List[ArtifactRef] = Field(default_factory=list)
    quality_report: Optional[QualityReport] = None
    error_message: Optional[str] = None

class CreateCaptureRequest(BaseModel):
    source_system: str = "vantage_spatial_twin"
    source_id: Optional[str] = None
    tier: str = "standard"
    crs: str = "EPSG:4326"

class StartCaptureRequest(BaseModel):
    tier: Optional[str] = None
    gps_file_ref: Optional[str] = None
    crs: Optional[str] = None
