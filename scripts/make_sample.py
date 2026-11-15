"""OPTIONAL - makes a SYNTHETIC test dataset (data/sample_points.csv) so you can try the whole system
before downloading real data.  These points are NOT real places. Never submit them as your dataset."""
import csv
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import config
from fetch_osm import COLUMNS

rng = random.Random(42)
S, W, N, E = config.BBOX
plan = [("Police station", "Police station", 9), ("Police station", "Check post / outpost", 3),
        ("Park", "Park", 5), ("Park", "Garden", 3), ("Petrol station", "Fuel station", 10), ("Petrol station", "CNG station", 2)]
rows, i = [], 0
for cat, sub, n in plan:
    for _ in range(n):
        i += 1
        fuel = cat == "Petrol station"
        rows.append({
            "osm_type": "sample", "osm_id": i, "name": f"SAMPLE {sub} {i:02d}", "category": cat, "subtype": sub,
            "operator": "", "brand": rng.choice(["PSO", "Shell", "Total", "Attock"]) if fuel else "",
            "address": "Synthetic test point", "phone": "", "opening_hours": "24/7" if fuel and i % 2 else "Mo-Su 08:00-20:00",
            "open_24h": "true" if fuel and i % 2 else "false", "fuel_types": "Diesel, Octane 92" if fuel else "",
            "access": "yes" if cat == "Park" else "", "fee": "no" if cat == "Park" else "", "website": "",
            "source": "SAMPLE (synthetic - not real)",
            "lon": round(rng.uniform(W + 0.02, E - 0.02), 6), "lat": round(rng.uniform(S + 0.02, N - 0.02), 6)})
with open(config.SAMPLE_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=COLUMNS)
    w.writeheader()
    w.writerows(rows)
print(f"Wrote {len(rows)} synthetic points to {config.SAMPLE_CSV}")
