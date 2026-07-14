"""
intervention_api.py  (Sentinel AI)

FastAPI routes for the intervention simulator.

Mount in main.py:

    from intervention_api import router as intervention_router
    app.include_router(intervention_router)

Endpoints
    GET  /api/interventions                 -> catalogue (for building sliders)
    POST /api/simulate                      -> one ward, given reductions
    POST /api/simulate/all                  -> every ward at once (map view)
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field

from intervention import (
    INTERVENTIONS,
    list_interventions,
    simulate,
    simulate_all,
    ward_shares,
)

try:
    from ward_bias import apply_ward_bias, WARD_COORDS
except ImportError:
    WARD_COORDS = {}
    apply_ward_bias = None

router = APIRouter(prefix="/api", tags=["intervention"])


class SimulateRequest(BaseModel):
    ward: str = Field(..., description="Ward name, e.g. 'Revenue Colony Shivajinagar'")
    base_aqi: float = Field(..., description="Ward's current AQI")
    reductions: dict[str, float] = Field(
        default_factory=dict,
        description="{intervention_key: 0.0-1.0}, e.g. {'traffic_reduction': 0.3}",
    )


class SimulateAllRequest(BaseModel):
    city_aqi: float = Field(..., description="Live city AQI from Open-Meteo")
    reductions: dict[str, float] = Field(default_factory=dict)


@router.get("/interventions")
def get_interventions():
    """Catalogue of levers the UI can render as sliders."""
    return {"interventions": list_interventions()}


@router.get("/sources/{ward}")
def get_ward_sources(ward: str):
    """This ward's PM source breakdown -- powers the 'why' panel."""
    shares = ward_shares(ward)
    return {
        "ward": ward,
        "sources": [
            {"source": s, "share_pct": round(v * 100, 1)}
            for s, v in sorted(shares.items(), key=lambda x: -x[1])
        ],
    }


@router.post("/simulate")
def post_simulate(req: SimulateRequest):
    """Run interventions on a single ward."""
    return simulate(req.ward, req.base_aqi, req.reductions)


@router.post("/simulate/all")
def post_simulate_all(req: SimulateAllRequest):
    """
    Run the same intervention across all wards.

    Takes the live city AQI, applies each ward's alpha to get its baseline,
    then simulates. Returns everything the map needs to recolour.
    """
    if apply_ward_bias is None:
        return {"error": "ward_bias not available"}

    ward_rows = apply_ward_bias(req.city_aqi, WARD_COORDS)
    ward_aqis = {r["ward"]: r["aqi"] for r in ward_rows}

    results = simulate_all(ward_aqis, req.reductions)
    coords = {r["ward"]: (r["lat"], r["lon"]) for r in ward_rows}

    for r in results:
        lat, lon = coords.get(r["ward"], (None, None))
        r["lat"], r["lon"] = lat, lon

    total_before = sum(r["base_aqi"] for r in results)
    total_after = sum(r["new_aqi"] for r in results)
    n = len(results) or 1

    return {
        "city_aqi": req.city_aqi,
        "reductions": req.reductions,
        "wards": results,
        "summary": {
            "avg_aqi_before": round(total_before / n, 1),
            "avg_aqi_after": round(total_after / n, 1),
            "avg_drop": round((total_before - total_after) / n, 1),
            "avg_pct_drop": round(
                100 * (total_before - total_after) / total_before, 1
            ) if total_before else 0.0,
            "best_ward": max(results, key=lambda r: r["pct_drop"])["ward"]
            if results else None,
        },
    }
