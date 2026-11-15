"""Project settings. Override any value with an environment variable (or a .env file)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# load simple KEY=VALUE pairs from .env if it exists (no extra library needed)
_env = ROOT / ".env"
if _env.exists():
    for line in _env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

DB = {
    "host": os.getenv("PGHOST", "localhost"),
    "port": int(os.getenv("PGPORT", "5432")),
    "user": os.getenv("PGUSER", "postgres"),
    "password": os.getenv("PGPASSWORD", "postgres"),
    "dbname": os.getenv("PGDATABASE", "chaman_webgis"),
}

# ---- study area: Chaman, Balochistan ----------------------------------------------------
STUDY_AREA_NAME = "Chaman, Balochistan"
# bounding box: south, west, north, east (EPSG:4326). The northern edge is kept just above the
# Friendship Gate (30.922 N, 66.445 E) so that places on the Afghan side are not included.
BBOX = (30.84, 66.36, 30.945, 66.56)

CATEGORIES = ["Police station", "Park", "Petrol station"]

DATA_DIR = ROOT / "data"
CSV_PATH = DATA_DIR / "chaman_places.csv"
GEOJSON_PATH = DATA_DIR / "chaman_places.geojson"
SAMPLE_CSV = DATA_DIR / "sample_points.csv"
MANUAL_CSV = DATA_DIR / "manual_points.csv"
SQL_DUMP = ROOT / "database" / "chaman_places_dump.sql"
