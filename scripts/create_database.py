"""Step 1 - create the database, enable PostGIS and build the tables."""
from _db import connect
import config

SCHEMA = config.ROOT / "database" / "01_schema.sql"

con = connect("postgres")
con.autocommit = True
cur = con.cursor()
cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (config.DB["dbname"],))
if cur.fetchone():
    print(f"Database '{config.DB['dbname']}' already exists.")
else:
    cur.execute(f'CREATE DATABASE "{config.DB["dbname"]}"')
    print(f"Created database '{config.DB['dbname']}'.")
con.close()

con = connect()
cur = con.cursor()
cur.execute(SCHEMA.read_text(encoding="utf-8"))
con.commit()
cur.execute("SELECT postgis_full_version()")
print("PostGIS enabled:", cur.fetchone()[0].split(" ")[0:2])
print("Tables created: study_area, places (+ view v_places)")
con.close()
