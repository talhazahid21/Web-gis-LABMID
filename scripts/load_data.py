"""Step 3 - load the CSV into PostGIS as spatial point features.

    python scripts/load_data.py            # loads data/chaman_places.csv  (real OSM data)
    python scripts/load_data.py --sample   # loads synthetic test points (for trying the system only)
"""
import argparse
import csv
from pathlib import Path

from _db import connect
import config

ap = argparse.ArgumentParser()
ap.add_argument("--sample", action="store_true")
ap.add_argument("--csv", help="load another CSV file")
a = ap.parse_args()
path = config.SAMPLE_CSV if a.sample else (a.csv or config.CSV_PATH)
if not Path(path).exists():
    raise SystemExit(f"{path} not found. Run  python scripts/fetch_osm.py  first.")


def nz(v):
    v = (v or "").strip()
    return v or None


with open(path, newline="", encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

con = connect()
cur = con.cursor()
cur.execute("TRUNCATE places RESTART IDENTITY")
cur.execute("TRUNCATE study_area RESTART IDENTITY")
S, W, N, E = config.BBOX
cur.execute("""INSERT INTO study_area (name, description, geom)
               VALUES (%s, %s, ST_MakeEnvelope(%s, %s, %s, %s, 4326))""",
            (config.STUDY_AREA_NAME,
             "Rectangular study extent around Chaman city, Chaman District, Balochistan, Pakistan.", W, S, E, N))
n = 0
for r in rows:
    cur.execute("""
        INSERT INTO places
            (osm_type, osm_id, name, category, subtype, operator, brand, address, phone, opening_hours,
             open_24h, fuel_types, access, fee, website, source, geom)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, ST_SetSRID(ST_MakePoint(%s,%s),4326))""",
                (nz(r.get("osm_type")), int(r["osm_id"]) if (r.get("osm_id") or "").strip().isdigit() else None,
                 r["name"], r["category"], nz(r.get("subtype")), nz(r.get("operator")), nz(r.get("brand")),
                 nz(r.get("address")), nz(r.get("phone")), nz(r.get("opening_hours")),
                 (r.get("open_24h") or "").strip().lower() in ("true", "1", "yes"),
                 nz(r.get("fuel_types")), nz(r.get("access")), nz(r.get("fee")), nz(r.get("website")),
                 r.get("source") or "OpenStreetMap", float(r["lon"]), float(r["lat"])))
    n += 1
con.commit()
cur.execute("SELECT category, count(*) FROM places GROUP BY 1 ORDER BY 1")
print(f"Loaded {n} point features from {path}")
for c, k in cur.fetchall():
    print(f"   {c:<16}{k}")
cur.execute("SELECT ST_AsText(ST_Extent(geom)) FROM places")
print("Extent:", cur.fetchone()[0])
con.close()
