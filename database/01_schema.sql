-- =====================================================================
--  Chaman Web GIS (police stations, parks, petrol stations)
--  PostgreSQL + PostGIS schema
-- =====================================================================
CREATE EXTENSION IF NOT EXISTS postgis;

DROP VIEW  IF EXISTS v_places;
DROP TABLE IF EXISTS places;
DROP TABLE IF EXISTS study_area;

-- Study area (one polygon, used for the map extent)
CREATE TABLE study_area (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL,
    description TEXT,
    geom        geometry(Polygon, 4326) NOT NULL
);

-- Point features: one row per police station, park or petrol station
CREATE TABLE places (
    id            SERIAL PRIMARY KEY,
    osm_type      TEXT,                          -- node / way / relation (NULL for manual points)
    osm_id        BIGINT,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL
                  CHECK (category IN ('Police station','Park','Petrol station')),
    subtype       TEXT,                          -- e.g. Check post / Garden / Playground / Fuel station
    operator      TEXT,
    brand         TEXT,                          -- petrol stations: PSO, Shell, Total ...
    address       TEXT,
    phone         TEXT,
    opening_hours TEXT,
    open_24h      BOOLEAN NOT NULL DEFAULT FALSE,
    fuel_types    TEXT,                          -- petrol stations: Diesel, Octane 92, CNG ...
    access        TEXT,                          -- parks: public / private / customers ...
    fee           TEXT,                          -- parks: yes / no
    website       TEXT,
    source        TEXT NOT NULL DEFAULT 'OpenStreetMap',
    geom          geometry(Point, 4326) NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (osm_type, osm_id)
);

-- Indexes: GiST for spatial queries (bbox, distance, nearest neighbour), B-tree for attribute filters
CREATE INDEX idx_places_geom     ON places USING GIST (geom);
CREATE INDEX idx_places_category ON places (category);

-- Read-only view used by the API (adds plain lon/lat columns)
CREATE VIEW v_places AS
SELECT id, name, category, subtype, operator, brand, address, phone, opening_hours, open_24h,
       fuel_types, access, fee, website, source,
       ST_X(geom) AS lon, ST_Y(geom) AS lat, geom
FROM places;
