"""
Sentinel AI - CPCB India AQI Calculator

Converts raw pollutant concentrations into the official India AQI (0-500)
using CPCB's sub-index method and breakpoint tables (CPCB, 2014).

How it works:
  1. For each pollutant, find which breakpoint band its concentration falls in.
  2. Linearly interpolate a sub-index (0-500) within that band.
  3. The overall AQI = the MAXIMUM sub-index across all pollutants.
     (The pollutant with that max is the "dominant pollutant".)

Rule: overall AQI needs >=3 pollutants, at least one being PM2.5 or PM10.

Units expected (CPCB 24-hour standards):
  PM2.5, PM10, NO2, SO2, NH3, O3 -> ug/m3
  CO -> mg/m3   (NOTE: many feeds give CO in ug/m3; divide by 1000 first)
"""

# CPCB breakpoint tables.
# Each row: (C_low, C_high, I_low, I_high)
# Concentration band -> AQI sub-index band.
BREAKPOINTS = {
    "PM2.5": [
        (0, 30, 0, 50), (31, 60, 51, 100), (61, 90, 101, 200),
        (91, 120, 201, 300), (121, 250, 301, 400), (251, 500, 401, 500),
    ],
    "PM10": [
        (0, 50, 0, 50), (51, 100, 51, 100), (101, 250, 101, 200),
        (251, 350, 201, 300), (351, 430, 301, 400), (431, 600, 401, 500),
    ],
    "NO2": [
        (0, 40, 0, 50), (41, 80, 51, 100), (81, 180, 101, 200),
        (181, 280, 201, 300), (281, 400, 301, 400), (401, 1000, 401, 500),
    ],
    "SO2": [
        (0, 40, 0, 50), (41, 80, 51, 100), (81, 380, 101, 200),
        (381, 800, 201, 300), (801, 1600, 301, 400), (1601, 2000, 401, 500),
    ],
    "CO": [  # CO in mg/m3
        (0, 1.0, 0, 50), (1.1, 2.0, 51, 100), (2.1, 10, 101, 200),
        (10, 17, 201, 300), (17, 34, 301, 400), (34, 50, 401, 500),
    ],
    "OZONE": [  # O3
        (0, 50, 0, 50), (51, 100, 51, 100), (101, 168, 101, 200),
        (169, 208, 201, 300), (209, 748, 301, 400), (749, 1000, 401, 500),
    ],
    "NH3": [
        (0, 200, 0, 50), (201, 400, 51, 100), (401, 800, 101, 200),
        (801, 1200, 201, 300), (1201, 1800, 301, 400), (1801, 2000, 401, 500),
    ],
}

CATEGORIES = [
    (0, 50, "Good"),
    (51, 100, "Satisfactory"),
    (101, 200, "Moderate"),
    (201, 300, "Poor"),
    (301, 400, "Very Poor"),
    (401, 500, "Severe"),
]


def sub_index(pollutant, conc):
    """Calculate the AQI sub-index for one pollutant concentration."""
    if conc is None or pollutant not in BREAKPOINTS:
        return None
    try:
        conc = float(conc)
    except (ValueError, TypeError):
        return None
    if conc < 0:
        return None

    for c_low, c_high, i_low, i_high in BREAKPOINTS[pollutant]:
        if c_low <= conc <= c_high:
            # Linear interpolation: Ip = (IHi-ILo)/(BPHi-BPLo) * (Cp-BPLo) + ILo
            return round(
                (i_high - i_low) / (c_high - c_low) * (conc - c_low) + i_low
            )
    # Above the top breakpoint -> cap at 500
    return 500


def category(aqi):
    """Return the CPCB category name for an AQI value."""
    if aqi is None:
        return "Unknown"
    for low, high, name in CATEGORIES:
        if low <= aqi <= high:
            return name
    return "Severe"


def calculate_aqi(readings):
    """
    readings: dict like {"PM2.5": 211, "PM10": 191, "NO2": 34, "CO": 0.59, ...}
    Returns dict with overall AQI, category, dominant pollutant, and all sub-indices.
    """
    subs = {}
    for pollutant, conc in readings.items():
        si = sub_index(pollutant, conc)
        if si is not None:
            subs[pollutant] = si

    # CPCB rule: need >=3 pollutants, at least one PM
    has_pm = "PM2.5" in subs or "PM10" in subs
    if len(subs) < 3 or not has_pm:
        return {
            "aqi": None,
            "category": "Insufficient data",
            "dominant": None,
            "sub_indices": subs,
        }

    dominant = max(subs, key=subs.get)
    overall = subs[dominant]
    return {
        "aqi": overall,
        "category": category(overall),
        "dominant": dominant,
        "sub_indices": subs,
    }


# ---------- quick self-test ----------
if __name__ == "__main__":
    # Reference check from CPCB docs:
    # PM2.5 = 31 ug/m3 should give sub-index 51; 60 -> 100; 45 -> 75
    assert sub_index("PM2.5", 31) == 51, sub_index("PM2.5", 31)
    assert sub_index("PM2.5", 60) == 100, sub_index("PM2.5", 60)
    assert sub_index("PM2.5", 45) == 75, sub_index("PM2.5", 45)
    print("Reference checks passed (PM2.5: 31->51, 60->100, 45->75)\n")

    # Example using a real row from the Pune 2024 data
    sample = {
        "PM2.5": 211, "PM10": 191, "NO2": 34,
        "CO": 0.59, "SO2": 3, "OZONE": 0, "NH3": 6,
    }
    result = calculate_aqi(sample)
    print("Sample reading:", sample)
    print("-> AQI:", result["aqi"], "(" + result["category"] + ")")
    print("-> Dominant pollutant:", result["dominant"])
    print("-> Sub-indices:", result["sub_indices"])