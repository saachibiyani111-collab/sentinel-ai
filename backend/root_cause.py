"""
root_cause.py - Root Cause Engine for Sentinel AI

For a given ward, scores WHY its air quality is what it is by ranking
nearby pollution sources on three transparent factors:
  1. Distance   - closer sources matter more (inverse distance)
  2. Wind       - a source UPWIND of the ward matters more than downwind
  3. Intensity  - a bigger source (major highway) outweighs a small one

Output: a ranked list of sources with a % contribution each, so an officer
sees "this ward's poor air is 55% construction 2km upwind, 30% traffic..."

Fully transparent scoring (no black box) - each factor is explainable.
"""

import math

# Known Pune pollution sources (real places, representative coordinates).
# type + base_intensity (0-10) reflect how much each typically emits.
PUNE_SOURCES = [
    {"name": "Pimpri-Chinchwad Industrial Area", "lat": 18.6280, "lon": 73.8000, "type": "industry",      "intensity": 9},
    {"name": "Bhosari MIDC",                      "lat": 18.6300, "lon": 73.8470, "type": "industry",      "intensity": 8},
    {"name": "Hadapsar Industrial Estate",        "lat": 18.5010, "lon": 73.9400, "type": "industry",      "intensity": 7},
    {"name": "Mumbai-Pune Highway (NH48)",        "lat": 18.5800, "lon": 73.7700, "type": "traffic",       "intensity": 8},
    {"name": "Katraj-Kondhwa Road",               "lat": 18.4500, "lon": 73.8650, "type": "traffic",       "intensity": 6},
    {"name": "Karve Road corridor",               "lat": 18.5050, "lon": 73.8150, "type": "traffic",       "intensity": 7},
    {"name": "Nagar Road construction belt",      "lat": 18.5520, "lon": 73.9100, "type": "construction",  "intensity": 7},
    {"name": "Hinjewadi IT construction",         "lat": 18.5910, "lon": 73.7380, "type": "construction",  "intensity": 6},
    {"name": "Wagholi quarry/dust zone",          "lat": 18.5800, "lon": 73.9800, "type": "dust",          "intensity": 6},
]


def _bearing(lat1, lon1, lat2, lon2):
    """Compass bearing FROM point1 TO point2, in degrees (0=N,90=E)."""
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(math.radians(lat2))
    x = (math.cos(math.radians(lat1)) * math.sin(math.radians(lat2)) -
         math.sin(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.cos(dlon))
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def _distance_km(lat1, lon1, lat2, lon2):
    """Approx distance in km (equirectangular - fine for city scale)."""
    x = (lon2 - lon1) * math.cos(math.radians((lat1 + lat2) / 2))
    y = (lat2 - lat1)
    return math.sqrt(x*x + y*y) * 111.0


def analyze_ward(ward_lat, ward_lon, wind_from_deg):
    """
    ward_lat/lon: the ward's location
    wind_from_deg: direction wind is coming FROM (meteorological convention,
                   e.g. 270 = wind from the west)

    Returns ranked source contributions with % and explanation.
    """
    scored = []
    for src in PUNE_SOURCES:
        d = _distance_km(ward_lat, ward_lon, src["lat"], src["lon"])
        if d < 0.1:
            d = 0.1

        # 1. Distance factor: closer = higher (inverse, capped)
        distance_factor = 1.0 / d

        # 2. Wind factor: is the source UPWIND of the ward?
        # bearing FROM ward TO source:
        brng_to_src = _bearing(ward_lat, ward_lon, src["lat"], src["lon"])
        # source is upwind if it sits in the direction the wind comes FROM.
        # angular difference between "where the source is" and "where wind comes from"
        diff = abs((brng_to_src - wind_from_deg + 180) % 360 - 180)
        # diff=0 -> perfectly upwind (max), diff=180 -> downwind (min)
        wind_factor = max(0.05, math.cos(math.radians(diff)))  # 0.05 floor

        # 3. Intensity factor
        intensity_factor = src["intensity"] / 10.0

        score = distance_factor * wind_factor * intensity_factor
        scored.append({
            "name": src["name"], "type": src["type"],
            "distance_km": round(d, 1),
            "upwind": diff < 90,
            "score": score,
        })

    total = sum(s["score"] for s in scored) or 1
    for s in scored:
        s["contribution_pct"] = round(s["score"] / total * 100)

    ranked = sorted(scored, key=lambda s: s["score"], reverse=True)
    return ranked


if __name__ == "__main__":
    # Test: Shivajinagar ward, wind from the west (270)
    ward = (18.5308, 73.8474)
    wind_from = 270  # from west
    print("Root Cause for Shivajinagar (wind from West):\n")
    ranked = analyze_ward(ward[0], ward[1], wind_from)
    for s in ranked[:5]:
        up = "UPWIND" if s["upwind"] else "downwind"
        print(f"  {s['contribution_pct']:>3}%  {s['name']:<35} ({s['type']}, {s['distance_km']}km, {up})")
