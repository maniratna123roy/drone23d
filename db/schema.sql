-- Spatial Twin: Primary Database Schema
-- Run once on Postgres 16 + PostGIS 3.4 + SFCGAL

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_sfcgal;

-- 1. Projects metadata
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    scale_factor REAL DEFAULT 1.0,
    frame_transform JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Geographic / Scene Regions (center, north, south, east, west)
CREATE TABLE IF NOT EXISTS regions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    boundary GEOMETRY(Polygon, 0)
);

-- 3. Structures (buildings, warehouses, industrial units)
CREATE TABLE IF NOT EXISTS structures (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    class TEXT DEFAULT 'structure',
    footprint GEOMETRY(Polygon, 0) NOT NULL,
    solid GEOMETRY(PolyhedralSurfaceZ, 0),
    height_m REAL NOT NULL,
    area_m2 REAL NOT NULL,
    region TEXT,
    splat_bbox JSONB,
    original_height_m REAL,
    version INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Geometry Change History (for Undo / Auditing)
CREATE TABLE IF NOT EXISTS geometry_history (
    id SERIAL PRIMARY KEY,
    object_id INTEGER REFERENCES structures(id) ON DELETE CASCADE,
    session_id TEXT,
    operation TEXT NOT NULL,
    footprint GEOMETRY(Polygon, 0),
    solid GEOMETRY(PolyhedralSurfaceZ, 0),
    height_m REAL,
    version INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Edit Sessions
CREATE TABLE IF NOT EXISTS edit_sessions (
    id TEXT PRIMARY KEY,
    command TEXT,
    intent JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Terrain layer
CREATE TABLE IF NOT EXISTS terrain (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    class TEXT DEFAULT 'terrain',
    boundary GEOMETRY(Polygon, 0) NOT NULL,
    elevation_m REAL,
    area_m2 REAL,
    splat_bbox JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Roads layer
CREATE TABLE IF NOT EXISTS roads (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    class TEXT DEFAULT 'road',
    boundary GEOMETRY(Polygon, 0) NOT NULL,
    length_m REAL,
    width_m REAL,
    area_m2 REAL,
    splat_bbox JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Vegetation layer
CREATE TABLE IF NOT EXISTS vegetation (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
    class TEXT DEFAULT 'vegetation',
    boundary GEOMETRY(Polygon, 0) NOT NULL,
    height_m REAL,
    width_m REAL,
    area_m2 REAL,
    splat_bbox JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Spatial & query performance indexes
CREATE INDEX IF NOT EXISTS idx_structures_footprint ON structures USING GIST (footprint);
CREATE INDEX IF NOT EXISTS idx_structures_solid ON structures USING GIST (solid);
CREATE INDEX IF NOT EXISTS idx_structures_height ON structures (height_m);
CREATE INDEX IF NOT EXISTS idx_regions_boundary ON regions USING GIST (boundary);
CREATE INDEX IF NOT EXISTS idx_geom_history_obj ON geometry_history (object_id, version);
CREATE INDEX IF NOT EXISTS idx_terrain_geom ON terrain USING GIST (boundary);
CREATE INDEX IF NOT EXISTS idx_roads_geom ON roads USING GIST (boundary);
CREATE INDEX IF NOT EXISTS idx_vegetation_geom ON vegetation USING GIST (boundary);



-- ============================================================================
-- VANTAGECAM: Drone Video to 3D Reconstruction Pipeline
-- ============================================================================

-- 9. VantageCam Capture Jobs (root job metadata)
CREATE TABLE IF NOT EXISTS vantagecam_captures (
    id TEXT PRIMARY KEY,                          -- cap_YYYYMMDD_HHMMSS_vantage
    tier TEXT NOT NULL,                           -- 'lite', 'standard', 'premium', 'premium_advanced'
    status TEXT NOT NULL DEFAULT 'CREATED',       -- CREATED, UPLOADING, QUEUED, PROCESSING, RETRYING, COMPLETED, DEGRADED, FAILED
    attempt_count INTEGER DEFAULT 0,              -- current retry attempt (0 to max_attempts)
    max_attempts INTEGER DEFAULT 1,               -- from tier config
    video_path TEXT,                              -- path to uploaded/stored video file
    gps_file_path TEXT,                           -- path to GPS log (optional)
    storage_dir TEXT NOT NULL,                    -- output/vantagecam/captures/{id}
    device TEXT DEFAULT 'cpu',                    -- 'cpu', 'cuda:0', etc.
    error_message TEXT,                           -- last error if status = FAILED
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 10. Pipeline Stages per Capture (stage history + timing)
CREATE TABLE IF NOT EXISTS vantagecam_stages (
    id SERIAL PRIMARY KEY,
    capture_id TEXT NOT NULL REFERENCES vantagecam_captures(id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL,                     -- 'probe', 'frames', 'masking', 'sfm', 'dense', 'mesh', 'splats', 'georef', 'quality_gate', 'export'
    stage_index INTEGER NOT NULL,                 -- 0-9 for ordering
    status TEXT NOT NULL DEFAULT 'PENDING',       -- PENDING, RUNNING, COMPLETED, SKIPPED, FAILED
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    duration_seconds REAL,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,           -- stage-specific data (e.g., frame count for 'frames', point count for 'sfm')
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 11. Artifact References (output files produced by stages)
CREATE TABLE IF NOT EXISTS vantagecam_artifacts (
    id SERIAL PRIMARY KEY,
    capture_id TEXT NOT NULL REFERENCES vantagecam_captures(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,                  -- 'mesh', 'splat', 'orthomosaic', 'dsm', 'point_cloud', 'manifest', 'quality_report'
    file_path TEXT NOT NULL,                      -- relative path in capture storage
    file_size_bytes BIGINT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 12. Quality Reports (per-capture metrics and verdict)
CREATE TABLE IF NOT EXISTS vantagecam_quality_reports (
    id SERIAL PRIMARY KEY,
    capture_id TEXT NOT NULL REFERENCES vantagecam_captures(id) ON DELETE CASCADE,
    registered_frames_ratio REAL,                 -- num registered / num keyframes
    reprojection_error_px REAL,                   -- mean pixel reprojection error from SfM
    sparse_points_count INTEGER,                  -- SfM point count
    dense_points_count INTEGER,                   -- MVS point count
    mesh_triangles_count INTEGER,                 -- Poisson mesh triangle count
    splat_count INTEGER,                          -- Gaussian splats count
    orthomosaic_resolution_cm REAL,               -- cm/pixel
    dsm_resolution_cm REAL,                       -- cm/pixel
    ssim_score REAL,                              -- 0-1 rendering quality
    point_cloud_accuracy_m REAL,                  -- estimated m accuracy
    verdict TEXT,                                 -- PASS, RETRY, DEGRADED, FAIL
    verdict_reason TEXT,                          -- explanation of verdict
    metrics JSONB DEFAULT '{}'::jsonb,            -- all 16 quantitative metrics as JSON
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for VantageCam tables
CREATE INDEX IF NOT EXISTS idx_vc_captures_status ON vantagecam_captures(status);
CREATE INDEX IF NOT EXISTS idx_vc_captures_tier ON vantagecam_captures(tier);
CREATE INDEX IF NOT EXISTS idx_vc_captures_created ON vantagecam_captures(created_at);
CREATE INDEX IF NOT EXISTS idx_vc_stages_capture ON vantagecam_stages(capture_id);
CREATE INDEX IF NOT EXISTS idx_vc_stages_status ON vantagecam_stages(status);
CREATE INDEX IF NOT EXISTS idx_vc_artifacts_capture ON vantagecam_artifacts(capture_id);
CREATE INDEX IF NOT EXISTS idx_vc_artifacts_type ON vantagecam_artifacts(artifact_type);
CREATE INDEX IF NOT EXISTS idx_vc_quality_capture ON vantagecam_quality_reports(capture_id);
