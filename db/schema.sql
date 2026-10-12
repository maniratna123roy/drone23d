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

