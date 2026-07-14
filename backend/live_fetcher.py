"""
live_fetcher.py - Live ward-level AQI for Pune (Open-Meteo + CPCB calculator + alpha)

THE PROBLEM THIS SOLVES
Open-Meteo serves the global CAMS model on a ~40-45 km grid. All of Pune sits
in one pixel, so calling it separately per ward returns near-identical AQI for
every ward -- a useless map. (Verified: WAQI is stale, Ambee maps 6 wards to
one sensor, Air Matters shows one value across the whole district. No live API
differentiates Pune wards, because only ~12 physical sensors exist.)

THE FIX (two stages)
  1. ONE live city-level fetch from Open-Meteo -> full CPCB AQI via
     aqi_calculator (all 7 pollutants, max-operator, Indian bands).
  2. Per-ward alpha from ward_bias_factors.json -- each ward's long-run
     pollution ratio vs. the city, derived from 4,700-17,700 paired hours of
     real CPCB station history (2017-2023) per ward.

     ward_aqi = live_city_aqi * alpha

WARDS = the 8 official CPCB monitoring-station locations in Pune. These are
the only locations with real historical ground truth, which is what makes the
alpha factors (and therefore the map) defensible.

JSON shape is unchanged from the previous version (name/lat/lon/aqi/category/
dominant/pm25/pm10/is_live/reading_time) plus: alpha, city_aqi, source.
"""

import requests

from aqi_calculator import calculate_aqi
from ward_bias import get_alpha

OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# Pune city-centre reference point for the single live fetch.
PUNE_CENTER = {"lat": 18.5204, "lon": 73.8567}

# The 8 CPCB station wards -- the ones with real historical alpha factors.
PUNE_WARDS = [
    {"name": "Revenue Colony Shivajinagar", "lat": 18.5308, "lon": 73.8475},
    {"name": "Bhosari",                     "lat": 18.6298, "lon": 73.8474},
    {"name": "Mhada Colony",                "lat": 18.5000, "lon": 73.8200},
    {"name": "Savitribai Phule University", "lat": 18.4550, "lon": 73.8250},
    {"name": "Transport Nagar Nigdi",       "lat": 18.6600, "lon": 73.7700},
    {"name": "Hadapsar",                    "lat": 18.5089, "lon": 73.9260},
    {"name": "MIT Kothrud",                 "lat": 18.5074, "lon": 73.8077},
    {"name": "Katraj Dairy",                "lat": 18.4483, "lon": 73.8600},
]

OM_FIELDS = "pm2_5,pm10,nitrogen_dioxide,sulphur_dioxide,ozone,carbon_monoxide,ammonia"
FIELD_MAP = {
    "pm2_5": "PM2.5",
    "pm10": "PM10",
    "nitrogen_dioxide": "NO2",
    "sulphur_dioxide": "SO2",
    "ozone": "OZONE",
    "carbon_monoxide": "CO",
    "ammonia": "NH3",
}


def fetch_city_aqi():
    """
    ONE live Open-Meteo call for Pune centre -> full CPCB AQI.

    Returns dict: {aqi, category, dominant, pm25, pm10, reading_time}
    or None values on failure (callers degrade gracefully).
    """
    params = {
        "latitude": PUNE_CENTER["lat"],
        "longitude": PUNE_CENTER["lon"],
        "current": OM_FIELDS,
        "timezone": "Asia/Kolkata",
    }
    try:
        response = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        response.raise_for_status()
        current = response.json().get("current", {})

        readings = {}
        for om_field, our_key in FIELD_MAP.items():
            val = current.get(om_field)
            if val is None:
                continue
            if our_key == "CO":
                val = val / 1000.0  # ug/m3 -> mg/m3 for CPCB
            readings[our_key] = val

        result = calculate_aqi(readings)
        pm25 = current.get("pm2_5")
        pm10 = current.get("pm10")
        return {
            "aqi": result["aqi"],
            "category": result["category"],
            "dominant": result["dominant"],
            "pm25": round(pm25, 2) if pm25 is not None else None,
            "pm10": round(pm10, 2) if pm10 is not None else None,
            "reading_time": current.get("time"),
        }
    except requests.exceptions.RequestException as e:
        print(f"Warning: city AQI fetch failed: {e}")
        return {
            "aqi": None, "category": "Unknown", "dominant": None,
            "pm25": None, "pm10": None, "reading_time": None,
        }


def _category_for(aqi):
    """Indian CPCB category for a (possibly alpha-scaled) AQI value."""
    if aqi is None:
        return "Unknown"
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Satisfactory"
    if aqi <= 200:
        return "Moderate"
    if aqi <= 300:
        return "Poor"
    if aqi <= 400:
        return "Very Poor"
    return "Severe"


def get_pune_wards_with_live_aqi():
    """
    Live differentiated AQI for all 8 wards.

    One city fetch, then per-ward alpha applied:
        ward_aqi = live_city_aqi * alpha
    """
    city = fetch_city_aqi()
    city_aqi = city["aqi"]

    wards = []
    for w in PUNE_WARDS:
        alpha = get_alpha(w["name"])
        if city_aqi is not None:
            ward_aqi = round(city_aqi * alpha, 1)
            is_live = True
        else:
            ward_aqi = None
            is_live = False

        # Scale the raw pollutant context values by the same alpha so the
        # popup numbers stay mutually consistent with the shown AQI.
        pm25 = round(city["pm25"] * alpha, 2) if city["pm25"] is not None else None
        pm10 = round(city["pm10"] * alpha, 2) if city["pm10"] is not None else None

        wards.append({
            "name": w["name"], "lat": w["lat"], "lon": w["lon"],
            "aqi": ward_aqi,
            "category": _category_for(ward_aqi),
            "dominant": city["dominant"],
            "pm25": pm25,
            "pm10": pm10,
            "is_live": is_live,
            "reading_time": city["reading_time"],
            "alpha": alpha,
            "city_aqi": city_aqi,
            "source": "live_city_x_alpha",
        })
    return wards


def get_ward_centers():
    return [{"name": w["name"], "lat": w["lat"], "lon": w["lon"]} for w in PUNE_WARDS]


if __name__ == "__main__":
    print("Fetching live city AQI (one call) and applying ward alphas...\n")
    wards = get_pune_wards_with_live_aqi()
    live = sum(1 for w in wards if w["is_live"])
    if wards:
        print(f"City AQI: {wards[0]['city_aqi']}   Live: {live}/{len(wards)}\n")
    print(f"{'Ward':<30} {'alpha':>6} {'AQI':>6}  {'Category':<12} {'Dominant':<8}")
    print("-" * 70)
    for w in sorted(wards, key=lambda x: -(x["aqi"] or 0)):
        aqi = w["aqi"] if w["aqi"] is not None else "-"
        print(f"{w['name']:<30} {w['alpha']:>6.3f} {str(aqi):>6}  "
              f"{w['category']:<12} {w['dominant'] or '-':<8}")
