-- Spatial Twin: Database Extensions Initialization
-- Enables PostGIS spatial geometry and SFCGAL 3D solid operations

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_sfcgal;
