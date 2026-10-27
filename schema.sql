CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS incidents (
  id serial PRIMARY KEY, name text NOT NULL, type text NOT NULL, location text,
  geom geography(Point,4326) NOT NULL, people int DEFAULT 0, rain_mm real, rain_src text,
  severity int, impact int, urgency int, vulnerability int, accessibility int);
CREATE TABLE IF NOT EXISTS resources (
  id text PRIMARY KEY, type text NOT NULL, name text, geom geography(Point,4326) NOT NULL,
  incident_id int REFERENCES incidents(id) ON DELETE SET NULL, source text);
CREATE TABLE IF NOT EXISTS allocations (
  id serial PRIMARY KEY, incident_id int, incident text, resource text, type text,
  km real, eta_min int, via text, created_at timestamptz DEFAULT now());
CREATE INDEX IF NOT EXISTS resources_geom_idx ON resources USING GIST (geom);
CREATE INDEX IF NOT EXISTS incidents_geom_idx ON incidents USING GIST (geom);
