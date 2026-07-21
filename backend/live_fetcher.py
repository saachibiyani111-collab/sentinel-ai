"""
live_fetcher.py - Sentinel AI

Provides current modeled air-quality context for selected Pune analysis
locations.

ARCHITECTURE
------------
1. Query Open-Meteo / CAMS Global independently for every configured location.
2. Retrieve trailing hourly modeled pollutant concentrations.
3. Aggregate pollutants into AQI-ready temporal windows.
4. Pass aggregated concentrations to aqi_calculator.py.
5. Calculate an unadjusted base modeled AQI from those aggregated pollutants.
6. When a validated historical composite-AQI spatial factor is available,
   apply it only to the composite base AQI to produce a localized modeled
   AQI estimate. Pollutant concentrations and pollutant sub-indices remain
   unadjusted.

IMPORTANT
---------
Historical spatial factors are applied ONLY at the composite-AQI level.
They are never applied to PM2.5, PM10, NO2, SO2, O3, CO concentrations or
their pollutant sub-indices.

The primary AQI output is a HISTORICALLY ADJUSTED MODELED AQI ESTIMATE when
a historical factor is available; otherwise it is the unadjusted modeled
CPCB-method AQI context.

It is NOT:
- a direct CPCB monitoring-station observation,
- an official CPCB AQI measurement,
- guaranteed hyperlocal ground truth,
- a future AQI forecast.

CAMS Global has coarse spatial resolution. Multiple Pune locations may
therefore resolve to identical model grid cells. Sentinel preserves those
values rather than manufacturing artificial differences.
"""

import math
from datetime import datetime

import requests

from aqi_calculator import calculate_aqi, category

try:
    from ward_bias import get_alpha
except ImportError:
    get_alpha = None


OPEN_METEO_URL = (
    "https://air-quality-api.open-meteo.com/v1/air-quality"
)


# ---------------------------------------------------------------------
# ANALYSIS LOCATIONS
# ---------------------------------------------------------------------

PUNE_WARDS = [
    {
        "name": "Revenue Colony Shivajinagar",
        "lat": 18.5308,
        "lon": 73.8475,
    },
    {
        "name": "Bhosari",
        "lat": 18.6298,
        "lon": 73.8474,
    },
    {
        "name": "Mhada Colony",
        "lat": 18.5000,
        "lon": 73.8200,
    },
    {
        "name": "Savitribai Phule University",
        "lat": 18.547056,
        "lon": 73.826908,
    },
    {
        "name": "Transport Nagar Nigdi",
        "lat": 18.6600,
        "lon": 73.7700,
    },
    {
        "name": "Hadapsar",
        "lat": 18.5089,
        "lon": 73.9260,
    },
    {
        "name": "MIT Kothrud",
        "lat": 18.5074,
        "lon": 73.8077,
    },
    {
        "name": "Katraj Dairy",
        "lat": 18.4483,
        "lon": 73.8600,
    },
]


# ---------------------------------------------------------------------
# OPEN-METEO FIELDS
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# TEMPORAL WINDOWS
# ---------------------------------------------------------------------

AGGREGATION_HOURS = {
    "PM2.5": 24,
    "PM10": 24,
    "NO2": 24,
    "SO2": 24,
    "OZONE": 8,
    "CO": 8,
}

# Request enough history to build the largest aggregation window even when
# the newest CAMS timestep is delayed by a few hours. Freshness is validated
# separately below; extra history is never used to disguise stale data.
MAX_DATA_AGE_HOURS = 3
PAST_HOURS = max(AGGREGATION_HOURS.values()) + MAX_DATA_AGE_HOURS

MIN_COMPLETENESS = 0.75


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def _safe_float(value):
    if value is None:
        return None

    try:
        value = float(value)
    except (TypeError, ValueError):
        return None

    if not math.isfinite(value):
        return None

    if value < 0:
        return None

    return value


def _aggregate_series(values, times, window_hours, anchor_time):
    """
    Aggregate one modeled pollutant over a fixed chronological trailing window.

    The window is anchored to the latest timestamp returned by the provider,
    not to the latest N valid pollutant values. Missing/invalid pollutant values
    therefore reduce completeness instead of causing the calculation to reach
    farther back in time.

    api_timesteps_available counts valid returned API timesteps inside the
    chronological window; these are modeled API values, not independent
    physical sensor observations.
    """

    minimum_timesteps = math.ceil(
        window_hours * MIN_COMPLETENESS
    )

    if (
        not isinstance(values, list)
        or not isinstance(times, list)
        or anchor_time is None
    ):
        return {
            "value": None,
            "api_timesteps_available": 0,
            "api_timesteps_required": minimum_timesteps,
            "window_hours": window_hours,
            "complete_enough": False,
            "window_start": None,
            "window_end": (
                anchor_time.isoformat()
                if anchor_time is not None
                else None
            ),
        }

    timestamped_values = []

    for timestamp, value in zip(times, values):
        try:
            parsed_time = datetime.fromisoformat(timestamp)
        except (TypeError, ValueError):
            continue

        # Never allow a timestamp later than the chosen current-context anchor.
        if parsed_time > anchor_time:
            continue

        timestamped_values.append(
            (parsed_time, _safe_float(value))
        )

    timestamped_values.sort(
        key=lambda item: item[0]
    )

    # Hourly API timestamps are discrete slots. Selecting the last
    # `window_hours` chronological timestamps preserves a true trailing
    # 24-slot/8-slot window. Invalid values remain represented as missing.
    trailing_slots = timestamped_values[-window_hours:]

    valid_values = [
        value
        for _, value in trailing_slots
        if value is not None
    ]

    complete_enough = (
        len(valid_values) >= minimum_timesteps
        and len(trailing_slots) >= minimum_timesteps
    )

    aggregated_value = (
        sum(valid_values) / len(valid_values)
        if complete_enough
        else None
    )

    return {
        "value": (
            round(aggregated_value, 3)
            if aggregated_value is not None
            else None
        ),
        "api_timesteps_available": len(valid_values),
        "api_timesteps_required": minimum_timesteps,
        "window_hours": window_hours,
        "complete_enough": complete_enough,
        "window_start": (
            trailing_slots[0][0].isoformat()
            if trailing_slots
            else None
        ),
        "window_end": (
            anchor_time.isoformat()
            if trailing_slots
            else None
        ),
    }


def _get_historical_factor(location_name):
    """
    Return the historical composite-AQI spatial factor for a location.

    When available, this factor is applied only to the composite base modeled
    AQI to produce the localized modeled AQI estimate. It is never applied to
    pollutant concentrations or pollutant sub-indices.
    """

    if get_alpha is None:
        return None

    try:
        value = get_alpha(location_name)

        if value is None:
            return None

        return float(value)

    except Exception:
        return None


def _empty_location_result(location, error=None):
    """
    Return a consistent response when modeled data cannot be fetched.
    """

    result = {
        "name": location["name"],
        "lat": location["lat"],
        "lon": location["lon"],

        "model_lat": None,
        "model_lon": None,
        "model_elevation": None,

        "aqi": None,
        "base_modeled_aqi": None,
        "category": "Unknown",
        "dominant": None,
        "sub_indices": {},
        "aqi_sufficient_data": False,
        "valid_pollutant_count": 0,

        "pm25": None,
        "pm10": None,
        "no2": None,
        "so2": None,
        "ozone": None,
        "co": None,

        "pollutant_aggregation": {},

        "historical_spatial_factor":
            _get_historical_factor(location["name"]),

        "historical_factor_role":
            "unavailable_for_current_aqi",

        "historical_factor_applied_to_current_aqi":
            False,

        "reading_time": None,
        "aqi_context_time": None,
        "latest_model_time": None,
        "data_age_hours": None,
        "freshness_status": "unavailable",
       "data_fresh": False,
"freshness_threshold_hours": MAX_DATA_AGE_HOURS,

"data_available": False,
"data_usable": False,
"is_current_context": False,
        # Legacy frontend compatibility.
        "is_live": False,

        "value_type":
            "unavailable",

        "observed": False,
        "official_cpcb_aqi": False,

        "source":
            "open_meteo_cams_global",
    }

    if error is not None:
        result["error"] = str(error)

    return result


# ---------------------------------------------------------------------
# LOCATION FETCH
# ---------------------------------------------------------------------

def _fetch_location_aqi(location):
    """
    Fetch and aggregate modeled air-quality data independently for one
    Pune analysis location.
    """

    params = {
        "latitude": location["lat"],
        "longitude": location["lon"],

        "hourly": OM_FIELDS,

        # Retrieve the trailing history needed for the largest AQI window.
        "past_hours": PAST_HOURS,

        # Do not allow future forecast hours into current AQI context.
        "forecast_hours": 0,

        "timezone": "Asia/Kolkata",

        "domains": "cams_global",

        "cell_selection": "nearest",
    }

    try:
        response = requests.get(
            OPEN_METEO_URL,
            params=params,
            timeout=20,
        )

        response.raise_for_status()

        payload = response.json()

        hourly = payload.get("hourly", {})

        times = hourly.get("time", [])

        if not isinstance(times, list) or not times:
            return _empty_location_result(
                location,
                error="No hourly timestamps returned by air-quality provider.",
            )

        parsed_times = []

        for timestamp in times:
            try:
                parsed_times.append(
                    datetime.fromisoformat(timestamp)
                )
            except (TypeError, ValueError):
                continue

        if not parsed_times:
            return _empty_location_result(
                location,
                error="No valid hourly timestamps returned by air-quality provider.",
            )

        latest_model_time = max(parsed_times)

        # The API is requested in Asia/Kolkata local time and returns local
        # timestamps without an offset. Compare against local system time only
        # for an age guard; negative ages are clamped defensively.
        now_local = datetime.now()
        data_age_hours = max(
            0.0,
            (now_local - latest_model_time).total_seconds() / 3600.0,
        )

        data_fresh = (
            data_age_hours <= MAX_DATA_AGE_HOURS
        )

        if not data_fresh:
            result = _empty_location_result(
                location,
                error=(
                    "Latest modeled air-quality timestep is stale "
                    f"({data_age_hours:.2f} hours old; "
                    f"maximum allowed is {MAX_DATA_AGE_HOURS} hours)."
                ),
            )
            result.update({
                "reading_time": latest_model_time.isoformat(),
                "aqi_context_time": latest_model_time.isoformat(),
                "latest_model_time": latest_model_time.isoformat(),
                "data_age_hours": round(data_age_hours, 2),
                "data_fresh": False,
                "freshness_threshold_hours": MAX_DATA_AGE_HOURS,
            })
            return result

        aggregation = {}
        calculator_readings = {}

        for open_meteo_field, internal_key in FIELD_MAP.items():
            values = hourly.get(
                open_meteo_field,
                [],
            )

            window = AGGREGATION_HOURS[
                internal_key
            ]

            result = _aggregate_series(
                values,
                times,
                window,
                latest_model_time,
            )

            raw_aggregated_value = result["value"]

            # Open-Meteo CO concentration is represented in µg/m³.
            # The CPCB AQI calculator expects CO in mg/m³.
            if (
                internal_key == "CO"
                and raw_aggregated_value is not None
            ):
                calculator_value = (
                    raw_aggregated_value / 1000.0
                )
            else:
                calculator_value = raw_aggregated_value

            if calculator_value is not None:
                calculator_readings[
                    internal_key
                ] = calculator_value

            aggregation[internal_key] = {
                **result,

                # Raw temporally aggregated model concentration.
                "raw_value":
                    raw_aggregated_value,

                "raw_unit":
                    "µg/m³",

                # Value actually supplied to aqi_calculator.py.
                "calculator_value":
                    (
                        round(calculator_value, 4)
                        if calculator_value is not None
                        else None
                    ),

                "calculator_unit":
                    (
                        "mg/m³"
                        if internal_key == "CO"
                        else "µg/m³"
                    ),
            }

        aqi_result = calculate_aqi(
            calculator_readings
        )

        historical_factor = (
            _get_historical_factor(
                location["name"]
            )
        )

        # Alpha was derived at the composite-AQI level from paired
        # historical station/city AQI observations. Apply it only to
        # the composite base AQI, never to pollutant concentrations
        # or pollutant sub-indices.
        base_modeled_aqi = aqi_result.get("aqi")

        historical_factor_applied = (
            base_modeled_aqi is not None
            and historical_factor is not None
        )

        if historical_factor_applied:
            localized_aqi = round(
                base_modeled_aqi * historical_factor,
                1,
            )
        else:
            localized_aqi = base_modeled_aqi

        localized_category = (
            category(localized_aqi)
            if localized_aqi is not None
            else "Unknown"
        )

        # The latest provider timestamp anchors every pollutant window.
        # Because stale responses return early above, this timestamp represents
        # accepted recent modeled context.
        aqi_context_time = latest_model_time.isoformat()

        data_available = bool(
            calculator_readings
        ) and data_fresh

        data_usable = bool(
            aqi_result.get("sufficient_data", False)
        ) and data_available

        return {
            # Location
            "name": location["name"],
            "lat": location["lat"],
            "lon": location["lon"],
            # Location
            "name": location["name"],
            "lat": location["lat"],
            "lon": location["lon"],

            # Returned CAMS model grid
            "model_lat":
                payload.get("latitude"),

            "model_lon":
                payload.get("longitude"),

            "model_elevation":
                payload.get("elevation"),

            # Primary frontend AQI: historically informed localized
            # modeled AQI estimate when alpha is available.
            "aqi":
                localized_aqi,

            # Unadjusted AQI from temporally aggregated CAMS pollutants.
            "base_modeled_aqi":
                base_modeled_aqi,

            # Category follows the primary localized AQI.
            "category":
                localized_category,

            # Dominant pollutant remains based on CAMS sub-indices.
            "dominant":
                aqi_result.get("dominant"),

            "sub_indices":
                aqi_result.get(
                    "sub_indices",
                    {},
                ),

            "aqi_sufficient_data":
                aqi_result.get(
                    "sufficient_data",
                    False,
                ),

            "valid_pollutant_count":
                aqi_result.get(
                    "valid_pollutant_count",
                    0,
                ),

            # Aggregated pollutant concentrations.
            #
            # PM/NO2/SO2/O3 are µg/m³.
            # CO is exposed in mg/m³ for compatibility with the
            # CPCB AQI calculator and existing API consumers.
            "pm25":
                aggregation["PM2.5"]["value"],

            "pm10":
                aggregation["PM10"]["value"],

            "no2":
                aggregation["NO2"]["value"],

            "so2":
                aggregation["SO2"]["value"],

            "ozone":
                aggregation["OZONE"]["value"],

            "co":
                aggregation["CO"]["calculator_value"],

            # Full temporal/unit metadata
            "pollutant_aggregation":
                aggregation,

            # Historical composite-AQI spatial factor.
            "historical_spatial_factor":
                historical_factor,

            "historical_factor_role":
                (
                    "applied_to_localized_aqi_estimate"
                    if historical_factor_applied
                    else "unavailable"
                ),

            "historical_factor_applied_to_current_aqi":
                historical_factor_applied,

            # Timestamp compatibility
            "reading_time":
                aqi_context_time,

            "aqi_context_time":
                aqi_context_time,

            "latest_model_time":
                latest_model_time.isoformat(),

            "data_age_hours":
    round(data_age_hours, 2),

"freshness_status":
    "fresh" if data_fresh else "stale",

"data_fresh":
    data_fresh,

"freshness_threshold_hours":
    MAX_DATA_AGE_HOURS,
# Availability and usability semantics
"data_available":
    data_available,

"data_usable":
    data_usable,

"is_current_context":
    data_usable and data_fresh,

            # Legacy frontend compatibility only.
            # This does NOT mean direct sensor observation.
            "is_live":
                False,

            # Provenance
            "value_type":
                (
                    "historically_adjusted_modeled_aqi_estimate"
                    if historical_factor_applied
                    else "modeled_cpcb_method_aqi_context"
                ),

            "observed":
                False,

            "official_cpcb_aqi":
                False,

            "source":
                "open_meteo_cams_global",

            "provenance": {
                "provider":
                    "Open-Meteo",

                "underlying_model":
                    (
                        "CAMS Global Atmospheric "
                        "Composition Forecast"
                    ),

                "data_type":
                    "modeled",

                "observed":
                    False,

                "requested_lat":
                    location["lat"],

                "requested_lon":
                    location["lon"],

                "returned_model_lat":
                    payload.get("latitude"),

                "returned_model_lon":
                    payload.get("longitude"),

                "historical_alpha_applied":
                    historical_factor_applied,
            },

            # Methodology
            "aqi_method": {
                "type":
                    "modeled_cpcb_method_context",

                "official_cpcb_aqi":
                    False,

                "spatial_method":
                    "independent_location_model_query",

                "temporal_method": {
                    "PM2.5":
                        "trailing_24h_mean",

                    "PM10":
                        "trailing_24h_mean",

                    "NO2":
                        "trailing_24h_mean",

                    "SO2":
                        "trailing_24h_mean",

                    "OZONE":
                        "trailing_8h_mean",

                    "CO":
                        "trailing_8h_mean",
                },

                "historical_alpha_applied":
                    historical_factor_applied,

                "freshness": {
                    "latest_model_time":
                        latest_model_time.isoformat(),
                    "data_age_hours":
                        round(data_age_hours, 2),
                    "maximum_age_hours":
                        MAX_DATA_AGE_HOURS,
                    "data_fresh":
                        data_fresh,
                },

                "limitation":
                    (
                        "AQI context is derived from CAMS Global "
                        "modeled concentrations using Indian AQI "
                        "breakpoint methodology. It is not a direct "
                        "CPCB monitoring-station observation and "
                        "must not be presented as official CPCB AQI."
                    ),
            },
        }

    except requests.exceptions.RequestException as exc:
        print(
            f"Warning: modeled air-quality fetch failed "
            f"for {location['name']}: {exc}"
        )

        return _empty_location_result(
            location,
            error=exc,
        )

    except (ValueError, TypeError, KeyError) as exc:
        print(
            f"Warning: invalid air-quality response "
            f"for {location['name']}: {exc}"
        )

        return _empty_location_result(
            location,
            error=exc,
        )


# ---------------------------------------------------------------------
# PUBLIC FUNCTIONS
# ---------------------------------------------------------------------

def get_pune_wards_with_live_aqi():
    """
    Legacy function name retained for API compatibility.

    Returns independently modeled air-quality context for all configured
    Pune analysis locations.
    """

    return [
        _fetch_location_aqi(location)
        for location in PUNE_WARDS
    ]


def get_ward_centers():
    """
    Legacy function retained for frontend/API compatibility.
    """

    return [
        {
            "name": location["name"],
            "lat": location["lat"],
            "lon": location["lon"],
        }
        for location in PUNE_WARDS
    ]


def _grid_signature(location):
    model_lat = location.get(
        "model_lat"
    )

    model_lon = location.get(
        "model_lon"
    )

    if (
        model_lat is None
        or model_lon is None
    ):
        return "unavailable"

    return f"{model_lat},{model_lon}"


# ---------------------------------------------------------------------
# DIAGNOSTIC
# ---------------------------------------------------------------------

if __name__ == "__main__":
    print(
        "SENTINEL AI - MODELED CPCB-METHOD "
        "AIR-QUALITY DIAGNOSTIC\n"
    )

    locations = (
        get_pune_wards_with_live_aqi()
    )

    print(
        f"{'Location':<32} "
        f"{'AQI':>5} "
        f"{'PM2.5':>8} "
        f"{'PM10':>8} "
        f"{'NO2':>8} "
        f"{'O3':>8} "
        f"{'Dominant':<9}"
    )

    print("-" * 95)

    for location in locations:
        def show(value):
            return (
                str(value)
                if value is not None
                else "-"
            )

        print(
            f"{location['name']:<32} "
            f"{show(location['aqi']):>5} "
            f"{show(location['pm25']):>8} "
            f"{show(location['pm10']):>8} "
            f"{show(location['no2']):>8} "
            f"{show(location['ozone']):>8} "
            f"{(location['dominant'] or '-'):<9}"
        )

    print(
        "\nTEMPORAL AGGREGATION DIAGNOSTIC\n"
    )

    for location in locations:
        print(location["name"])

        print(
            f"  AQI context time: "
            f"{location.get('aqi_context_time')}"
        )

        for pollutant, info in (
            location
            .get(
                "pollutant_aggregation",
                {},
            )
            .items()
        ):
            print(
                f"  {pollutant:<7} "
                f"raw={info.get('raw_value')} "
                f"{info.get('raw_unit')} "
                f"calculator={info.get('calculator_value')} "
                f"{info.get('calculator_unit')} "
                f"window={info.get('window_hours')}h "
                f"api_timesteps="
                f"{info.get('api_timesteps_available')}/"
                f"{info.get('window_hours')} "
                f"usable={info.get('complete_enough')}"
            )

        print()

    print(
        "MODEL GRID DIAGNOSTIC\n"
    )

    grid_groups = {}

    for location in locations:
        signature = _grid_signature(
            location
        )

        grid_groups.setdefault(
            signature,
            [],
        ).append(
            location["name"]
        )

    for signature, names in grid_groups.items():
        print(
            f"Returned model coordinate: "
            f"{signature}"
        )

        for name in names:
            print(
                f"  - {name}"
            )

    print(
        "\nIMPORTANT:"
    )

    print(
        "  Each location was queried independently."
    )

    print(
        "  Historical composite-AQI factors are applied "
        "to base modeled AQI when available; pollutants remain unadjusted."
    )

    print(
        "  Pollutants were temporally aggregated "
        "before AQI sub-index calculation."
    )

    print(
        "  CO is converted from modeled µg/m³ "
        "to mg/m³ only for CPCB-method calculation."
    )

    print(
        "  Results are modeled CPCB-method AQI context, "
        "not official CPCB station observations."
    )

    print(
        "  Identical values may occur when locations "
        "resolve to the same coarse CAMS Global grid cell."
    )