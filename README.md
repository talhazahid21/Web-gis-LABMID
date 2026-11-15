# Chaman Places Atlas – Dynamic Web GIS (PostgreSQL/PostGIS + API + Leaflet)

**Student:** Talha Zahid · FA23-BRG-063 · **Course:** Web GIS Applications (MET418)
**Study area:** Chaman, Balochistan · **Features:** police stations, parks and petrol stations

## What you need
* PostgreSQL 14+ with the **PostGIS** extension (Windows: PostgreSQL installer → *Application Stack Builder* → Spatial Extensions → PostGIS)
* Python 3.9+ and internet (to download the data and the map tiles)

## Run it (5 minutes)
```bash
pip install -r requirements.txt
copy .env.example .env          # Windows  (Mac/Linux: cp)   then put YOUR postgres password in .env
python scripts/setup_all.py     # creates DB + PostGIS, downloads real OSM data, loads it, writes the SQL dump
python api/app.py               # open http://localhost:5000
```
Or step by step: `create_database.py` → `fetch_osm.py` → `load_data.py` → `export_sql.py` (all in `scripts/`).

### Important – the dataset (read this)
`fetch_osm.py` downloads **real** police stations (`amenity=police`), petrol stations (`amenity=fuel`) and parks
(`leisure=park|garden|playground|recreation_ground`) from OpenStreetMap into `data/chaman_places.csv` and
`data/chaman_places.geojson`. Submit these two files + `database/chaman_places_dump.sql`.

* **Minimum 20 points.** Chaman is a small city and OSM coverage there can be thin (police stations and parks especially).
  If the script prints a warning: (1) make the extent bigger with `--bbox S W N E` (edit `BBOX` in `config.py` as well so the
  map extent matches), (2) keep unnamed features (default), and/or (3) add places you verified on Google Maps/satellite
  imagery to `data/manual_points.csv` (copy `data/manual_points_template.csv`). Manual rows are merged automatically.
* **Border check.** Chaman is on the Afghan border. The default extent stops just north of the Friendship Gate, but look at the
  map and delete any point that is across the border, then re-run `load_data.py` and `export_sql.py`.
* Parks and large buildings mapped as polygons are converted to one point (their centre).
* `data/sample_points.csv` (`make_sample.py`, `load_data.py --sample`) is **synthetic test data** – fake names, random
  locations. Use it only to try the system. **Never submit it.**

## Project structure
```
config.py                 settings (DB login, study-area bounding box, categories)
database/01_schema.sql    CREATE EXTENSION postgis + tables + indexes + view
scripts/                  create_database / fetch_osm / load_data / export_sql / setup_all
api/app.py                Flask REST API  ->  GeoJSON from PostGIS
web/                      index.html, css/style.css, js/app.js, vendor/ (Leaflet 1.9.4, bundled)
data/                     CSV + GeoJSON (created by fetch_osm.py)
```

## Database design
| Table | Geometry | Purpose |
|---|---|---|
| `places` | `Point, 4326` | one row per police station / park / petrol station: name, category, subtype, operator, brand, address, phone, opening hours, `open_24h`, fuel types, access, fee, website, source |
| `study_area` | `Polygon, 4326` | study-area extent |
| `v_places` (view) | – | adds `lon`/`lat`, used by the API |

Indexes: **GiST** on `geom` (spatial queries, nearest-neighbour), B-tree on `category`. A CHECK constraint limits `category`
to the three allowed values.

## API (all return JSON/GeoJSON, queries are parameterised)
| Endpoint | Description |
|---|---|
| `GET /api/health` | service and PostGIS check |
| `GET /api/study-area` | study-area polygon |
| `GET /api/places?category=Police station,Park&open24=1&q=pso&bbox=minLon,minLat,maxLon,maxLat` | FeatureCollection with optional filters |
| `GET /api/places/{id}` | one place |
| `GET /api/places/nearest?lat=30.91&lng=66.45&limit=5&radius_m=3000&category=Petrol station` | nearest places with distance in metres (`ST_Distance` on geography, `<->` KNN) |
| `GET /api/stats` | counts by category / subtype, open-24/7 count, extent |

## Website features
Title, study-area information, legend, interactive map (OSM + satellite, scale bar), pop-ups with category-specific attributes
(fuel types and brand for petrol stations, access and fee for parks, operator for police), filter by category / "open 24/7" /
name or brand, clickable list, **nearest police station / park / petrol station** (click the map or use your location), live
counts, shape + colour markers (square = police, circle = park, diamond = petrol), responsive layout.

## Explaining it in the demonstration (likely questions)
* **Why PostGIS?** Real spatial types and indexes; supports `ST_DWithin`, `ST_Distance`, `<->`.
* **Why SRID 4326?** Leaflet and GeoJSON use WGS84 lon/lat; `::geography` gives distances in metres.
* **What does the GiST index do?** Makes bbox and nearest-neighbour queries fast without scanning every row.
* **Flow:** browser → `fetch('/api/places')` → Flask runs SQL → PostGIS → `ST_AsGeoJSON` → Leaflet draws markers.
* **Why parameterised SQL?** `%s` placeholders stop SQL injection (try searching `'; DROP TABLE x;--`).
* **Why polygons become points?** The project needs point features; the centre of a park polygon is stored.

## Troubleshooting
* *password authentication failed* → fix `PGPASSWORD` in `.env`.
* *could not open extension control file postgis.control* → PostGIS is not installed (Stack Builder).
* Map background blank → no internet for tile servers; markers still work.
* Port 5000 busy → change the port on the last line of `api/app.py`.

Data © OpenStreetMap contributors (ODbL).
