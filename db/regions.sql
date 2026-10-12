-- Spatial Twin: Predefined Regions for Mill-19 Scene
-- Coordinate frame: (0,0) is scene center, metric coordinates

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
