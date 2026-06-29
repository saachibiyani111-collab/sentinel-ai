import os
import requests
from fastapi import APIRouter
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

OPENAQ_BASE = "https://api.openaq.org/v3"
API_KEY = os.getenv("OPENAQ_API_KEY", "")
HEADERS = {"X-API-Key": API_KEY}

PUNE_LAT = 18.5204
PUNE_LON = 73.8567

PUNE_WARDS = {
    "Kothrud":     {"lat": 18.5074, "lon": 73.8077},
    "Hadapsar":    {"lat": 18.5089, "lon": 73.9260},
    "Hinjewadi":   {"lat": 18.5912, "lon": 73.7389},
    "Shivajinagar":{"lat": 18.5308, "lon": 73.8470},
    "Kharadi":     {"lat": 18.5515, "lon": 73.9410},
    "Aundh":       {"lat": 18.5590, "lon": 73.8077},
    "Katraj":      {"lat": 18.4480, "lon": 73.8654},
    "Wakad":       {"lat": 18.5985, "lon": 73.7647},
}


@router.get("/api/aqi/pune")
def get_pune_aqi():
    """Fetch live air-quality stations near Pune from OpenAQ v3."""
    try:
        url = f"{OPENAQ_BASE}/locations"
        params = {
            "coordinates": f"{PUNE_LAT},{PUNE_LON}",
            "radius": 25000,
            "limit": 100,
        }
        resp = requests.get(url, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        stations = []
        for loc in data.get("results", []):
            coords = loc.get("coordinates") or {}
            stations.append({
                "id": loc.get("id"),
                "name": loc.get("name"),
                "lat": coords.get("latitude"),
                "lon": coords.get("longitude"),
                "sensors": [s.get("parameter", {}).get("name") for s in loc.get("sensors", [])],
            })

        return {"count": len(stations), "stations": stations}

    except requests.exceptions.RequestException as e:
        return {"error": str(e), "count": 0, "stations": []}


@router.get("/api/aqi/wards")
def get_wards():
    """Return the 8 Pune ward centers."""
    return {"count": len(PUNE_WARDS), "wards": PUNE_WARDS}