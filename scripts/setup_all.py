"""Runs the whole setup in one go:  python scripts/setup_all.py
   1. create database + PostGIS + tables   2. download OSM data   3. load into PostGIS   4. export SQL dump"""
import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
for step in ("create_database.py", "fetch_osm.py", "load_data.py", "export_sql.py"):
    print(f"\n=== {step} ===")
    if subprocess.call([sys.executable, str(here / step)]) != 0:
        sys.exit(f"Stopped: {step} failed (see message above).")
print("\nAll done.  Start the website with:  python api/app.py   then open http://localhost:5000")
