"""
main.py - Sentinel AI Backend

Main FastAPI application for the Sentinel AI
urban air-quality decision-support prototype.

Data layers:
    1. Modeled air-quality context
       -> /api/aqi/pune

    2. Ward/locality analysis points
       -> /api/aqi/wards

    3. Recent observed monitoring-station PM snapshots
       -> /api/aqi/observed

    4. Intervention, enforcement, spatial-screening,
       and citizen-advisory intelligence
       -> intervention_api router

Development frontend:
    Next.js on localhost:3000 or localhost:3001

Important data boundaries:

    The modeled air-quality layer provides atmospheric-model-derived
    context for Sentinel AI's configured Pune ward/locality analysis
    points. It should not be interpreted as direct monitoring-station
    observations or precise ward-wide measurements.

    The observed layer provides recent raw PM2.5 and PM10 concentration
    snapshots from physical monitoring stations available through
    OpenAQ. These observations remain tied to station coordinates and
    are not directly converted into CPCB AQI or assigned to wards.

    Intervention scenarios estimate relative source-weighted
    particulate-burden change. They do not predict future AQI.

    Localized spatial screening identifies potential investigation
    leads. It does not establish causal pollution-source attribution.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.aqi import router as aqi_router
from api.observed import router as observed_router
from intervention_api import router as intervention_router


# ---------------------------------------------------------------------------
# APPLICATION
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Sentinel AI",
    description=(
        "Urban air-quality decision-support backend combining "
        "modeled air-quality context, recent observed monitoring-station "
        "PM snapshots, ward-focused analysis, source-weighted intervention "
        "scenario analysis, localized spatial source screening, "
        "evidence-aware enforcement prioritisation, and citizen "
        "health advisories."
    ),
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

# Development origins.
#
# Port 3000 is the standard Next.js development port.
# Port 3001 is included because Next.js may automatically use it
# when port 3000 is already occupied.

ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]


app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# ROUTERS
# ---------------------------------------------------------------------------

# Existing modeled AQI context and ward/locality analysis points:
#
#   GET /api/aqi/pune
#   GET /api/aqi/wards
#
# This existing pipeline remains independent from the OpenAQ
# observed monitoring-station layer.
app.include_router(
    aqi_router
)


# Recent raw PM2.5 / PM10 observations from physical monitoring stations:
#
#   GET /api/aqi/observed
#
# No AQI is calculated from these latest observations.
# Measurements remain tied to actual station coordinates.
app.include_router(
    observed_router
)


# Existing intervention scenario, spatial screening,
# enforcement-prioritisation, model-information,
# and citizen-advisory endpoints.
app.include_router(
    intervention_router
)


# ---------------------------------------------------------------------------
# ROOT
# ---------------------------------------------------------------------------

@app.get("/")
def root():

    return {
        "service": "Sentinel AI",

        "status": "running",

        "version": "1.0.0",

        "capabilities": [
            "current modeled air-quality context",
            "recent observed monitoring-station PM snapshots",
            "ward-focused air-quality analysis",
            "source-weighted intervention scenario analysis",
            "localized source screening",
            "spatial evidence assessment",
            "evidence-aware enforcement prioritisation",
            "citizen health advisories",
        ],

        "data_layers": {
            "modeled": {
                "endpoint": "/api/aqi/pune",
                "interpretation": (
                    "Model-derived air-quality context for configured "
                    "Pune analysis locations. Values are not direct "
                    "monitoring-station observations or precise "
                    "ward-wide measurements."
                ),
            },

            "observed": {
                "endpoint": "/api/aqi/observed",
                "interpretation": (
                    "Recent raw PM2.5 and PM10 concentration observations "
                    "from physical monitoring stations available through "
                    "OpenAQ. Observations remain tied to station coordinates "
                    "and are not directly converted into CPCB AQI or "
                    "interpreted as ward-wide measurements."
                ),
            },
        },

        "model_boundary": (
            "Intervention scenarios estimate relative source-weighted "
            "particulate-burden change and do not predict future AQI. "
            "Localized spatial screening identifies potential investigation "
            "leads and does not establish causal pollution-source attribution."
        ),
    }


# ---------------------------------------------------------------------------
# HEALTH CHECK
# ---------------------------------------------------------------------------

@app.get("/health")
def health():

    return {
        "status": "ok",
        "service": "Sentinel AI",
        "version": "1.0.0",
    }