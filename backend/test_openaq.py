"""
Sentinel AI - OpenAQ Pune Data Validation

TEST ONLY.
Does not modify production backend.

Goal:
Verify whether OpenAQ provides fresh, real observed Pune station data
that is usable for Sentinel AI.

This script:
1. Finds Pune monitoring locations.
2. Gets sensor metadata for each location.
3. Gets latest measurements.
4. Joins latest measurements to sensors using sensor IDs.
5. Reports actual pollutant, value, unit and timestamp.
6. Does NOT calculate AQI.
7. Does NOT assign stations to wards.
8. Does NOT fabricate missing data.
"""

import os
import requests
from datetime import datetime, timezone

from dotenv import load_dotenv


# ============================================================
# CONFIG
# ============================================================

OPENAQ_BASE = "https://api.openaq.org/v3"

PUNE_LAT = 18.5204
PUNE_LON = 73.8567

SEARCH_RADIUS_METERS = 25000

TIMEOUT = 30

FRESH_HOURS = 24
RECENT_HOURS = 72


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

API_KEY = os.getenv(
    "OPENAQ_API_KEY"
)

if not API_KEY:
    raise RuntimeError(
        "OPENAQ_API_KEY not found in .env"
    )


HEADERS = {
    "X-API-Key": API_KEY,
    "Accept": "application/json",
}


# ============================================================
# HELPERS
# ============================================================

def api_get(
    path,
    params=None,
):
    """
    Perform authenticated OpenAQ request.
    """

    url = (
        f"{OPENAQ_BASE}{path}"
    )

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    return response.json()


def parse_datetime(value):
    """
    Parse ISO timestamp safely.
    """

    if not value:
        return None

    try:

        return datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        ).astimezone(
            timezone.utc
        )

    except (
        ValueError,
        TypeError,
    ):

        return None


def get_age_hours(
    timestamp,
):
    """
    Return age in hours.
    """

    parsed = parse_datetime(
        timestamp
    )

    if parsed is None:
        return None

    now = datetime.now(
        timezone.utc
    )

    delta = (
        now - parsed
    )

    return max(
        0,
        delta.total_seconds()
        / 3600,
    )


def freshness(
    age,
):
    """
    Classify measurement freshness.
    """

    if age is None:
        return "UNKNOWN"

    if age <= FRESH_HOURS:
        return "FRESH"

    if age <= RECENT_HOURS:
        return "RECENT"

    return "STALE"


def normalize_parameter(
    parameter,
):
    """
    Normalize parameter metadata.

    Returns canonical pollutant name
    or None for pollutants not used
    by Sentinel AQI analysis.
    """

    if not parameter:
        return None


    if isinstance(
        parameter,
        dict,
    ):

        name = (
            parameter.get("name")
            or parameter.get(
                "displayName"
            )
        )

    else:

        name = str(
            parameter
        )


    if not name:
        return None


    normalized = (
        name.lower()
        .strip()
        .replace(" ", "")
        .replace("_", "")
    )


    mapping = {

        "pm25":
            "PM2.5",

        "pm2.5":
            "PM2.5",

        "pm10":
            "PM10",

        "no2":
            "NO2",

        "so2":
            "SO2",

        "o3":
            "OZONE",

        "ozone":
            "OZONE",

        "co":
            "CO",
    }


    return mapping.get(
        normalized
    )


# ============================================================
# FETCH LOCATIONS
# ============================================================

print()

print(
    "=" * 90
)

print(
    "SENTINEL AI - OPENAQ "
    "PUNE OBSERVATION VALIDATION"
)

print(
    "=" * 90
)

print()


print(
    "Searching Pune-area "
    "OpenAQ monitoring locations..."
)


locations_payload = api_get(

    "/locations",

    params={

        "coordinates":
            f"{PUNE_LAT},"
            f"{PUNE_LON}",

        "radius":
            SEARCH_RADIUS_METERS,

        "limit":
            100,
    },
)


locations = (
    locations_payload.get(
        "results",
        []
    )
)


print()

print(
    f"Locations returned: "
    f"{len(locations)}"
)

print()


# ============================================================
# PROCESS EACH LOCATION
# ============================================================

reports = []


for index, location in enumerate(
    locations,
    start=1,
):


    location_id = (
        location.get("id")
    )


    location_name = (
        location.get("name")
        or f"Location {location_id}"
    )


    coordinates = (
        location.get(
            "coordinates"
        )
        or {}
    )


    latitude = (
        coordinates.get(
            "latitude"
        )
    )


    longitude = (
        coordinates.get(
            "longitude"
        )
    )


    print(
        f"[{index}/{len(locations)}] "
        f"{location_name}"
    )


    # --------------------------------------------------------
    # SENSOR METADATA
    # --------------------------------------------------------

    try:

        sensors_payload = (
            api_get(
                f"/locations/"
                f"{location_id}"
                f"/sensors"
            )
        )


        sensors = (
            sensors_payload.get(
                "results",
                []
            )
        )


    except requests.RequestException as exc:

        print(
            f"  Sensor request failed: "
            f"{exc}"
        )

        continue


    # --------------------------------------------------------
    # BUILD SENSOR LOOKUP
    # --------------------------------------------------------

    sensor_lookup = {}


    for sensor in sensors:


        sensor_id = (
            sensor.get("id")
        )


        parameter = (
            sensor.get(
                "parameter"
            )
        )


        pollutant = (
            normalize_parameter(
                parameter
            )
        )


        if pollutant is None:
            continue


        unit = None


        if isinstance(
            parameter,
            dict,
        ):

            units = (
                parameter.get(
                    "units"
                )
                or parameter.get(
                    "unit"
                )
            )


            if isinstance(
                units,
                str,
            ):

                unit = units


        sensor_lookup[
            sensor_id
        ] = {

            "pollutant":
                pollutant,

            "unit":
                unit,
        }


    # --------------------------------------------------------
    # LATEST MEASUREMENTS
    # --------------------------------------------------------

    try:

        latest_payload = (
            api_get(
                f"/locations/"
                f"{location_id}"
                f"/latest"
            )
        )


        latest_results = (
            latest_payload.get(
                "results",
                []
            )
        )


    except requests.RequestException as exc:

        print(
            f"  Latest request failed: "
            f"{exc}"
        )

        continue


    # --------------------------------------------------------
    # JOIN LATEST -> SENSOR
    # --------------------------------------------------------

    measurements = {}


    for item in latest_results:


        sensor_id = (

            item.get(
                "sensorsId"
            )

            or item.get(
                "sensorId"
            )
        )


        sensor_info = (
            sensor_lookup.get(
                sensor_id
            )
        )


        if not sensor_info:
            continue


        pollutant = (
            sensor_info[
                "pollutant"
            ]
        )


        value = (
            item.get(
                "value"
            )
        )


        datetime_info = (
            item.get(
                "datetime"
            )
        )


        timestamp = None


        if isinstance(
            datetime_info,
            dict,
        ):

            timestamp = (

                datetime_info.get(
                    "utc"
                )

                or datetime_info.get(
                    "local"
                )
            )


        elif isinstance(
            datetime_info,
            str,
        ):

            timestamp = (
                datetime_info
            )


        age = (
            get_age_hours(
                timestamp
            )
        )


        unit = (

            item.get(
                "unit"
            )

            or sensor_info.get(
                "unit"
            )
        )


        # If duplicate sensors exist for the
        # same pollutant, keep the freshest
        # valid measurement only.

        existing = (
            measurements.get(
                pollutant
            )
        )


        if existing:

            existing_age = (
                existing.get(
                    "age_hours"
                )
            )


            if (
                existing_age is not None
                and age is not None
                and existing_age <= age
            ):

                continue


        measurements[
            pollutant
        ] = {

            "value":
                value,

            "unit":
                unit,

            "timestamp":
                timestamp,

            "age_hours":
                age,

            "freshness":
                freshness(
                    age
                ),

            "sensor_id":
                sensor_id,
        }


    reports.append(
        {

            "id":
                location_id,

            "name":
                location_name,

            "lat":
                latitude,

            "lon":
                longitude,

            "sensor_count":
                len(
                    sensors
                ),

            "target_sensor_count":
                len(
                    sensor_lookup
                ),

            "measurements":
                measurements,
        }
    )


# ============================================================
# PRINT RESULTS
# ============================================================

print()

print(
    "=" * 90
)

print(
    "OBSERVED STATION DATA"
)

print(
    "=" * 90
)


stations_with_data = 0

stations_with_fresh_data = 0

stations_with_pm = 0


for report in reports:


    print()

    print(
        report[
            "name"
        ]
    )


    print(
        f"  OpenAQ ID: "
        f"{report['id']}"
    )


    print(
        f"  Coordinates: "
        f"{report['lat']}, "
        f"{report['lon']}"
    )


    print(
        f"  Sensors returned: "
        f"{report['sensor_count']}"
    )


    print(
        f"  Target pollutant sensors: "
        f"{report['target_sensor_count']}"
    )


    measurements = (
        report[
            "measurements"
        ]
    )


    if not measurements:

        print(
            "  Latest target measurements: "
            "NONE"
        )

        continue


    stations_with_data += 1


    has_fresh = any(

        measurement[
            "freshness"
        ]

        in {
            "FRESH",
            "RECENT",
        }

        for measurement
        in measurements.values()
    )


    if has_fresh:

        stations_with_fresh_data += 1


    if (

        "PM2.5"
        in measurements

        or

        "PM10"
        in measurements

    ):

        stations_with_pm += 1


    for pollutant in [

        "PM2.5",

        "PM10",

        "NO2",

        "SO2",

        "OZONE",

        "CO",

    ]:


        measurement = (
            measurements.get(
                pollutant
            )
        )


        if not measurement:

            print(

                f"  "
                f"{pollutant:<6} "

                f"UNAVAILABLE"

            )

            continue


        age = (
            measurement[
                "age_hours"
            ]
        )


        age_text = (

            f"{age:.2f}h"

            if age is not None

            else "UNKNOWN"

        )


        print(

            f"  "
            f"{pollutant:<6} "

            f"value="
            f"{measurement['value']} "

            f"unit="
            f"{measurement['unit']} "

            f"age="
            f"{age_text} "

            f"["
            f"{measurement['freshness']}"
            f"]"

        )


# ============================================================
# CROSS-STATION DIFFERENTIATION
# ============================================================

print()

print(
    "=" * 90
)

print(
    "CROSS-STATION VALUE CHECK"
)

print(
    "=" * 90
)


for pollutant in [

    "PM2.5",

    "PM10",

    "NO2",

    "OZONE",

]:


    values = []


    for report in reports:


        measurement = (

            report[
                "measurements"
            ].get(
                pollutant
            )

        )


        if not measurement:

            continue


        if (

            measurement[
                "freshness"
            ]

            not in {

                "FRESH",

                "RECENT",

            }

        ):

            continue


        value = (
            measurement.get(
                "value"
            )
        )


        if value is None:

            continue


        values.append(

            (

                report[
                    "name"
                ],

                value,

            )

        )


    unique_values = {

        value

        for _,
        value

        in values

    }


    print()

    print(
        pollutant
    )


    print(

        f"  Fresh/recent stations: "
        f"{len(values)}"

    )


    print(

        f"  Unique values: "
        f"{len(unique_values)}"

    )


    if len(values) >= 2:

        print(

            "  Differentiated: "

            + (

                "YES"

                if len(
                    unique_values
                ) > 1

                else "NO"

            )

        )


    else:

        print(

            "  Differentiated: "
            "INSUFFICIENT DATA"

        )


# ============================================================
# FINAL SUMMARY
# ============================================================

print()

print(
    "=" * 90
)

print(
    "SUMMARY"
)

print(
    "=" * 90
)

print()


print(

    f"Locations discovered: "
    f"{len(locations)}"

)


print(

    f"Locations processed: "
    f"{len(reports)}"

)


print(

    f"Stations with target "
    f"pollutant data: "
    f"{stations_with_data}"

)


print(

    f"Stations with fresh/recent "
    f"target data: "
    f"{stations_with_fresh_data}"

)


print(

    f"Stations with PM2.5 "
    f"or PM10: "
    f"{stations_with_pm}"

)


print()

print(
    "IMPORTANT:"
)


print(

    "This test reports raw observed "
    "station measurements only."

)


print(

    "It does NOT calculate CPCB AQI "
    "from instantaneous latest values."

)


print(

    "It does NOT assign a station's "
    "measurement to an entire ward."

)


print(

    "If the observations are fresh "
    "and useful, the next test must "
    "retrieve the required historical "
    "measurement windows before any "
    "CPCB-method AQI is calculated."

)

print()