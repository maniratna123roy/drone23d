-- Spatial Twin: Seed Data (db/seed.sql)
-- Real-world analogy: A mock architectural scale model placed on the planning table 
-- so engineers can test queries and building edits before the physical survey data arrives.

-- 1. Ensure Default Project Exists
INSERT INTO projects (id, name, scale_factor, frame_transform)
VALUES (1, 'Mill-19 Digital Twin', 1.0, '[]'::jsonb)
ON CONFLICT (id) DO UPDATE SET 
    name = EXCLUDED.name,
    scale_factor = EXCLUDED.scale_factor;

-- 2. Ensure Predefined Geographic Regions
INSERT INTO regions (id, name, boundary)
VALUES 
    ('center', 'Central District', 'POLYGON((-25 -25, 25 -25, 25 25, -25 25, -25 -25))'::geometry),
    ('north',  'Northern Sector',  'POLYGON((-60 25, 60 25, 60 80, -60 80, -60 25))'::geometry),
    ('south',  'Southern Sector',  'POLYGON((-60 -80, 60 -80, 60 -25, -60 -25, -60 -80))'::geometry),
    ('east',   'Eastern Yard',     'POLYGON((25 -25, 80 -25, 80 25, 25 25, 25 -25))'::geometry),
    ('west',   'Western Yard',     'POLYGON((-80 -25, -25 -25, -25 25, -80 25, -80 -25))'::geometry)
ON CONFLICT (id) DO UPDATE SET 
    name = EXCLUDED.name,
    boundary = EXCLUDED.boundary;

-- 3. Clear existing seed data for Project 1 for idempotency
DELETE FROM geometry_history WHERE object_id IN (SELECT id FROM structures WHERE project_id = 1);
DELETE FROM structures WHERE project_id = 1;
DELETE FROM terrain WHERE project_id = 1;
DELETE FROM roads WHERE project_id = 1;
DELETE FROM vegetation WHERE project_id = 1;

-- 4. Insert 10 Seed Structures (aligned with Mill-19 scene coordinates & 3D SFCGAL solids)
-- Building 1: Main Mill Plant A (Center, height 28m)
INSERT INTO structures (project_id, class, footprint, solid, height_m, original_height_m, area_m2, region, splat_bbox, version)
VALUES (
    1,
    'structure',
    'POLYGON((-19 -18, -5 -18, -5 -2, -19 -2, -19 -18))'::geometry,
    ST_Extrude('POLYGON((-19 -18, -5 -18, -5 -2, -19 -2, -19 -18))'::geometry, 0, 0, 28.0),
    28.0,
    28.0,
    224.0,
    'center',
    '{"min": [-19.0, -18.0, 0.0], "max": [-5.0, -2.0, 28.0]}'::jsonb,
    1
);

-- Building 2: Blast Furnace Tower (Center, height 36m)
INSERT INTO structures (project_id, class, footprint, solid, height_m, original_height_m, area_m2, region, splat_bbox, version)
VALUES (
    1,
    'structure',
    'POLYGON((4.5 3.0, 19.5 3.0, 19.5 17.0, 4.5 17.0, 4.5 3.0))'::geometry,
    ST_Extrude('POLYGON((4.5 3.0, 19.5 3.0, 19.5 17.0, 4.5 17.0, 4.5 3.0))'::geometry, 0, 0, 36.0),
    36.0,
    36.0,
    210.0,
    'center',
    '{"min": [4.5, 3.0, 0.0], "max": [19.5, 17.0, 36.0]}'::jsonb,
    1
);

-- Building 3: Rolling Mill B (Center, height 22m)
INSERT INTO structures (project_id, class, footprint, solid, height_m, original_height_m, area_m2, region, splat_bbox, version)
VALUES (
    1,
    'structure',
    'POLYGON((-20.0 6.0, -8.0 6.0, -8.0 18.0, -20.0 18.0, -20.0 6.0))'::geometry,
    ST_Extrude('POLYGON((-20.0 6.0, -8.0 6.0, -8.0 18.0, -20.0 18.0, -20.0 6.0))'::geometry, 0, 0, 22.0),
    22.0,
    22.0,
    144.0,
    'center',
    '{"min": [-20.0, 6.0, 0.0], "max": [-8.0, 18.0, 22.0]}'::jsonb,
    1
);

-- Building 4: Cooling Bed Warehouse (Center, height 18m)
INSERT INTO structures (project_id, class, footprint, solid, height_m, original_height_m, area_m2, region, splat_bbox, version)
VALUES (
    1,
    'structure',
    'POLYGON((9.0 -18.0, 19.0 -18.0, 19.0 -6.0, 9.0 -6.0, 9.0 -18.0))'::geometry,
    ST_Extrude('POLYGON((9.0 -18.0, 19.0 -18.0, 19.0 -6.0, 9.0 -6.0, 9.0 -18.0))'::geometry, 0, 0, 18.0),
    18.0,
    18.0,
    120.0,
    'center',
    '{"min": [9.0, -18.0, 0.0], "max": [19.0, -6.0, 18.0]}'::jsonb,
    1
);

-- Building 5: Northern Smelter (North, height 44m)
INSERT INTO structures (project_id, class, footprint, solid, height_m, original_height_m, area_m2, region, splat_bbox, version)
VALUES (
    1,
    'structure',
    'POLYGON((-11.0 32.0, 11.0 32.0, 11.0 44.0, -11.0 44.0, -11.0 32.0))'::geometry,
    ST_Extrude('POLYGON((-11.0 32.0, 11.0 32.0, 11.0 44.0, -11.0 44.0, -11.0 32.0))'::geometry, 0, 0, 44.0),
    44.0,
    44.0,
    264.0,
    'north',
    '{"min": [-11.0, 32.0, 0.0], "max": [11.0, 44.0, 44.0]}'::jsonb,
    1
);

-- Building 6: Western Assembly Hall (West, height 32m)
INSERT INTO structures (project_id, class, footprint, solid, height_m, original_height_m, area_m2, region, splat_bbox, version)
VALUES (
    1,
    'structure',
    'POLYGON((-45.0 -10.0, -31.0 -10.0, -31.0 10.0, -45.0 10.0, -45.0 -10.0))'::geometry,
    ST_Extrude('POLYGON((-45.0 -10.0, -31.0 -10.0, -31.0 10.0, -45.0 10.0, -45.0 -10.0))'::geometry, 0, 0, 32.0),
    32.0,
    32.0,
    280.0,
    'west',
    '{"min": [-45.0, -10.0, 0.0], "max": [-31.0, 10.0, 32.0]}'::jsonb,
    1
);

-- Building 7: Eastern Machine Shop (East, height 25m)
INSERT INTO structures (project_id, class, footprint, solid, height_m, original_height_m, area_m2, region, splat_bbox, version)
VALUES (
    1,
    'structure',
    'POLYGON((32.0 -9.0, 44.0 -9.0, 44.0 9.0, 32.0 9.0, 32.0 -9.0))'::geometry,
    ST_Extrude('POLYGON((32.0 -9.0, 44.0 -9.0, 44.0 9.0, 32.0 9.0, 32.0 -9.0))'::geometry, 0, 0, 25.0),
    25.0,
    25.0,
    216.0,
    'east',
    '{"min": [32.0, -9.0, 0.0], "max": [44.0, 9.0, 25.0]}'::jsonb,
    1
);

-- Building 8: Southern Storage Unit (South, height 16m)
INSERT INTO structures (project_id, class, footprint, solid, height_m, original_height_m, area_m2, region, splat_bbox, version)
VALUES (
    1,
    'structure',
    'POLYGON((-10.0 -47.0, 10.0 -47.0, 10.0 -33.0, -10.0 -33.0, -10.0 -47.0))'::geometry,
    ST_Extrude('POLYGON((-10.0 -47.0, 10.0 -47.0, 10.0 -33.0, -10.0 -33.0, -10.0 -47.0))'::geometry, 0, 0, 16.0),
    16.0,
    16.0,
    280.0,
    'south',
    '{"min": [-10.0, -47.0, 0.0], "max": [10.0, -33.0, 16.0]}'::jsonb,
    1
);

-- Building 9: Northwest Substation (North, height 15m)
INSERT INTO structures (project_id, class, footprint, solid, height_m, original_height_m, area_m2, region, splat_bbox, version)
VALUES (
    1,
    'structure',
    'POLYGON((-41.0 30.0, -29.0 30.0, -29.0 40.0, -41.0 40.0, -41.0 30.0))'::geometry,
    ST_Extrude('POLYGON((-41.0 30.0, -29.0 30.0, -29.0 40.0, -41.0 40.0, -41.0 30.0))'::geometry, 0, 0, 15.0),
    15.0,
    15.0,
    120.0,
    'north',
    '{"min": [-41.0, 30.0, 0.0], "max": [-29.0, 40.0, 15.0]}'::jsonb,
    1
);

-- Building 10: Northeast High-Bay Silo (North, height 48m)
INSERT INTO structures (project_id, class, footprint, solid, height_m, original_height_m, area_m2, region, splat_bbox, version)
VALUES (
    1,
    'structure',
    'POLYGON((30.0 29.0, 40.0 29.0, 40.0 41.0, 30.0 41.0, 30.0 29.0))'::geometry,
    ST_Extrude('POLYGON((30.0 29.0, 40.0 29.0, 40.0 41.0, 30.0 41.0, 30.0 29.0))'::geometry, 0, 0, 48.0),
    48.0,
    48.0,
    120.0,
    'north',
    '{"min": [30.0, 29.0, 0.0], "max": [40.0, 41.0, 48.0]}'::jsonb,
    1
);

-- 5. Insert Supporting Layers (Terrain, Roads, Vegetation)
-- Terrain base boundary
INSERT INTO terrain (project_id, class, boundary, area_m2)
VALUES (
    1,
    'terrain',
    'POLYGON((-60 -80, 60 -80, 60 80, -60 80, -60 -80))'::geometry,
    19200.0
);

-- Crossing road corridors
INSERT INTO roads (project_id, class, boundary, area_m2)
VALUES 
    (1, 'road', 'POLYGON((-3 -80, 3 -80, 3 80, -3 80, -3 -80))'::geometry, 960.0),
    (1, 'road', 'POLYGON((-60 -3, 60 -3, 60 3, -60 3, -60 -3))'::geometry, 720.0);

-- Perimeter vegetation groves
INSERT INTO vegetation (project_id, class, boundary, area_m2)
VALUES 
    (1, 'vegetation', 'POLYGON((-55 15, -48 15, -48 30, -55 30, -55 15))'::geometry, 105.0),
    (1, 'vegetation', 'POLYGON((48 -30, 56 -30, 56 -15, 48 -15, 48 -30))'::geometry, 120.0),
    (1, 'vegetation', 'POLYGON((-30 -65, 30 -65, 30 -55, -30 -55, -30 -65))'::geometry, 600.0);
