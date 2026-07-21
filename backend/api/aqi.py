"""
api/aqi.py - Sentinel AI Modeled Air Quality API

Exposes modeled air-quality context for Sentinel AI's configured
Pune ward/locality analysis points.

This router is separate from the observed OpenAQ monitoring-station
layer exposed through api/observed.py.

Important data boundary:

    Current air-quality values returned here come from Sentinel AI's
    existing live_fetcher.py modeled-data pipeline.

    These values must not be interpreted as:
        - direct CPCB monitoring-station observations,
        - official CPCB AQI observations,
        - or precise measurements representing an entire ward.

    Configured locations are representative ward/locality analysis
    points used for ward-focused decision support.
"""

from fastapi import APIRouter

from live_fetcher import (
    get_pune_wards_with_live_aqi,
    get_ward_centers,
)


# ---------------------------------------------------------------------------
# ROUTER
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api/aqi",
    tags=["Air Quality - Modeled"],
)


# ---------------------------------------------------------------------------
# CURRENT MODELED PUNE AIR-QUALITY CONTEXT
# ---------------------------------------------------------------------------

@router.get("/pune")
def get_pune_aqi():
    """
    Return current modeled air-quality context for Sentinel AI's
    configured Pune ward/locality analysis points.

    Values are produced by the existing live_fetcher.py pipeline.

    They are model-derived context and are not direct physical
    monitoring-station observations.

    This endpoint is independent from /api/aqi/observed.
    """

    locations = get_pune_wards_with_live_aqi()

    available_count = sum(
        1
        for location in locations
        if location.get("aqi") is not None
    )

    return {
        "count": len(locations),

        "available_count": available_count,

        "data_source": {
            "provider": "Open-Meteo",

            "underlying_model": (
                "CAMS Global Atmospheric Composition Forecast"
            ),

            "data_type": "modeled",

            "observed": False,

            "official_cpcb_observation": False,
        },

        "analysis_scope": "ward_focused",

        "spatial_interpretation": (
            "Sentinel AI uses configured Pune ward or locality "
            "analysis points for ward-focused decision support. "
            "Air-quality values are derived from modeled atmospheric "
            "data and are not direct monitoring-station observations "
            "or precise ward-wide measurements."
        ),

        "locations": locations,

        # ---------------------------------------------------------------
        # LEGACY FRONTEND COMPATIBILITY
        # ---------------------------------------------------------------
        #
        # Retained because the existing frontend may currently expect
        # the key 'stations'.
        #
        # These entries are the same modeled analysis locations as
        # 'locations'. They are NOT physical monitoring stations.
        "stations": locations,
    }


# ---------------------------------------------------------------------------
# WARD / LOCALITY ANALYSIS POINTS
# ---------------------------------------------------------------------------

@router.get("/wards")
def get_wards():
    """
    Return Sentinel AI's configured Pune ward/locality analysis points.

    These points support map-based and ward-focused decision analysis.

    They should not automatically be interpreted as verified official
    administrative ward polygons or official ward centroids.
    """

    locations = get_ward_centers()

    return {
        "count": len(locations),

        "analysis_scope": "ward_focused",

        "location_type": (
            "ward_or_locality_analysis_point"
        ),

        "spatial_precision": (
            "representative_analysis_point"
        ),

        "locations": locations,

        # ---------------------------------------------------------------
        # FRONTEND COMPATIBILITY
        # ---------------------------------------------------------------
        #
        # Retained because the existing frontend may expect 'wards'.
        "wards": locations,
    }