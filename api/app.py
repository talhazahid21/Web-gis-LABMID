"""REST API for the Chaman Web GIS (police stations, parks, petrol stations).

Run:  python api/app.py        ->  http://localhost:5000   (website)  and  /api/...  (data)

Endpoints (all return JSON / GeoJSON)
    GET /api/health                  service + database check
    GET /api/study-area              study area polygon (GeoJSON Feature)
    GET /api/places                  FeatureCollection; filters: category, q, open24, bbox
    GET /api/places/<id>             one Feature
    GET /api/places/nearest          lat, lng, limit, radius_m, category -> nearest places with distance (m)
    GET /api/stats                   counts by category and subtype + extent
Every query is parameterised (no string-built SQL), so user input cannot inject SQL.
"""
import sys
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from psycopg2 import pool, extras

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

WEB_DIR = config.ROOT / "web"
app = Flask(__name__, static_folder=None)
app.json.ensure_ascii = False

CATEGORIES = config.CATEGORIES
PROPS = ("id, name, category, subtype, operator, brand, address, phone, opening_hours, open_24h, "
         "fuel_types, access, fee, website, source, lon, lat")

_pool = None


def db():
    global _pool
    if _pool is None:
        _pool = pool.ThreadedConnectionPool(1, 8, **config.DB)
    return _pool


def query(sql, params=(), one=False):
    conn = db().getconn()
    try:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            res = cur.fetchone() if one else cur.fetchall()
        conn.rollback()  # read-only: release any transaction
        return res
    finally:
        db().putconn(conn)


@app.after_request
def cors(resp):  # lets the website be hosted on another origin during development
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@app.errorhandler(Exception)
def on_error(e):
    code = getattr(e, "code", 500)
    if code == 500:
        app.logger.exception(e)
        return jsonify(error="Server error"), 500
    return jsonify(error=str(getattr(e, "description", "Error"))), code


def bad(msg):
    return jsonify(error=msg), 400


def parse_categories(raw):
    cats = [c for c in (raw or "").split(",") if c]
    return cats, any(c not in CATEGORIES for c in cats)


def feature_collection(where, params):
    sql = f"""
        SELECT COALESCE(json_agg(json_build_object(
                 'type', 'Feature', 'id', id,
                 'geometry', ST_AsGeoJSON(geom)::json,
                 'properties', to_jsonb(t) - 'geom' - 'lon' - 'lat'
               ) ORDER BY name), '[]'::json) AS features
        FROM (SELECT {PROPS}, geom FROM v_places {where}) t"""
    row = query(sql, params, one=True)
    return {"type": "FeatureCollection", "features": row["features"]}


@app.get("/api/health")
def health():
    row = query("SELECT PostGIS_Version() AS postgis, (SELECT count(*) FROM places) AS places", one=True)
    return jsonify(status="ok", **row)


@app.get("/api/study-area")
def study_area():
    row = query("SELECT name, description, ST_AsGeoJSON(geom)::json AS geometry, "
                "ST_XMin(geom) AS xmin, ST_YMin(geom) AS ymin, ST_XMax(geom) AS xmax, ST_YMax(geom) AS ymax "
                "FROM study_area ORDER BY id LIMIT 1", one=True)
    if not row:
        return jsonify(error="study area not loaded"), 404
    return jsonify(type="Feature", geometry=row["geometry"],
                   properties={"name": row["name"], "description": row["description"],
                               "bbox": [row["xmin"], row["ymin"], row["xmax"], row["ymax"]]})


@app.get("/api/places")
def places():
    where, params = [], []
    cats, invalid = parse_categories(request.args.get("category"))
    if invalid:
        return bad(f"category must be one of {CATEGORIES}")
    if cats:
        where.append("category = ANY(%s)")
        params.append(cats)
    if request.args.get("open24") in ("1", "true"):
        where.append("open_24h")
    q = request.args.get("q", "").strip()
    if q:
        where.append("(name ILIKE %s OR brand ILIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    bbox = request.args.get("bbox")
    if bbox:
        try:
            x1, y1, x2, y2 = (float(v) for v in bbox.split(","))
        except ValueError:
            return bad("bbox must be minLon,minLat,maxLon,maxLat")
        where.append("geom && ST_MakeEnvelope(%s, %s, %s, %s, 4326)")
        params += [x1, y1, x2, y2]
    return jsonify(feature_collection("WHERE " + " AND ".join(where) if where else "", params))


@app.get("/api/places/nearest")
def nearest():
    try:
        lat, lng = float(request.args["lat"]), float(request.args["lng"])
        limit = min(max(int(request.args.get("limit", 5)), 1), 50)
        radius = float(request.args["radius_m"]) if request.args.get("radius_m") else None
    except (KeyError, ValueError):
        return bad("lat and lng are required numbers; limit and radius_m must be numeric")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return bad("lat/lng out of range")
    cats, invalid = parse_categories(request.args.get("category"))
    if invalid:
        return bad(f"category must be one of {CATEGORIES}")
    sql = f"""
        WITH p AS (SELECT ST_SetSRID(ST_MakePoint(%s, %s), 4326) AS g)
        SELECT {PROPS}, ST_Distance(v.geom::geography, p.g::geography) AS distance_m,
               ST_AsGeoJSON(v.geom)::json AS geometry
        FROM v_places v, p
        WHERE (%s::text[] IS NULL OR v.category = ANY(%s))
          AND (%s::float IS NULL OR ST_DWithin(v.geom::geography, p.g::geography, %s))
        ORDER BY v.geom <-> p.g          -- GiST index-assisted nearest-neighbour search
        LIMIT %s"""
    rows = query(sql, (lng, lat, cats or None, cats or None, radius, radius, limit))
    rows.sort(key=lambda r: r["distance_m"])
    feats = [{"type": "Feature", "id": r["id"], "geometry": r.pop("geometry"),
              "properties": {k: v for k, v in r.items() if k not in ("lon", "lat")}} for r in rows]
    return jsonify(type="FeatureCollection", query={"lat": lat, "lng": lng}, features=feats)


@app.get("/api/places/<int:pid>")
def one(pid):
    fc = feature_collection("WHERE id = %s", (pid,))
    if not fc["features"]:
        return jsonify(error="place not found"), 404
    return jsonify(fc["features"][0])


@app.get("/api/stats")
def stats():
    by_cat = query("SELECT category AS label, count(*)::int AS count FROM places GROUP BY 1 ORDER BY 2 DESC")
    by_sub = query("SELECT category, COALESCE(subtype, 'Other') AS label, count(*)::int AS count FROM places "
                   "GROUP BY 1, 2 ORDER BY 1, 3 DESC")
    ext = query("SELECT count(*)::int AS total, count(*) FILTER (WHERE open_24h)::int AS open24, "
                "ST_XMin(ST_Extent(geom)) AS xmin, ST_YMin(ST_Extent(geom)) AS ymin, "
                "ST_XMax(ST_Extent(geom)) AS xmax, ST_YMax(ST_Extent(geom)) AS ymax FROM places", one=True)
    return jsonify(total=ext["total"], open_24h=ext["open24"], by_category=by_cat, by_subtype=by_sub,
                   extent=[ext["xmin"], ext["ymin"], ext["xmax"], ext["ymax"]])


# ---------------------------------------------------------------- website (static files)
@app.get("/")
def index():
    return send_from_directory(WEB_DIR, "index.html")


@app.get("/<path:path>")
def static_files(path):
    return send_from_directory(WEB_DIR, path)


if __name__ == "__main__":
    print("Website + API running at http://localhost:5000   (Ctrl+C to stop)")
    app.run(host="0.0.0.0", port=5000, debug=False)
