"""Data models for VantageCam v1 Sidecar.
Polycam-inspired drone video to 3D reconstruction with:
- Parallax-based keyframe extraction
- Dual output (mesh + Gaussian splats)
- GPS georeferencing (Umeyama alignment)
- Dynamic object masking
- Orthomosaic / DSM generation
- Automated quality gate with retry ladder

Pydantic schemas for captures, stages, artifacts, and quality reports.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field


class CaptureStatus(str, Enum):
    """Lifecycle states for a VantageCam capture job."""
    CREATED = "created"
    UPLOADING = "uploading"
    QUEUED = "queued"
    PROCESSING = "processing"
    RETRYING = "retrying"
    COMPLETED = "completed"
    DEGRADED = "degraded"
    FAILED = "failed"


class StageName(str, Enum):
    """10-stage pipeline for drone video to 3D reconstruction."""
    STAGE_0_PROBE = "stage0_probe"
    STAGE_1_FRAMES = "stage1_frames"
    STAGE_2_MASKING = "stage2_masking"
    STAGE_3_SFM = "stage3_sfm"
    STAGE_4_DENSE = "stage4_dense"
    STAGE_5A_MESH = "stage5a_mesh"
    STAGE_5B_SPLATS = "stage5b_splats"
    STAGE_6_GEOREF = "stage6_georef"
    STAGE_7_QUALITY_GATE = "stage7_quality_gate"
    STAGE_8_EXPORT = "stage8_export"


class StageStatus(str, Enum):
    """Execution status for each stage."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"


class QualityVerdict(str, Enum):
    """Quality gate verdict determines outcome of stage 7."""
    PASS = "pass"
    RETRY = "retry"
    DEGRADED = "degraded"
    FAIL = "fail"


class QualityMetrics(BaseModel):
    """Quantitative metrics from reconstruction pipeline.
    
    Real-world analogy: Like a builder's checklist — every measurement
    tells you if the house is level, square, and built to spec.
    """
    registered_frames_ratio: float = 0.0
    """Fraction of keyframes successfully localized (target >= 0.85)."""
    
    mean_reprojection_error_px: float = 0.0
    """SfM reprojection error in pixels (target < 1.5 px)."""
    
    sparse_points_count: int = 0
    """Number of 3D points from Structure-from-Motion (target > 50k)."""
    
    dense_points_count: int = 0
    """Number of 3D points after dense reconstruction (target > 1M)."""
    
    mesh_triangles_count: int = 0
    """Mesh triangle count for stage 5a (bounded by tier)."""
    
    mesh_hole_area_ratio: float = 0.0
    """Ratio of holes/unfilled areas (target < 0.1)."""
    
    splat_count: int = 0
    """Number of Gaussian splats (stage 5b)."""
    
    held_out_ssim: float = 0.0
    """SSIM of held-out validation views (target >= 0.85)."""
    
    outlier_geometry_ratio: float = 0.0
    """Ratio of outlier points removed (target < 0.05)."""
    
    ground_sample_distance_cm: float = 2.5
    """Pixel-to-world scale: cm/pixel at ground level."""
    
    scale_accuracy_note: str = "Metric scale estimated via GPS prior Umeyama alignment (relative error ~1-2%, absolute error subject to GPS accuracy)"
    """How scale was determined (GPS or reference prior)."""
    
    orthomosaic_resolution_cm: float = 5.0
    """Orthomosaic GSD (cm/pixel)."""
    
    dsm_resolution_m: float = 0.1
    """Digital Surface Model resolution (m/pixel)."""


class QualityReport(BaseModel):
    """Result of quality gate (stage 7) evaluation."""
    job_id: str
    """Unique capture job identifier."""
    
    attempt: int
    """Which retry attempt this is (1-indexed)."""
    
    metrics: QualityMetrics
    """Quantitative reconstruction metrics."""
    
    verdict: QualityVerdict
    """Pass/Retry/Degraded/Fail."""
    
    retry_strategy: Optional[str] = None
    """If retry: escalation strategy (e.g., 'increase_frames', 'tighter_masking')."""
    
    evaluated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    """ISO 8601 timestamp of evaluation."""


class ArtifactRef(BaseModel):
    """Reference to a produced output file (mesh, splats, orthomosaic, DSM, etc.)."""
    id: str
    """Unique artifact ID (uuidv4)."""
    
    capture_id: str
    """Parent capture job ID."""
    
    kind: str
    """File type: glb, obj, usdz, laz, cog_geotiff, orthomosaic_png, dsm_tif, splat_ply, manifest_json."""
    
    filename: str
    """Filename in artifact directory."""
    
    uri: str
    """Relative path from capture root (e.g., 'out/model.glb')."""
    
    sha256: str = ""
    """SHA256 hash of file (for integrity checking)."""
    
    bytes: int = 0
    """File size in bytes."""
    
    mime_type: str = "application/octet-stream"
    """MIME type (e.g., 'model/gltf-binary', 'text/plain')."""
    
    produced_by_stage: str = ""
    """Stage that produced this (e.g., 'stage5a_mesh')."""
    
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    """ISO 8601 creation timestamp."""


class StageRecord(BaseModel):
    """Execution record for one pipeline stage."""
    stage: StageName
    """Stage identifier (0-8)."""
    
    title: str
    """Human-readable stage title."""
    
    status: StageStatus = StageStatus.PENDING
    """Current execution status."""
    
    progress: float = 0.0
    """Progress 0.0-1.0 (when RUNNING)."""
    
    started_at: Optional[str] = None
    """ISO 8601 start timestamp."""
    
    finished_at: Optional[str] = None
    """ISO 8601 finish timestamp."""
    
    duration_s: float = 0.0
    """Wall-clock duration in seconds."""
    
    metrics: Dict[str, Any] = Field(default_factory=dict)
    """Stage-specific metrics (e.g., frames_extracted, sfm_points)."""
    
    error: Optional[str] = None
    """Error message if FAILED."""


class Capture(BaseModel):
    """Root model for a VantageCam capture job."""
    id: str
    """Unique capture job ID (e.g., 'cap_<timestamp>_<random>')."""
    
    source_system: str = "vantage_spatial_twin"
    """Source system identifier."""
    
    source_id: Optional[str] = None
    """ID in the source system (e.g., Spatial Twin inspection UUID)."""
    
    content_hash: Optional[str] = None
    """SHA256 of video file (for deduplication)."""
    
    tier: str = "standard"
    """Quality tier: lite, standard, premium, premium_advanced."""
    
    status: CaptureStatus = CaptureStatus.CREATED
    """Current job status."""
    
    crs: str = "EPSG:4326"
    """Coordinate Reference System (e.g., WGS84, or projected UTM)."""
    
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    """Job creation timestamp."""
    
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    """Last update timestamp."""
    
    current_stage: Optional[StageName] = None
    """Currently executing stage."""
    
    progress: float = 0.0
    """Overall pipeline progress 0.0-1.0."""
    
    attempt: int = 1
    """Retry attempt number (1-indexed)."""
    
    max_attempts: int = 3
    """Max retry attempts before failure (tier-dependent)."""
    
    video_filename: Optional[str] = None
    """Name of uploaded video file."""
    
    video_size_bytes: int = 0
    """Video file size."""
    
    video_duration_s: float = 0.0
    """Video duration in seconds."""
    
    video_resolution: str = ""
    """Video resolution (e.g., '1920x1080')."""
    
    video_fps: float = 0.0
    """Video frame rate."""
    
    has_gps: bool = False
    """Whether GPS log was provided (enables georeferencing)."""
    
    stages: List[StageRecord] = Field(default_factory=list)
    """Records for all 10 pipeline stages."""
    
    artifacts: List[ArtifactRef] = Field(default_factory=list)
    """Produced mesh, splats, orthomosaic, DSM, etc."""
    
    quality_report: Optional[QualityReport] = None
    """Quality gate verdict and metrics (stage 7)."""
    
    error_message: Optional[str] = None
    """If FAILED, the reason why."""


class CreateCaptureRequest(BaseModel):
    """Request to create a new capture job."""
    source_system: str = "vantage_spatial_twin"
    source_id: Optional[str] = None
    tier: str = "standard"
    crs: str = "EPSG:4326"


class StartCaptureRequest(BaseModel):
    """Request to start processing an existing capture."""
    tier: Optional[str] = None
    gps_file_ref: Optional[str] = None
    crs: Optional[str] = None
