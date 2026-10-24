"""VantageCam ORM Models & Pydantic Schemas.

SQLAlchemy models for database tables + Pydantic schemas for API responses.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, String, Integer, Float, DateTime, Text, BigInteger, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel, Field

Base = declarative_base()


# ============================================================================
# SQLAlchemy ORM Models (Database Layer)
# ============================================================================

class VantageCamCapture(Base):
    """Root job record for a VantageCam capture."""
    __tablename__ = "vantagecam_captures"

    id = Column(String, primary_key=True)                    # cap_YYYYMMDD_HHMMSS_vantage
    tier = Column(String, nullable=False)                    # 'lite', 'standard', 'premium', 'premium_advanced'
    status = Column(String, nullable=False, default="CREATED")  # CREATED, UPLOADING, QUEUED, PROCESSING, RETRYING, COMPLETED, DEGRADED, FAILED
    attempt_count = Column(Integer, default=0)               # current retry attempt
    max_attempts = Column(Integer, default=1)                # from tier config
    video_path = Column(Text)                                # path to uploaded/stored video file
    gps_file_path = Column(Text)                             # path to GPS log (optional)
    storage_dir = Column(Text, nullable=False)               # output/vantagecam/captures/{id}
    device = Column(String, default="cpu")                   # 'cpu', 'cuda:0', etc.
    error_message = Column(Text)                             # last error if status = FAILED
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    stages = relationship("VantageCamStage", back_populates="capture", cascade="all, delete-orphan")
    artifacts = relationship("VantageCamArtifact", back_populates="capture", cascade="all, delete-orphan")
    quality_report = relationship("VantageCamQualityReport", back_populates="capture", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_vc_captures_status", "status"),
        Index("idx_vc_captures_tier", "tier"),
        Index("idx_vc_captures_created", "created_at"),
    )


class VantageCamStage(Base):
    """Pipeline stage execution record per capture."""
    __tablename__ = "vantagecam_stages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    capture_id = Column(String, ForeignKey("vantagecam_captures.id", ondelete="CASCADE"), nullable=False)
    stage_name = Column(String, nullable=False)              # 'probe', 'frames', 'masking', 'sfm', 'dense', 'mesh', 'splats', 'georef', 'quality_gate', 'export'
    stage_index = Column(Integer, nullable=False)            # 0-9 for ordering
    status = Column(String, nullable=False, default="PENDING")  # PENDING, RUNNING, COMPLETED, SKIPPED, FAILED
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    duration_seconds = Column(Float)
    error_message = Column(Text)
    metadata = Column(JSONB, default={})                     # stage-specific data (frame count, point count, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    capture = relationship("VantageCamCapture", back_populates="stages")

    __table_args__ = (
        Index("idx_vc_stages_capture", "capture_id"),
        Index("idx_vc_stages_status", "status"),
    )


class VantageCamArtifact(Base):
    """Output file reference produced by stages."""
    __tablename__ = "vantagecam_artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    capture_id = Column(String, ForeignKey("vantagecam_captures.id", ondelete="CASCADE"), nullable=False)
    artifact_type = Column(String, nullable=False)           # 'mesh', 'splat', 'orthomosaic', 'dsm', 'point_cloud', 'manifest', 'quality_report'
    file_path = Column(Text, nullable=False)                 # relative path in capture storage
    file_size_bytes = Column(BigInteger)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    capture = relationship("VantageCamCapture", back_populates="artifacts")

    __table_args__ = (
        Index("idx_vc_artifacts_capture", "capture_id"),
        Index("idx_vc_artifacts_type", "artifact_type"),
    )


class VantageCamQualityReport(Base):
    """Per-capture quality metrics and verdict."""
    __tablename__ = "vantagecam_quality_reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    capture_id = Column(String, ForeignKey("vantagecam_captures.id", ondelete="CASCADE"), nullable=False)
    registered_frames_ratio = Column(Float)                  # num registered / num keyframes
    reprojection_error_px = Column(Float)                    # mean pixel reprojection error from SfM
    sparse_points_count = Column(Integer)                    # SfM point count
    dense_points_count = Column(Integer)                     # MVS point count
    mesh_triangles_count = Column(Integer)                   # Poisson mesh triangle count
    splat_count = Column(Integer)                            # Gaussian splats count
    orthomosaic_resolution_cm = Column(Float)                # cm/pixel
    dsm_resolution_cm = Column(Float)                        # cm/pixel
    ssim_score = Column(Float)                               # 0-1 rendering quality
    point_cloud_accuracy_m = Column(Float)                   # estimated m accuracy
    verdict = Column(String)                                 # PASS, RETRY, DEGRADED, FAIL
    verdict_reason = Column(Text)                            # explanation of verdict
    metrics = Column(JSONB, default={})                      # all 16 quantitative metrics as JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    capture = relationship("VantageCamCapture", back_populates="quality_report")

    __table_args__ = (
        Index("idx_vc_quality_capture", "capture_id"),
    )


# ============================================================================
# Pydantic Response Schemas (API Layer)
# ============================================================================

class StageResponse(BaseModel):
    """Response schema for a pipeline stage."""
    id: int
    capture_id: str
    stage_name: str
    stage_index: int
    status: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True


class ArtifactResponse(BaseModel):
    """Response schema for an artifact reference."""
    id: int
    capture_id: str
    artifact_type: str
    file_path: str
    file_size_bytes: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


class QualityReportResponse(BaseModel):
    """Response schema for quality metrics and verdict."""
    id: int
    capture_id: str
    registered_frames_ratio: Optional[float] = None
    reprojection_error_px: Optional[float] = None
    sparse_points_count: Optional[int] = None
    dense_points_count: Optional[int] = None
    mesh_triangles_count: Optional[int] = None
    splat_count: Optional[int] = None
    orthomosaic_resolution_cm: Optional[float] = None
    dsm_resolution_cm: Optional[float] = None
    ssim_score: Optional[float] = None
    point_cloud_accuracy_m: Optional[float] = None
    verdict: Optional[str] = None
    verdict_reason: Optional[str] = None
    metrics: Dict[str, Any] = {}
    created_at: datetime

    class Config:
        from_attributes = True


class CaptureResponse(BaseModel):
    """Response schema for a VantageCam capture job."""
    id: str
    tier: str
    status: str
    attempt_count: int
    max_attempts: int
    video_path: Optional[str] = None
    gps_file_path: Optional[str] = None
    storage_dir: str
    device: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    stages: List[StageResponse] = []
    artifacts: List[ArtifactResponse] = []
    quality_report: Optional[QualityReportResponse] = None

    class Config:
        from_attributes = True


class CreateCaptureRequest(BaseModel):
    """Request schema to create a new capture job."""
    tier: str = Field(..., description="Quality tier: 'lite', 'standard', 'premium', 'premium_advanced'")
    device: str = Field(default="cpu", description="Device to use: 'cpu' or 'cuda:0'")


class StartCaptureRequest(BaseModel):
    """Request schema to start pipeline execution."""
    video_path: str = Field(..., description="Path to video file (relative or absolute)")
    gps_file_path: Optional[str] = Field(None, description="Path to GPS log file (optional)")


class CaptureListResponse(BaseModel):
    """Response schema for listing captures."""
    total: int
    captures: List[CaptureResponse]


class CaptureStatusResponse(BaseModel):
    """Response schema for capture status."""
    id: str
    tier: str
    status: str
    attempt_count: int
    max_attempts: int
    error_message: Optional[str] = None
    progress_percent: float = Field(default=0.0, ge=0, le=100)
    stages: List[StageResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
