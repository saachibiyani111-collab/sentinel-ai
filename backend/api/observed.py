"""
api/observed.py - Sentinel AI Observed Air Quality API

Separate observed monitoring-station layer.

This router does not modify Sentinel AI's existing modeled AQI pipeline.

The endpoint exposes recent raw PM2.5 and PM10 concentration snapshots
from physical monitoring stations available through OpenAQ.

IMPORTANT:
    - No AQI is calculated from instantaneous/latest observations.
    - Measurements remain tied to actual station coordinates.
    - Measurements are not assigned to wards.
    - Each pollutant is independently checked for freshness upstream.
    - Observations outside the configured current-snapshot window
      are excluded upstream by openaq_fetcher.py.
"""

from fastapi import APIRouter

from openaq_fetcher import (
    get_pune_observed_snapshots,
)


# ---------------------------------------------------------------------------
# ROUTER
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/aqi",
    tags=["Air Quality - Observed"],
)


# ---------------------------------------------------------------------------
# OBSERVED SNAPSHOT ENDPOINT
# ---------------------------------------------------------------------------

@router.get("/observed")
def get_observed_air_quality():
    """
    Return recent observed PM2.5 and PM10 concentration snapshots
    from physical Pune-area monitoring stations.

    These are raw pollutant concentrations.

    They are NOT calculated CPCB AQI values.

    A station is returned only if at least one eligible PM2.5 or PM10
    observation remains after per-pollutant freshness filtering.
    """

    result = (
        get_pune_observed_snapshots()
    )


    stations = result.get(
        "stations",
        [],
    )


    return {
        "status":
            result.get(
                "status",
                "unavailable",
            ),

        "available":
            result.get(
                "available",
                False,
            ),

        "count":
            len(
                stations
            ),

        "data_source": {
            "provider":
                "OpenAQ",

            "data_type":
                "observed_snapshot",

            "observed":
                True,

            "aqi_calculated":
                False,

            "official_cpcb_aqi":
                False,
        },

        "measurement_scope":
            "physical_monitoring_station",

        "freshness_policy": {
            "maximum_measurement_age_hours":
                result.get(
                    "max_observation_age_hours",
                    24,
                ),

            "applied_per_pollutant":
                True,

            "policy_type": (
                "Sentinel AI current-snapshot "
                "display policy"
            ),
        },

        "interpretation": (
            "Recent raw PM2.5 and PM10 concentration observations "
            "from physical monitoring stations available through "
            "OpenAQ. Measurements remain tied to their actual station "
            "coordinates. Each pollutant is independently checked for "
            "freshness. These latest observations are not directly "
            "converted into CPCB AQI and should not be interpreted "
            "as ward-wide measurements."
        ),

        "stations":
            stations,

        "reason":
            result.get(
                "reason"
            ),
    }