"""
live_fetcher.py - Sentinel AI

Fetches current modeled air-quality data for selected Pune analysis locations
using the Open-Meteo Air Quality API.

DATA PROVENANCE
---------------
For Pune, Open-Meteo uses CAMS Global atmospheric-composition model data.
These values are MODEL-DERIVED and are NOT direct ground-monitoring-station
observations.

The underlying CAMS Global product is substantially coarser than ward-scale
geography. Therefore, location values should be interpreted as modeled
air-quality context, not precise ward-level measurements.

AQI NOTE
--------
The current AQI field produced here is a PROVISIONAL CPCB-style index computed
from currently available modeled pollutant concentrations.

It must NOT be described as:
- official CPCB AQI,
- observed station AQI,
- measured ward AQI.

A future methodology upgrade should calculate pollutant-specific averaging
periods and data-completeness requirements before CPCB sub-index calculation.
"""

import requests

from aqi_calculator import calculate_aqi


OPEN_METEO_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


# These are analysis locations used by the Sentinel AI map.
# They are NOT automatically equivalent to official administrative wards
# or CPCB monitoring stations.
PUNE_LOCATIONS = [
    {"name": "Kothrud",      "lat": 18.5074, "lon": 73.8077},
    {"name": "Hadapsar",     "lat": 18.5018, "lon": 73.9260},
    {"name": "Hinjewadi",    "lat": 18.5912, "lon": 73.7389},
    {"name": "Shivajinagar", "lat": 18.5308, "lon": 73.8474},
    {"name": "Kharadi",      "lat": 18.5515, "lon": 73.9355},
    {"name": "Aundh",        "lat": 18.5586, "lon": 73.8080},
    {"name": "Katraj",       "lat": 18.4530, "lon": 73.8567},
    {"name": "Wakad",        "lat": 18.5986, "lon": 73.7615},
]


# NH3 intentionally excluded:
# Open-Meteo documents ammonia availability for Europe only.
OM_FIELDS = (
    "pm2_5,"
    "pm10,"
    "nitrogen_dioxide,"
    "sulphur_dioxide,"
    "ozone,"
    "carbon_monoxide"
)


FIELD_MAP = {
    "pm2_5": "PM2.5",
    "pm10": "PM10",
    "nitrogen_dioxide": "NO2",
    "sulphur_dioxide": "SO2",
    "ozone": "OZONE",
    "carbon_monoxide": "CO",
}


def _safe_round(value, digits=2):
    if value is None:
        return None

    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _fetch_location_air_quality(location):
    """
    Fetch current modeled pollutant concentrations for one Pune analysis point.

    Returns model-derived air-quality context.

    The calculated AQI is explicitly marked provisional because current
    instantaneous modeled concentrations are being supplied to the existing
    CPCB breakpoint calculator without the full pollutant-specific temporal
    averaging methodology.
    """

    params = {
        "latitude": location["lat"],
        "longitude": location["lon"],
        "current": OM_FIELDS,
        "timezone": "Asia/Kolkata",

        # Explicitly use the global CAMS domain for Pune.
        "domains": "cams_global",
    }

    try:
        response = requests.get(
            OPEN_METEO_URL,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        payload = response.json()
        current = payload.get("current", {})

        readings = {}

        for om_field, internal_key in FIELD_MAP.items():
            value = current.get(om_field)

            if value is None:
                continue

            try:
                value = float(value)
            except (TypeError, ValueError):
                continue

            if value < 0:
                continue

            # Open-Meteo provides CO in µg/m³.
            # Existing CPCB calculator expects CO in mg/m³.
            if internal_key == "CO":
                value = value / 1000.0

            readings[internal_key] = value

        # IMPORTANT:
        # This remains provisional until pollutant-specific CPCB averaging
        # periods are implemented upstream.
        result = calculate_aqi(readings)

        aqi_available = result.get("aqi") is not None

        return {
            "name": location["name"],
            "lat": location["lat"],
            "lon": location["lon"],

            # AQI-like decision-support field.
            "aqi": result.get("aqi"),
            "category": result.get("category"),
            "dominant": result.get("dominant"),
            "sub_indices": result.get("sub_indices", {}),

            "pm25": _safe_round(current.get("pm2_5")),
            "pm10": _safe_round(current.get("pm10")),

            "data_available": bool(readings),
            "aqi_available": aqi_available,

            "reading_time": current.get("time"),

            "provenance": {
                "provider": "Open-Meteo",
                "underlying_model": (
                    "CAMS Global Atmospheric Composition Forecast"
                ),
                "data_type": "modeled",
                "observed": False,
            },

            "aqi_method": {
                "type": "provisional_cpcb_style_index",
                "official_cpcb_aqi": False,
                "limitation": (
                    "Calculated from current modeled pollutant concentrations. "
                    "Full CPCB pollutant-specific temporal averaging and "
                    "data-completeness methodology is not yet applied."
                ),
            },

            "spatial_limitation": (
                "Underlying global atmospheric model is coarser than "
                "neighbourhood or ward scale."
            ),
        }

    except requests.exceptions.RequestException as exc:
        print(
            f"Warning: failed to fetch modeled air-quality data for "
            f"{location['name']}: {exc}"
        )

        return {
            "name": location["name"],
            "lat": location["lat"],
            "lon": location["lon"],

            "aqi": None,
            "category": "Unknown",
            "dominant": None,
            "sub_indices": {},

            "pm25": None,
            "pm10": None,

            "data_available": False,
            "aqi_available": False,

            "reading_time": None,

            "provenance": {
                "provider": "Open-Meteo",
                "underlying_model": (
                    "CAMS Global Atmospheric Composition Forecast"
                ),
                "data_type": "modeled",
                "observed": False,
            },

            "aqi_method": {
                "type": "unavailable",
                "official_cpcb_aqi": False,
            },

            "spatial_limitation": (
                "Underlying global atmospheric model is coarser than "
                "neighbourhood or ward scale."
            ),

            "error": "Air-quality model data unavailable.",
        }


def get_pune_wards_with_live_aqi():
    """
    Backward-compatible function name.

    Returns current modeled air-quality context for Pune analysis locations.
    The legacy function name is retained temporarily so existing API imports
    and frontend integration do not break.
    """

    return [
        _fetch_location_air_quality(location)
        for location in PUNE_LOCATIONS
    ]


def get_ward_centers():
    """
    Backward-compatible function name.

    Returns static analysis-location coordinates.
    """

    return [
        {
            "name": location["name"],
            "lat": location["lat"],
            "lon": location["lon"],
        }
        for location in PUNE_LOCATIONS
    ]


if __name__ == "__main__":

    print(
        "SENTINEL AI - CURRENT MODELED AIR-QUALITY CONTEXT\n"
    )

    locations = get_pune_wards_with_live_aqi()

    available = sum(
        1 for location in locations
        if location["data_available"]
    )

    print(
        f"Modeled data available: "
        f"{available}/{len(locations)} locations\n"
    )

    print(
        f"{'Location':<14} "
        f"{'AQI*':>5} "
        f"{'PM2.5':>8} "
        f"{'PM10':>8} "
        f"{'Category':<15} "
        f"{'Dominant':<10} "
        f"Time"
    )

    print("-" * 90)

    for location in locations:

        aqi = (
            location["aqi"]
            if location["aqi"] is not None
            else "-"
        )

        pm25 = (
            location["pm25"]
            if location["pm25"] is not None
            else "-"
        )

        pm10 = (
            location["pm10"]
            if location["pm10"] is not None
            else "-"
        )

        dominant = location["dominant"] or "-"

        print(
            f"{location['name']:<14} "
            f"{str(aqi):>5} "
            f"{str(pm25):>8} "
            f"{str(pm10):>8} "
            f"{location['category']:<15} "
            f"{dominant:<10} "
            f"{location['reading_time'] or '-'}"
        )

    print(
        "\n* AQI is currently a provisional CPCB-style decision-support "
        "index derived from modeled concentrations, not an official "
        "CPCB station observation."
    )