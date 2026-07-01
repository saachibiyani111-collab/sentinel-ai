"""
live_fetcher.py - Live AQI for Pune wards via Open-Meteo

Fetches live air quality for Pune's 8 ward centers from the Open-Meteo
Air Quality API (no key, no card), and computes the FULL CPCB AQI using
aqi_calculator (all 7 pollutants, max-operator method).

Design notes:
- Open-Meteo: no API key, hourly live data (CAMS models), single call/location.
- Per-ward safe fallback: if one ward's call fails, it returns Unknown
  instead of crashing the whole response.
- Uses the complete CPCB calculator (not PM2.5-only), so AQI reflects the
  true dominant pollutant, and Indian color bands are correct.
"""

import requests
from aqi_calculator import calculate_aqi

OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

PUNE_WARDS = [
    {"name": "Kothrud",      "lat": 18.5074, "lon": 73.8077},
    {"name": "Hadapsar",     "lat": 18.5018, "lon": 73.9260},
    {"name": "Hinjewadi",    "lat": 18.5912, "lon": 73.7389},
    {"name": "Shivajinagar", "lat": 18.5308, "lon": 73.8474},
    {"name": "Kharadi",      "lat": 18.5515, "lon": 73.9355},
    {"name": "Aundh",        "lat": 18.5586, "lon": 73.8080},
    {"name": "Katraj",       "lat": 18.4530, "lon": 73.8567},
    {"name": "Wakad",        "lat": 18.5986, "lon": 73.7615},
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


def _fetch_ward_aqi(ward):
    params = {
        "latitude": ward["lat"],
        "longitude": ward["lon"],
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
            "name": ward["name"], "lat": ward["lat"], "lon": ward["lon"],
            "aqi": result["aqi"], "category": result["category"],
            "dominant": result["dominant"],
            "pm25": round(pm25, 2) if pm25 is not None else None,
            "pm10": round(pm10, 2) if pm10 is not None else None,
            "is_live": result["aqi"] is not None,
            "reading_time": current.get("time"),
        }
    except requests.exceptions.RequestException as e:
        print(f"Warning: failed to fetch AQI for {ward['name']}: {e}")
        return {
            "name": ward["name"], "lat": ward["lat"], "lon": ward["lon"],
            "aqi": None, "category": "Unknown", "dominant": None,
            "pm25": None, "pm10": None, "is_live": False, "reading_time": None,
        }


def get_pune_wards_with_live_aqi():
    return [_fetch_ward_aqi(w) for w in PUNE_WARDS]


def get_ward_centers():
    return [{"name": w["name"], "lat": w["lat"], "lon": w["lon"]} for w in PUNE_WARDS]


if __name__ == "__main__":
    print("Fetching live AQI for all 8 Pune wards from Open-Meteo...\n")
    wards = get_pune_wards_with_live_aqi()
    live = sum(1 for w in wards if w["is_live"])
    print(f"Live readings: {live}/{len(wards)}\n")
    print(f"{'Ward':<14} {'AQI':>4} {'PM2.5':>6} {'PM10':>6}  {'Category':<14} {'Dominant':<8} Time")
    print("-" * 78)
    for w in wards:
        aqi = w["aqi"] if w["aqi"] is not None else "-"
        pm25 = w["pm25"] if w["pm25"] is not None else "-"
        pm10 = w["pm10"] if w["pm10"] is not None else "-"
        dom = w["dominant"] or "-"
        print(f"{w['name']:<14} {str(aqi):>4} {str(pm25):>6} {str(pm10):>6}  "
              f"{w['category']:<14} {dom:<8} {w['reading_time'] or '-'}")
