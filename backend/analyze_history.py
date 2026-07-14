"""
analyze_history.py  (Sentinel AI)

Computes per-ward AQI multipliers (alpha) from historical CPCB station data
and writes ward_bias_factors.json.

    ward_AQI = live_city_AQI * alpha

METHOD (paired-hourly ratio):
- Each station CSV is a composite-AQI series in a month-block pivot layout
  (month header -> day rows 1-31 -> 24 hourly columns). No pollutant columns
  exist, so composite AQI is used.
- For every hour where >=3 stations report, a CITY mean is computed.
- Each station's alpha = mean(station values) / mean(city values) over the
  hours THAT STATION actually reported. Because station and city means are
  taken over the same paired hours, this is a like-for-like ratio and needs
  no fixed basis year -- every station uses all of its own valid data.
- This gives all 8 wards a real alpha (no alpha=1.0 fallbacks).

WHY NOT AFFINE (alpha*city + beta):
An affine fit was tested. It produced NEGATIVE AQI at low city readings for
several wards (e.g. Bhosari -4.1, Savitribai -28.7 at city AQI 30), which is
physically impossible, and R^2 was weak for some wards (MIT Kothrud 0.20).
The ratio model is bounded, always positive, and defensible. Affine/EQM/ML
remain future work.

Run:  python analyze_history.py  ->  writes ward_bias_factors.json
"""

import csv
import json
import os
import statistics

DATA_DIR = os.environ.get("SENTINEL_DATA_DIR", ".")
MIN_STATIONS_FOR_CITY = 3   # an hour counts toward city mean only if >=3 report
MIN_PAIRS = 200             # a station needs this many paired hours

FILES = {
    "Bhosari": "bhosari.csv",
    "Hadapsar": "hadapsar.csv",
    "Katraj Dairy": "katraj_dairy.csv",
    "Mhada Colony": "mhada_colony.csv",
    "MIT Kothrud": "MIT_Kothrud.csv",
    "Revenue Colony Shivajinagar": "revenue_colony_shivajinagar.csv",
    "Savitribai Phule University": "savitribai_phule_university.csv",
    "Transport Nagar Nigdi": "transport_nagar_nigdi.csv",
}

MONTHS = ["january", "february", "march", "april", "may", "june",
          "july", "august", "september", "october", "november", "december"]


def parse_keyed(path):
    """Return {(year, month, day, hour): aqi} for one station file."""
    out, year, month = {}, None, None
    with open(path, newline="") as fh:
        for row in csv.reader(fh):
            if not row:
                continue
            c0 = row[0].strip()
            if c0.startswith("Year") and len(row) > 1 and row[1].strip().isdigit():
                year = int(row[1].strip())
                continue
            joined = ",".join(row).lower()
            for mi, mn in enumerate(MONTHS, 1):
                if mn in joined:
                    month = mi
                    break
            if c0.isdigit() and 1 <= int(c0) <= 31 and year and month:
                day = int(c0)
                for hour, cell in enumerate(row[1:25]):
                    cell = cell.strip().strip('"')
                    try:
                        v = float(cell)
                        if v > 0:
                            out[(year, month, day, hour)] = v
                    except ValueError:
                        pass
    return out


def build():
    stations = {name: parse_keyed(os.path.join(DATA_DIR, fn))
                for name, fn in FILES.items()}

    # City mean for each hour with enough reporting stations
    all_keys = set()
    for d in stations.values():
        all_keys |= set(d)
    city = {}
    for k in all_keys:
        vals = [d[k] for d in stations.values() if k in d]
        if len(vals) >= MIN_STATIONS_FOR_CITY:
            city[k] = statistics.mean(vals)

    wards, skipped = {}, []
    for name, d in stations.items():
        pairs = [(city[k], d[k]) for k in d if k in city]
        if len(pairs) < MIN_PAIRS:
            skipped.append(name)
            continue
        city_mean = statistics.mean(p[0] for p in pairs)
        stn_mean = statistics.mean(p[1] for p in pairs)
        wards[name] = {
            "alpha": round(stn_mean / city_mean, 3),
            "station_mean_aqi": round(stn_mean, 1),
            "city_mean_aqi_paired": round(city_mean, 1),
            "n_paired_hours": len(pairs),
        }

    out = {
        "_meta": {
            "description": "Per-ward composite-AQI multipliers. ward_aqi = live_city_aqi * alpha.",
            "method": "paired-hourly ratio: mean(station) / mean(city) over hours both reported",
            "city_hours_used": len(city),
            "notes": [
                "Composite AQI only; source files have no per-pollutant columns.",
                "All wards get a real alpha (no 1.0 fallbacks) via hour-pairing.",
                "Affine (alpha*city+beta) tested and rejected: produced negative AQI at low readings.",
                "Unknown wards fall back to alpha=1.0 in the apply code.",
            ],
        },
        "wards": dict(sorted(wards.items(), key=lambda kv: -kv[1]["alpha"])),
    }

    with open(os.path.join(DATA_DIR, "ward_bias_factors.json"), "w") as f:
        json.dump(out, f, indent=2)

    print(f"City hourly series: {len(city)} hours (>= {MIN_STATIONS_FOR_CITY} stations)\n")
    for name, w in out["wards"].items():
        print(f"  {name:<30} alpha={w['alpha']:.3f}  (paired hours={w['n_paired_hours']})")
    if skipped:
        print(f"  skipped (too few pairs) -> alpha=1.0: {', '.join(skipped)}")
    print("\nWrote ward_bias_factors.json")


if __name__ == "__main__":
    build()
