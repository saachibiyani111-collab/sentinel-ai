from fastapi import APIRouter
import sys, os

# allow importing from backend/ root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from live_fetcher import get_pune_wards_with_live_aqi, get_ward_centers

router = APIRouter()

@router.get("/api/aqi/pune")
def get_pune_aqi():
    """Live AQI for all 8 Pune wards via Open-Meteo + CPCB calculator."""
    stations = get_pune_wards_with_live_aqi()
    return {"count": len(stations), "stations": stations}

@router.get("/api/aqi/wards")
def get_wards():
    """Static ward centers for map initialization."""
    wards = get_ward_centers()
    return {"count": len(wards), "wards": wards}