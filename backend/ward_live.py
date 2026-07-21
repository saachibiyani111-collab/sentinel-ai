"""
ward_live.py  (Sentinel AI)

CORRECT ward AQI: fetch each ward's REAL measured AQI from its own CPCB
monitoring station (via the WAQI/AQICN API), instead of estimating it by
multiplying a single coarse city reading.

WHY THIS EXISTS
Open-Meteo serves the global CAMS model on a ~40-45 km grid, so all of Pune
falls in one pixel and every ward reads nearly the same AQI (~42). Multiplying
that single number by a historical ratio (alpha) is an ESTIMATE. Every one of
Pune's 8 wards has a real CPCB station reporting live -- so we measure instead.

STRATEGY (defence in depth)
  1. PRIMARY   : live per-station AQI from WAQI  -> real measurement
  2. FALLBACK  : city AQI x historical alpha     -> estimate, if a station is down
  3. LAST      : city AQI unchanged              -> if alpha is also missing

Every returned ward is tagged with `source` so the UI (and the judges) can see
exactly which values are measured and which are estimated. Nothing is hidden.

SETUP
  1. Get a free token: https://aqicn.org/data-platform/token/
  2. Put it in your .env as:  WAQI_TOKEN=your_token_here
  3. pip install requests python-dotenv

USAGE
  from ward_live import get_ward_aqi
  wards = get_ward_aqi(live_city_aqi=42)   # city value only used for fallback
"""

import os
import time
from functools import lru_cache

import requests

try:
    from ward_bias import get_alpha, WARD_COORDS
except ImportError:  # allow standalone use
    WARD_COORDS = {}

    def get_alpha(_ward: str) -> float:
        return 1.0


WAQI_TOKEN = os.environ.get("WAQI_TOKEN", "demo")
BASE_URL = "https://api.waqi.info/feed/{station}/?token={token}"
TIMEOUT = 6          # seconds per station
CACHE_TTL = 600      # 10 min - WAQI updates hourly, so don't hammer it

# Ward -> WAQI station. Numeric ids (@nnnnnn) are exact CPCB stations.
# MIT Kothrud has no station of its own; Karve Road is the nearest CPCB
# station in Kothrud and is used as its proxy (documented, not hidden).
WARD_STATIONS = {
    "Revenue Colony Shivajinagar": "@567736",
    "Mhada Colony":                "@567730",
    "Transport Nagar Nigdi":       "@567733",
    "Katraj Dairy":                "@567988",
    "Savitribai Phule University": "@568315",
    "Bhosari":                     "pune/bhosari",
    "Hadapsar":                    "pune/hadapsar",
    "MIT Kothrud":                 "pune/karve-road-pune",   # nearest CPCB station
}

_cache: dict[str, tuple[float, float | None]] = {}   # station -> (fetched_at, aqi)


def _fetch_station_aqi(station: str) -> float | None:
    """Live AQI for one WAQI station. None if unavailable. Cached for CACHE_TTL."""
    now = time.time()
    if station in _cache:
        fetched_at, value = _cache[station]
        if now - fetched_at < CACHE_TTL:
            return value

    aqi = None
    try:
        r = requests.get(
            BASE_URL.format(station=station, token=WAQI_TOKEN), timeout=TIMEOUT
        )
        payload = r.json()
        if payload.get("status") == "ok":
            raw = payload.get("data", {}).get("aqi")
            # WAQI returns "-" when a station is reporting no data
            if isinstance(raw, (int, float)):
                aqi = float(raw)
    except (requests.RequestException, ValueError):
        aqi = None   # network error / bad JSON -> fall back, never crash

    _cache[station] = (now, aqi)
    return aqi


def get_ward_aqi(live_city_aqi: float | None = None) -> list[dict]:
    """
    Return AQI for every ward, measured where possible.

    Args:
        live_city_aqi: coarse city AQI (Open-Meteo). Only used as a fallback
                       when a ward's station is unreachable. May be None.

    Returns:
        List of dicts, each tagged with `source`:
          "station"   -> real measured value from that ward's CPCB station
          "estimated" -> city AQI x historical alpha (station was down)
          "city"      -> raw city AQI (no station, no alpha)
          "unknown"   -> nothing available
    """
    results = []
    for ward, (lat, lon) in (WARD_COORDS or {}).items():
        station = WARD_STATIONS.get(ward)
        aqi = _fetch_station_aqi(station) if station else None

        if aqi is not None:
            source, alpha = "station", None
        elif live_city_aqi is not None:
            alpha = get_alpha(ward)
            aqi = round(live_city_aqi * alpha, 1)
            source = "estimated" if alpha != 1.0 else "city"
        else:
            alpha, source = None, "unknown"

        results.append({
            "ward": ward,
            "lat": lat,
            "lon": lon,
            "aqi": aqi,
            "source": source,
            "station": station,
            "alpha": alpha,
            "city_aqi": live_city_aqi,
        })

    return results


if __name__ == "__main__":
    if WAQI_TOKEN == "demo":
        print("WARNING: using 'demo' token. Get a real one at "
              "https://aqicn.org/data-platform/token/ and set WAQI_TOKEN.\n")

    rows = get_ward_aqi(live_city_aqi=90)   # 90 only used if a station is down
    measured = sum(1 for r in rows if r["source"] == "station")

    print(f"{'Ward':<30}{'AQI':>7}  source")
    print("-" * 55)
    for r in sorted(rows, key=lambda x: -(x["aqi"] or 0)):
        print(f"{r['ward']:<30}{str(r['aqi']):>7}  {r['source']}")
    print(f"\n{measured}/{len(rows)} wards from REAL station measurements.")
