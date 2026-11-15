"""Step 2 - download REAL police stations, parks and petrol stations for Chaman from OpenStreetMap.

Uses the free Overpass API (needs internet). Output:
    data/chaman_places.csv      attribute table with lon/lat
    data/chaman_places.geojson  same data as GeoJSON (the 'spatial dataset' to submit)

Options:
    --named-only     skip features that have no name tag (default: keep them as 'Unnamed ...')
    --bbox S W N E   use another extent instead of the one in config.py
Parks, police stations and petrol stations that are mapped as areas (polygons) are converted to one point
(the centre given by Overpass). Extra points you checked yourself (Google Maps / field visit) can go in
data/manual_points.csv - they are merged automatically.
"""
import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config

SERVERS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
COLUMNS = ["osm_type", "osm_id", "name", "category", "subtype", "operator", "brand", "address", "phone",
           "opening_hours", "open_24h", "fuel_types", "access", "fee", "website", "source", "lon", "lat"]
PARK_TYPES = {"park": "Park", "garden": "Garden", "playground": "Playground",
              "recreation_ground": "Recreation ground"}
FUELS = [("fuel:diesel", "Diesel"), ("fuel:octane_91", "Octane 91"), ("fuel:octane_92", "Octane 92"),
         ("fuel:octane_95", "Octane 95"), ("fuel:octane_98", "Octane 98"), ("fuel:lpg", "LPG"),
         ("fuel:cng", "CNG")]


def build_query(bbox):
    s, w, n, e = bbox
    box = f"({s},{w},{n},{e})"
    return f"""[out:json][timeout:90];
(
  nwr["amenity"="police"]{box};
  nwr["amenity"="fuel"]{box};
  nwr["leisure"~"^(park|garden|playground|recreation_ground)$"]{box};
);
out center tags;"""


def run_overpass(query):
    last = None
    for url in SERVERS:
        for _ in range(2):
            try:
                print(f"  querying {url} ...")
                r = requests.post(url, data={"data": query}, timeout=120,
                                  headers={"User-Agent": "chaman-webgis-student-project/1.0"})
                if r.status_code == 200:
                    return r.json()
                last = f"HTTP {r.status_code}"
            except Exception as ex:  # network problems, bad JSON ...
                last = str(ex)
            time.sleep(3)
    sys.exit(f"Overpass request failed ({last}). Check your internet connection and try again.")


def category_of(tags):
    if tags.get("amenity") == "police":
        return "Police station"
    if tags.get("amenity") == "fuel":
        return "Petrol station"
    if tags.get("leisure") in PARK_TYPES:
        return "Park"
    return None


def subtype_of(cat, tags):
    name = tags.get("name", "")
    if cat == "Police station":
        if re.search(r"check ?post|chowki|outpost|out post|levies|fc |frontier", name, re.I):
            return "Check post / outpost"
        return "Police station"
    if cat == "Park":
        return PARK_TYPES[tags["leisure"]]
    if tags.get("fuel:cng") == "yes" and not (tags.get("fuel:diesel") == "yes" or str(tags.get("fuel:octane_92")) == "yes"):
        return "CNG station"
    return "Fuel station"


def fuel_types(tags):
    return ", ".join(label for key, label in FUELS if tags.get(key) == "yes")


def address(tags):
    if tags.get("addr:full"):
        return tags["addr:full"]
    parts = [tags.get(k) for k in ("addr:housenumber", "addr:street", "addr:suburb", "addr:city")]
    return ", ".join(p for p in parts if p)


def parse(elements, named_only):
    rows, dropped = [], 0
    for el in elements:
        t = el.get("tags", {})
        cat = category_of(t)
        lat = el.get("lat", el.get("center", {}).get("lat"))
        lon = el.get("lon", el.get("center", {}).get("lon"))
        if not cat or lat is None or lon is None:
            continue
        sub = subtype_of(cat, t)
        name = t.get("name") or t.get("name:en") or t.get("name:ur") or t.get("int_name")
        if not name:
            if named_only:
                dropped += 1
                continue
            label = t.get("brand") or t.get("operator") or "Unnamed"
            name = f"{label} {sub.lower()}" if label != "Unnamed" else f"Unnamed {sub.lower()}"
        hours = (t.get("opening_hours") or "").strip()
        rows.append({
            "osm_type": el["type"], "osm_id": el["id"], "name": name.strip(), "category": cat, "subtype": sub,
            "operator": t.get("operator", ""), "brand": t.get("brand", ""), "address": address(t),
            "phone": t.get("phone") or t.get("contact:phone") or "", "opening_hours": hours,
            "open_24h": "true" if hours == "24/7" else "false",
            "fuel_types": fuel_types(t) if cat == "Petrol station" else "",
            "access": t.get("access", "") if cat == "Park" else "",
            "fee": t.get("fee", "") if cat == "Park" else "",
            "website": t.get("website") or t.get("contact:website") or "",
            "source": "OpenStreetMap (Overpass API)", "lon": round(lon, 6), "lat": round(lat, 6),
        })
    return rows, dropped


def read_manual():
    if not config.MANUAL_CSV.exists():
        return []
    rows = []
    with open(config.MANUAL_CSV, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not (r.get("name") and r.get("lon") and r.get("lat") and r.get("category") in config.CATEGORIES):
                continue
            row = {c: r.get(c, "") for c in COLUMNS}
            row["source"] = row["source"] or "Manual survey"
            row["open_24h"] = row["open_24h"] or "false"
            rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--named-only", action="store_true")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("S", "W", "N", "E"))
    a = ap.parse_args()
    bbox = tuple(a.bbox) if a.bbox else config.BBOX

    print(f"Downloading police stations, parks and petrol stations for {config.STUDY_AREA_NAME}, bbox={bbox}")
    data = run_overpass(build_query(bbox))
    rows, dropped = parse(data["elements"], a.named_only)
    manual = read_manual()
    seen = {(r["osm_type"], str(r["osm_id"])) for r in rows}
    rows += [m for m in manual if not m["osm_id"] or (m["osm_type"], str(m["osm_id"])) not in seen]
    rows.sort(key=lambda r: (r["category"], r["name"]))

    config.DATA_DIR.mkdir(exist_ok=True)
    with open(config.CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)
    gj = {"type": "FeatureCollection", "name": "chaman_places",
          "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
          "features": [{"type": "Feature",
                        "properties": {k: v for k, v in r.items() if k not in ("lon", "lat")},
                        "geometry": {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]}}
                       for r in rows]}
    config.GEOJSON_PATH.write_text(json.dumps(gj, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\nSaved {len(rows)} places  ({len(manual)} manual, {dropped} unnamed skipped)")
    for c in config.CATEGORIES:
        print(f"   {c:<16}{sum(r['category'] == c for r in rows)}")
    print(f"Files: {config.CSV_PATH.name}, {config.GEOJSON_PATH.name}")
    if len(rows) < 20:
        print("\nWARNING: fewer than 20 points (the project minimum). Try a larger --bbox, remove --named-only, "
              "or add facilities you verified to data/manual_points.csv.")
    print("\nCHECK: open the map and delete any point that lies across the Afghan border.")


if __name__ == "__main__":
    main()
