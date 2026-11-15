"""Step 4 - write the submission file  database/chaman_places_dump.sql
(schema + all rows as INSERT statements; runs on any PostgreSQL with PostGIS, no pg_dump needed)."""
from _db import connect
import config

con = connect()
cur = con.cursor()
out = ["-- Chaman Web GIS - database dump", "-- Restore:  psql -U postgres -d chaman_webgis -f chaman_places_dump.sql", ""]
out.append((config.ROOT / "database" / "01_schema.sql").read_text(encoding="utf-8"))
out.append("\n-- ---------------- data ----------------\n")
cur.execute("SELECT name, description, ST_AsText(geom) FROM study_area ORDER BY id")
for name, desc, wkt in cur.fetchall():
    out.append(cur.mogrify("INSERT INTO study_area (name, description, geom) VALUES (%s, %s, ST_GeomFromText(%s, 4326));",
                           (name, desc, wkt)).decode())
out.append("")
cols = ("osm_type, osm_id, name, category, subtype, operator, brand, address, phone, opening_hours, open_24h, "
        "fuel_types, access, fee, website, source")
cur.execute(f"SELECT {cols}, ST_AsText(geom) FROM places ORDER BY id")
n = 0
for row in cur.fetchall():
    *vals, wkt = row
    ph = ", ".join(["%s"] * len(vals))
    out.append(cur.mogrify(f"INSERT INTO places ({cols}, geom) VALUES ({ph}, ST_GeomFromText(%s, 4326));",
                           (*vals, wkt)).decode())
    n += 1
config.SQL_DUMP.write_text("\n".join(out) + "\n", encoding="utf-8")
print(f"Wrote {config.SQL_DUMP}  ({n} places)")
