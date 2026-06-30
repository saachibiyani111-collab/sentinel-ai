"""
Sentinel AI - AQI Fetcher / Processor

Reads the historical Pune pollutant data, computes the CPCB AQI for every
hourly row using aqi_calculator, and writes a new CSV with added columns:
    AQI, AQI_Category, Dominant_Pollutant

This is the "calculate then store" step: run this once, and the output CSV
is ready for plotting, the forecast model, or the API to fetch.

Usage (from project root):
    python ml/aqi_fetcher.py
"""

import os
import csv

# Import the calculator that lives in the same ml/ folder
from aqi_calculator import calculate_aqi

# ---------- paths ----------
INPUT_PATH = os.path.join("data", "2024_hourly_data.csv")
OUTPUT_PATH = os.path.join("data", "pune_aqi_computed.csv")

# Columns in the source CSV that are pollutants we can feed the calculator.
# NOTE: CO in this dataset is ug/m3; CPCB expects mg/m3, so we divide by 1000.
POLLUTANT_COLS = ["CO", "NH3", "NO2", "OZONE", "PM10", "PM2.5", "SO2"]


def to_float(value):
    """Safely convert a cell to float, or None if blank/invalid."""
    try:
        v = float(value)
        return v if v >= 0 else None
    except (ValueError, TypeError):
        return None


def main():
    with open(INPUT_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    out_rows = []
    computed = 0
    skipped = 0

    for row in rows:
        # Build the readings dict for the calculator
        readings = {}
        for col in POLLUTANT_COLS:
            val = to_float(row.get(col))
            if val is None:
                continue
            # CO unit fix: dataset is ug/m3 -> convert to mg/m3
            if col == "CO":
                val = val / 1000.0
            readings[col] = val

        result = calculate_aqi(readings)

        # Add the computed fields to the row
        row["AQI"] = result["aqi"] if result["aqi"] is not None else ""
        row["AQI_Category"] = result["category"]
        row["Dominant_Pollutant"] = result["dominant"] or ""

        if result["aqi"] is not None:
            computed += 1
        else:
            skipped += 1

        out_rows.append(row)

    # Write the new CSV with the extra columns
    fieldnames = list(rows[0].keys()) + ["AQI", "AQI_Category", "Dominant_Pollutant"]
    # de-duplicate in case keys already existed
    seen = set()
    fieldnames = [c for c in fieldnames if not (c in seen or seen.add(c))]

    with open(OUTPUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    print("=" * 50)
    print("  SENTINEL AI - AQI FETCHER")
    print("=" * 50)
    print(f"  Input  : {INPUT_PATH}")
    print(f"  Output : {OUTPUT_PATH}")
    print(f"  Total rows       : {len(rows)}")
    print(f"  AQI computed     : {computed}")
    print(f"  Skipped (no AQI) : {skipped}")
    print("=" * 50)

    # Show a few sample computed rows
    print("\n  Sample (first 5 rows with computed AQI):")
    print(f"  {'Date':12} {'Time':10} {'PM2.5':>6} {'AQI':>5}  Category")
    shown = 0
    for r in out_rows:
        if r["AQI"] == "":
            continue
        print(f"  {r['Date']:12} {r['Time']:10} {r['PM2.5']:>6} {str(r['AQI']):>5}  {r['AQI_Category']}")
        shown += 1
        if shown >= 5:
            break


if __name__ == "__main__":
    main()
