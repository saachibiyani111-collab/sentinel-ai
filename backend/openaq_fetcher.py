"""
openaq_fetcher.py - Sentinel AI Observed Air-Quality Snapshot

Fetches latest observed particulate-matter measurements from OpenAQ v3
for physical monitoring stations in the Pune urban region.

IMPORTANT DATA BOUNDARY
-----------------------
This module returns raw observed PM2.5 and PM10 concentration snapshots.

It does NOT:
    - calculate CPCB AQI,
    - convert instantaneous concentrations into AQI,
    - assign station measurements to wards,
    - interpolate observations between stations,
    - modify or scale observed values,
    - replace Sentinel AI's modeled AQI context.

The observations are tied to physical monitoring-station coordinates.

The production modeled AQI pipeline remains in live_fetcher.py.
"""

import math
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv


# ---------------------------------------------------------------------------
# ENVIRONMENT
# ---------------------------------------------------------------------------

load_dotenv()

OPENAQ_API_KEY = os.getenv("OPENAQ_API_KEY")


# ---------------------------------------------------------------------------
# OPENAQ CONFIGURATION
# ---------------------------------------------------------------------------

OPENAQ_BASE_URL = "https://api.openaq.org/v3"

PUNE_CENTER_LAT = 18.5204
PUNE_CENTER_LON = 73.8567

# Broad Pune urban-region search.
SEARCH_RADIUS_METERS = 25000

REQUEST_TIMEOUT_SECONDS = 20

# We expose freshness transparently instead of pretending stale data is live.
FRESH_HOURS = 24
RECENT_HOURS = 72

# Only particulate pollutants are included in this snapshot layer.
#
# Gaseous pollutants are intentionally excluded because stations may report
# different units and this endpoint's purpose is a simple, defensible
# observed PM snapshot.
TARGET_POLLUTANTS = {
    "pm25": "PM2.5",
    "pm2.5": "PM2.5",
    "pm10": "PM10",
}


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """
    Parse an ISO timestamp and normalize it to UTC.
    """

    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    except (ValueError, TypeError):
        return None


def _age_hours(value: Optional[str]) -> Optional[float]:
    """
    Calculate measurement age in hours.
    """

    parsed = _parse_datetime(value)

    if parsed is None:
        return None

    age = (
        datetime.now(timezone.utc) - parsed
    ).total_seconds() / 3600

    return max(0.0, age)


def _freshness_label(age: Optional[float]) -> str:
    """
    Classify observation freshness.

    FRESH:
        <= 24 hours

    RECENT:
        > 24 and <= 72 hours

    STALE:
        > 72 hours

    UNKNOWN:
        timestamp unavailable
    """

    if age is None:
        return "unknown"

    if age <= FRESH_HOURS:
        return "fresh"

    if age <= RECENT_HOURS:
        return "recent"

    return "stale"


def _normalize_parameter(
    parameter: Any,
) -> Optional[str]:
    """
    Normalize OpenAQ parameter metadata to PM2.5 or PM10.
    """

    if not parameter:
        return None

    if isinstance(parameter, dict):
        name = (
            parameter.get("name")
            or parameter.get("displayName")
        )
    else:
        name = str(parameter)

    if not name:
        return None

    normalized = (
        name.lower()
        .strip()
        .replace(" ", "")
        .replace("_", "")
    )

    return TARGET_POLLUTANTS.get(normalized)


def _extract_timestamp(
    item: Dict[str, Any],
) -> Optional[str]:
    """
    Extract UTC/local timestamp from an OpenAQ latest measurement.
    """

    datetime_info = item.get("datetime")

    if isinstance(datetime_info, dict):
        return (
            datetime_info.get("utc")
            or datetime_info.get("local")
        )

    if isinstance(datetime_info, str):
        return datetime_info

    return None


def _request_json(
    session: requests.Session,
    path: str,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Perform an authenticated OpenAQ v3 request.
    """

    if not OPENAQ_API_KEY:
        raise RuntimeError(
            "OPENAQ_API_KEY is not configured."
        )

    response = session.get(
        f"{OPENAQ_BASE_URL}{path}",
        headers={
            "X-API-Key": OPENAQ_API_KEY,
            "Accept": "application/json",
        },
        params=params,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )

    response.raise_for_status()

    return response.json()


# ---------------------------------------------------------------------------
# LOCATION DISCOVERY
# ---------------------------------------------------------------------------

def _fetch_locations(
    session: requests.Session,
) -> List[Dict[str, Any]]:
    """
    Fetch OpenAQ monitoring locations around Pune.
    """

    payload = _request_json(
        session,
        "/locations",
        params={
            "coordinates": (
                f"{PUNE_CENTER_LAT},"
                f"{PUNE_CENTER_LON}"
            ),
            "radius": SEARCH_RADIUS_METERS,
            "limit": 100,
        },
    )

    return payload.get("results", [])


# ---------------------------------------------------------------------------
# STATION OBSERVATION FETCHING
# ---------------------------------------------------------------------------

def _fetch_station_snapshot(
    session: requests.Session,
    location: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """
    Fetch latest PM2.5 / PM10 observations for one physical station.

    Sensor metadata is joined to latest measurements using sensor IDs.
    """

    location_id = location.get("id")

    if location_id is None:
        return None

    coordinates = location.get("coordinates") or {}

    latitude = coordinates.get("latitude")
    longitude = coordinates.get("longitude")

    if latitude is None or longitude is None:
        return None


    # ---------------------------------------------------------------------
    # FETCH SENSOR METADATA
    # ---------------------------------------------------------------------

    sensors_payload = _request_json(
        session,
        f"/locations/{location_id}/sensors",
    )

    sensors = sensors_payload.get("results", [])


    # sensor_id -> pollutant metadata

    sensor_lookup: Dict[Any, Dict[str, Any]] = {}

    for sensor in sensors:

        sensor_id = sensor.get("id")

        parameter = sensor.get("parameter")

        pollutant = _normalize_parameter(
            parameter
        )

        if (
            sensor_id is None
            or pollutant is None
        ):
            continue

        unit = None

        if isinstance(parameter, dict):
            unit = (
                parameter.get("units")
                or parameter.get("unit")
            )

        sensor_lookup[sensor_id] = {
            "pollutant": pollutant,
            "unit": unit,
        }


    if not sensor_lookup:
        return None


    # ---------------------------------------------------------------------
    # FETCH LATEST OBSERVATIONS
    # ---------------------------------------------------------------------

    latest_payload = _request_json(
        session,
        f"/locations/{location_id}/latest",
    )

    latest_results = latest_payload.get(
        "results",
        [],
    )


    measurements: Dict[str, Dict[str, Any]] = {}


    for item in latest_results:

        sensor_id = (
            item.get("sensorsId")
            or item.get("sensorId")
        )

        sensor_info = sensor_lookup.get(
            sensor_id
        )

        if not sensor_info:
            continue


        pollutant = sensor_info["pollutant"]

        value = item.get("value")

        if value is None:
            continue


        timestamp = _extract_timestamp(
            item
        )

        age = _age_hours(
            timestamp
        )

        unit = (
            item.get("unit")
            or sensor_info.get("unit")
        )


        candidate = {
            "value": value,
            "unit": unit,
            "timestamp": timestamp,
            "age_hours": (
                round(age, 2)
                if age is not None
                else None
            ),
            "freshness": _freshness_label(
                age
            ),
            "sensor_id": sensor_id,
        }


        # A location may contain more than one sensor for the same pollutant.
        # Keep the freshest measurement rather than arbitrarily selecting one.

        existing = measurements.get(
            pollutant
        )

        if existing is None:
            measurements[pollutant] = candidate
            continue


        existing_age = existing.get(
            "age_hours"
        )


        if (
            age is not None
            and (
                existing_age is None
                or age < existing_age
            )
        ):
            measurements[pollutant] = candidate


    if not measurements:
        return None


    # ---------------------------------------------------------------------
    # STATION-LEVEL FRESHNESS
    # ---------------------------------------------------------------------

    valid_ages = [
        measurement["age_hours"]
        for measurement in measurements.values()
        if measurement.get("age_hours") is not None
    ]


    newest_age = (
        min(valid_ages)
        if valid_ages
        else None
    )


    station_freshness = _freshness_label(
        newest_age
    )


    return {
        "station_id": location_id,
        "station_name": (
            location.get("name")
            or f"OpenAQ Station {location_id}"
        ),
        "lat": latitude,
        "lon": longitude,
        "data_type": "observed_snapshot",
        "provider": "OpenAQ",
        "observed": True,
        "aqi": None,
        "aqi_calculated": False,
        "freshness": station_freshness,
        "newest_measurement_age_hours": newest_age,
        "measurements": measurements,
    }


# ---------------------------------------------------------------------------
# DEDUPLICATION
# ---------------------------------------------------------------------------

def _coordinate_key(
    station: Dict[str, Any],
) -> tuple:
    """
    Build a coordinate key for identifying duplicate physical stations.

    Five decimal places is approximately metre-level precision and is
    sufficient to collapse exact/near-exact duplicate OpenAQ records
    such as legacy and active records for the same monitoring location.
    """

    return (
        round(float(station["lat"]), 5),
        round(float(station["lon"]), 5),
    )


def _station_quality(
    station: Dict[str, Any],
) -> tuple:
    """
    Rank duplicate station records.

    Priority:
        1. Freshness
        2. Number of available PM pollutants
        3. Newest measurement age

    Higher tuple is better.
    """

    freshness_rank = {
        "fresh": 3,
        "recent": 2,
        "stale": 1,
        "unknown": 0,
    }

    freshness_score = freshness_rank.get(
        station.get("freshness"),
        0,
    )

    measurement_count = len(
        station.get("measurements", {})
    )

    age = station.get(
        "newest_measurement_age_hours"
    )

    age_score = (
        -age
        if age is not None
        else float("-inf")
    )

    return (
        freshness_score,
        measurement_count,
        age_score,
    )


def _deduplicate_stations(
    stations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Collapse duplicate OpenAQ location records representing the same
    physical coordinates.

    The best-quality / freshest record is retained.
    """

    best_by_coordinate: Dict[
        tuple,
        Dict[str, Any],
    ] = {}


    for station in stations:

        key = _coordinate_key(
            station
        )

        existing = best_by_coordinate.get(
            key
        )

        if existing is None:
            best_by_coordinate[key] = station
            continue


        if (
            _station_quality(station)
            > _station_quality(existing)
        ):
            best_by_coordinate[key] = station


    return list(
        best_by_coordinate.values()
    )


# ---------------------------------------------------------------------------
# PUBLIC FUNCTION
# ---------------------------------------------------------------------------

def get_pune_observed_snapshots() -> Dict[str, Any]:
    """
    Return latest observed PM snapshots for physical Pune-area
    monitoring stations available through OpenAQ.

    Failure behavior:
        OpenAQ errors are handled gracefully.

        The function returns an unavailable response instead of raising
        an exception that could crash the Sentinel AI API.

    Important:
        This function does not calculate AQI.
    """

    if not OPENAQ_API_KEY:

        return {
            "status": "unavailable",
            "available": False,
            "reason": (
                "OPENAQ_API_KEY is not configured."
            ),
            "stations": [],
        }


    session = requests.Session()


    try:

        locations = _fetch_locations(
            session
        )


        station_snapshots = []


        for location in locations:

            try:

                snapshot = _fetch_station_snapshot(
                    session,
                    location,
                )


                if snapshot is not None:
                    station_snapshots.append(
                        snapshot
                    )


            except (
                requests.RequestException,
                ValueError,
                TypeError,
            ):
                # A single bad station must not
                # break the complete endpoint.
                continue


        station_snapshots = (
            _deduplicate_stations(
                station_snapshots
            )
        )


        # Keep stale observations in the response for transparency,
        # but expose freshness explicitly so the frontend can choose
        # whether to display them.

        station_snapshots.sort(
            key=lambda station: (
                station.get(
                    "newest_measurement_age_hours"
                )
                if station.get(
                    "newest_measurement_age_hours"
                )
                is not None
                else float("inf")
            )
        )


        fresh_count = sum(
            1
            for station in station_snapshots
            if station.get("freshness")
            == "fresh"
        )


        recent_count = sum(
            1
            for station in station_snapshots
            if station.get("freshness")
            == "recent"
        )


        stale_count = sum(
            1
            for station in station_snapshots
            if station.get("freshness")
            == "stale"
        )


        return {
            "status": "ok",
            "available": bool(
                station_snapshots
            ),
            "count": len(
                station_snapshots
            ),
            "fresh_count": fresh_count,
            "recent_count": recent_count,
            "stale_count": stale_count,
            "stations": station_snapshots,
        }


    except (
        requests.RequestException,
        ValueError,
        TypeError,
        RuntimeError,
    ) as exc:

        return {
            "status": "unavailable",
            "available": False,
            "reason": (
                "Observed monitoring-station "
                "data is temporarily unavailable."
            ),
            "error_type": (
                type(exc).__name__
            ),
            "stations": [],
        }


    finally:

        session.close()