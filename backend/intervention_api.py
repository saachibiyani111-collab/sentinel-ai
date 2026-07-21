"""
intervention_api.py - Sentinel AI

FastAPI API layer connecting:

    live_fetcher.py
        -> current modeled CPCB-method air-quality context
           for configured Pune analysis locations

    intervention.py
        -> source-weighted intervention scenario engine

    enforcement.py
        -> evidence-aware enforcement prioritisation

    advisory.py
        -> citizen health advisories


IMPORTANT MODEL BOUNDARY

Current AQI:
    - comes from live_fetcher.py
    - starts from independently queried CAMS Global modeled pollutant context
    - uses CPCB-method temporal aggregation before base AQI calculation
    - may share the same base modeled AQI where locations resolve to the same coarse model grid cell
    - may apply a historical composite-AQI spatial factor, when available, to produce
      the primary localized modeled AQI estimate
    - keeps base_modeled_aqi separately for transparency
    - does NOT apply the historical factor to pollutant concentrations or pollutant sub-indices
    - is modeled CPCB-method context, not an official CPCB station observation

Historical spatial factors:
    - are applied only to the composite base modeled AQI when available
    - are NOT applied to current pollutant concentrations or pollutant sub-indices
    - produce a historically informed localized modeled AQI estimate, not a measurement

Intervention simulator:
    - is a first-order source-weighted scenario model
    - estimates source-weighted particulate-burden reduction potential
    - estimates remaining relative particulate-burden index
    - does NOT predict future CPCB AQI
    - does NOT claim guaranteed policy effectiveness
    - does NOT claim validated ward-level source apportionment

Current AQI is used only as current contextual information and for:
    - enforcement urgency
    - citizen health advisory generation
"""

import math

from fastapi import (
    APIRouter,
    HTTPException,
)

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)

from live_fetcher import get_pune_wards_with_live_aqi

from intervention import (
    INTERVENTIONS,
    list_interventions,
    simulate,
    simulate_all,
    ward_shares,
)

from advisory import (
    advisory_for,
    advisories_all,
)

from enforcement import recommend


# ---------------------------------------------------------------------------
# ROUTER
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/api",
    tags=["Sentinel AI Decision Intelligence"],
)


# ---------------------------------------------------------------------------
# CURRENT LIVE/MODELED LOCATION CONTEXT
# ---------------------------------------------------------------------------

def _get_current_location_rows():
    """
    Return current modeled CPCB-method AQI context for all configured
    Sentinel AI analysis locations.

    The values come directly from live_fetcher.py.

    live_fetcher.py may already have applied a historical composite-AQI
    spatial factor to the primary localized AQI estimate. This API does not
    apply that factor a second time.
    """

    try:
        rows = get_pune_wards_with_live_aqi()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Current modeled air-quality context is unavailable: "
                f"{str(exc)}"
            ),
        )

    if not rows:
        raise HTTPException(
            status_code=503,
            detail=(
                "Current modeled air-quality context returned "
                "no configured locations."
            ),
        )

    return rows


def _get_current_location_map():
    """
    Index current modeled location rows by configured location name.
    """

    return {
        row["name"]: row
        for row in _get_current_location_rows()
        if row.get("name")
    }


def _known_wards():
    """
    Return the configured Sentinel AI analysis-location names.

    The project keeps the existing ward/location concept for frontend
    compatibility, but validation is based on the same configured
    locations used by live_fetcher.py.
    """

    return set(
        _get_current_location_map().keys()
    )


def _resolve_location_name(
    ward: str,
):
    """
    Resolve user/frontend location input to the canonical configured name.

    Matching is whitespace-trimmed and case-insensitive, so values such as
    'bhosari', 'Bhosari' and '  BHOSARI  ' resolve to the same location.

    The canonical configured spelling is always returned.
    """

    requested = str(
        ward
    ).strip().casefold()

    if not requested:
        raise HTTPException(
            status_code=404,
            detail="Configured location name cannot be empty.",
        )

    canonical_by_key = {
        str(name).strip().casefold():
            name
        for name in _known_wards()
    }

    canonical = canonical_by_key.get(
        requested
    )

    if canonical is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Unknown configured location '{ward}'."
            ),
        )

    return canonical


def _validate_ward_if_available(
    ward: str,
):
    """
    Backward-compatible validation helper.

    Returns the canonical configured location name.
    """

    return _resolve_location_name(
        ward
    )


def _get_current_aqi_for_ward(ward: str):
    """
    Return a usable current modeled AQI context for one configured location.

    A row is accepted only when:
    - the location exists
    - AQI is available
    - data is available
    - data is fresh/current enough to be used
    - live_fetcher has marked the context as usable

    This prevents stale or unavailable modeled AQI from silently
    propagating into advisory or enforcement decisions.
    """

    location_map = _get_current_location_map()
    row = location_map.get(ward)

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown location '{ward}'.",
        )

    if row.get("aqi") is None:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Current modeled AQI is unavailable for '{ward}'."
            ),
        )

    if row.get("data_available") is not True:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Current air-quality data is unavailable for '{ward}'."
            ),
        )

    if row.get("data_usable") is not True:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Air-quality context for '{ward}' is not usable "
                "because the modeled data is stale or incomplete."
            ),
        )

    if row.get("data_fresh") is not True:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Air-quality context for '{ward}' is not fresh enough "
                "for current advisory or enforcement use."
            ),
        )

    if row.get("is_current_context") is not True:
        raise HTTPException(
            status_code=503,
            detail=(
                f"No valid current air-quality context is available "
                f"for '{ward}'."
            ),
        )

    return row


def _row_is_usable_current_context(row: dict) -> bool:
    """
    Return True only for rows that are safe to use as current context
    in bulk simulation/advisory endpoints.

    This mirrors the acceptance criteria used by
    _get_current_aqi_for_ward() without raising per-row exceptions.
    """

    return (
        bool(row.get("name"))
        and row.get("aqi") is not None
        and row.get("data_available") is True
        and row.get("data_usable") is True
        and row.get("data_fresh") is True
        and row.get("is_current_context") is True
    )


def _aqi_context_method(row: dict) -> str:
    """
    Describe the AQI methodology accurately based on the live_fetcher row.
    """

    if row.get("historical_factor_applied_to_current_aqi") is True:
        return (
            "current historically adjusted modeled CPCB-method AQI estimate "
            "from live_fetcher; historical composite-AQI spatial factor applied"
        )

    return (
        "current modeled CPCB-method AQI estimate from live_fetcher; "
        "no historical spatial factor applied"
    )


def _aqi_context_metadata(row: dict) -> dict:
    """
    Return consistent AQI provenance and freshness metadata for
    downstream advisory and enforcement endpoints.
    """

    return {
        "aqi_context_source": row.get("source"),
        "aqi_context_reading_time": row.get("aqi_context_time"),
        "aqi_context_method": _aqi_context_method(row),

        "aqi_context_value_type": row.get("value_type"),

        "base_modeled_aqi": row.get("base_modeled_aqi"),
        "historical_spatial_factor":
            row.get("historical_spatial_factor"),

        "historical_factor_applied_to_current_aqi":
            row.get(
                "historical_factor_applied_to_current_aqi",
                False,
            ),

        "data_age_hours": row.get("data_age_hours"),
        "freshness_status": row.get("freshness_status"),
        "data_fresh": row.get("data_fresh", False),
        "data_usable": row.get("data_usable", False),
        "data_available": row.get("data_available", False),
        "is_current_context":
            row.get("is_current_context", False),

        "observed": row.get("observed", False),
        "official_cpcb_aqi":
            row.get("official_cpcb_aqi", False),
    }


# ---------------------------------------------------------------------------
# VALIDATION HELPERS
# ---------------------------------------------------------------------------

def _validate_finite_number(
    value,
    field_name: str,
):
    """
    Reject NaN and infinity values.
    """

    if value is None:
        return value

    if not math.isfinite(
        float(value)
    ):
        raise ValueError(
            f"{field_name} must be a finite number."
        )

    return value


def _validate_reductions(
    reductions: dict[str, float],
):
    """
    Validate intervention scenario assumptions.

    Rules:
        - intervention key must exist
        - reduction must be numeric
        - reduction must be finite
        - reduction must be between 0 and 1

    Example:

        {"traffic_reduction": 0.30}

    means:

        hypothetical 30% reduction in the targeted
        source contribution.

    It does NOT mean:

        guaranteed 30% policy effectiveness

    or:

        30% AQI improvement.
    """

    validated = {}

    for key, value in (
        reductions or {}
    ).items():

        if key not in INTERVENTIONS:

            valid_keys = ", ".join(
                sorted(
                    INTERVENTIONS.keys()
                )
            )

            raise ValueError(
                f"Unknown intervention '{key}'. "
                f"Valid interventions: {valid_keys}."
            )

        try:
            value = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            raise ValueError(
                f"Reduction for '{key}' "
                "must be numeric."
            )

        if not math.isfinite(
            value
        ):
            raise ValueError(
                f"Reduction for '{key}' "
                "must be a finite number."
            )

        if not (
            0.0 <= value <= 1.0
        ):
            raise ValueError(
                f"Reduction for '{key}' "
                "must be between 0 and 1."
            )

        validated[
            key
        ] = value

    return validated


# ---------------------------------------------------------------------------
# REQUEST MODELS
# ---------------------------------------------------------------------------

class SimulateRequest(
    BaseModel
):
    """
    Request for running one intervention scenario
    for one configured ward/location.

    Current modeled AQI is obtained internally from
    live_fetcher.py.

    The caller does NOT provide base_aqi.

    This prevents stale, hardcoded or frontend-supplied
    AQI values from being treated as current AQI.
    """

    ward: str = Field(
        ...,
        description=(
            "Configured Sentinel AI analysis location."
        ),
    )

    reductions: dict[
        str,
        float,
    ] = Field(
        default_factory=dict,
        description=(
            "Hypothetical source-reduction assumptions "
            "expressed as fractions from 0 to 1. "
            "Example: {'traffic_reduction': 0.3}."
        ),
    )

    @field_validator(
        "ward"
    )
    @classmethod
    def validate_ward(
        cls,
        value,
    ):

        value = value.strip()

        if not value:
            raise ValueError(
                "Ward/location name cannot be empty."
            )

        return value

    @field_validator(
        "reductions"
    )
    @classmethod
    def validate_reduction_values(
        cls,
        value,
    ):

        return _validate_reductions(
            value
        )


class SimulateAllRequest(
    BaseModel
):
    """
    Request for applying one intervention scenario
    across all configured wards/locations.

    Current modeled local AQI context is obtained internally
    from live_fetcher.py.

    Callers cannot inject a stale or hardcoded city AQI.
    """

    reductions: dict[
        str,
        float,
    ] = Field(
        default_factory=dict,
        description=(
            "Hypothetical source-reduction assumptions "
            "expressed as fractions from 0 to 1."
        ),
    )

    @field_validator(
        "reductions"
    )
    @classmethod
    def validate_reduction_values(
        cls,
        value,
    ):

        return _validate_reductions(
            value
        )


# ---------------------------------------------------------------------------
# API INFORMATION
# ---------------------------------------------------------------------------

@router.get(
    "/model-info"
)
def get_model_info():
    """
    Return transparent model boundaries for the frontend
    and hackathon demonstration.
    """

    return {

        "system":
            "Sentinel AI",

        "purpose":
            (
                "Urban air-quality decision intelligence "
                "and intervention scenario analysis"
            ),

        "current_aqi_model": {

            "source":
                "live_fetcher",

            "method":
                "modeled_cpcb_method_context",

            "location_queries":
                "independent",

            "historical_factors_applied_to_current_aqi":
                "when_available",

            "historical_factor_scope":
                "composite_base_modeled_aqi_only",

            "historical_factors_applied_to_current_pollutants":
                False,

            "historical_factors_applied_to_pollutant_sub_indices":
                False,

            "primary_aqi_value":
                "historically_adjusted_localized_modeled_aqi_estimate_when_factor_available",

            "base_aqi_transparency_field":
                "base_modeled_aqi",

            "direct_cpcb_station_observation":
                False,

            "coarse_grid_note":
                (
                    "Different configured locations may return "
                    "identical values when they resolve to the same "
                    "coarse atmospheric-model grid cell."
                ),
        },

        "intervention_model": {

            "type":
                "first_order_source_weighted_scenario",

            "future_aqi_predicted":
                False,

            "causal_source_attribution":
                False,

            "ward_specific_source_apportionment":
                False,

            "output":
                (
                    "relative source-weighted particulate-"
                    "burden reduction potential"
                ),
        },

        "enforcement_model": {

            "primary_signal":
                (
                    "city-level source-weighted "
                    "intervention potential"
                ),

            "local_evidence_role":
                (
                    "supporting contextual screening "
                    "evidence and secondary tie-break"
                ),

            "aqi_role":
                "enforcement urgency",

            "missing_evidence_policy":
                "null_not_zero",
        },
    }


# ---------------------------------------------------------------------------
# INTERVENTION CATALOGUE
# ---------------------------------------------------------------------------

@router.get(
    "/interventions"
)
def get_interventions():
    """
    Return intervention levers for frontend controls.
    """

    return {

        "interventions":
            list_interventions(),

        "slider_meaning":
            (
                "Each slider represents a hypothetical "
                "reduction in the targeted source contribution "
                "for scenario analysis. It is not a guaranteed "
                "policy-effectiveness percentage."
            ),

        "input_scale": {

            "minimum":
                0.0,

            "maximum":
                1.0,

            "frontend_display":
                "percentage",
        },

        "model_type":
            "first_order_source_weighted_scenario",

        "future_aqi_predicted":
            False,
    }


# ---------------------------------------------------------------------------
# SOURCE-WEIGHT PROFILE
# ---------------------------------------------------------------------------

@router.get(
    "/sources/{ward}"
)
def get_ward_sources(
    ward: str,
):
    """
    Return the source-weight profile used by the
    intervention scenario model.

    The current prototype uses city-level source weights.

    These values must NOT be presented as measured
    ward-level source contribution percentages.
    """

    ward = _validate_ward_if_available(
        ward
    )

    shares = ward_shares(
        ward
    )

    source_weights = [

        {
            "source":
                source,

            "weight_pct":
                round(
                    value * 100,
                    2,
                ),
        }

        for (
            source,
            value,
        ) in sorted(

            shares.items(),

            key=lambda item:
                -item[1],
        )
    ]

    return {

        "ward":
            ward,

        "source_weights":
            source_weights,

        "methodology": {

            "type":
                "city_level_source_weight_profile",

            "ward_specific":
                False,

            "purpose":
                "first_order_intervention_scenario",

            "note":
                (
                    "The current prototype does not claim "
                    "validated ward-level source apportionment. "
                    "City-level source weights are used for "
                    "transparent scenario analysis."
                ),
        },
    }


# ---------------------------------------------------------------------------
# SINGLE-WARD INTERVENTION SCENARIO
# ---------------------------------------------------------------------------

@router.post(
    "/simulate"
)
def post_simulate(
    req: SimulateRequest,
):
    """
    Run a first-order intervention scenario for one configured location.

    Current AQI is obtained internally from live_fetcher.py.

    The result describes relative source-weighted particulate
    burden change.

    It does NOT predict future CPCB AQI.
    """

    ward = _validate_ward_if_available(
        req.ward
    )

    current_row = _get_current_aqi_for_ward(
        ward
    )

    current_aqi = current_row[
        "aqi"
    ]

    result = simulate(
        ward=ward,
        base_aqi=current_aqi,
        reductions=req.reductions,
    )

    result[
        "current_aqi_context"
    ] = current_aqi

    result[
        "lat"
    ] = current_row.get(
        "lat"
    )

    result[
        "lon"
    ] = current_row.get(
        "lon"
    )

    if not isinstance(result, dict):
        raise HTTPException(
            status_code=500,
            detail="Intervention engine returned an invalid response.",
        )

    result.update(
        _aqi_context_metadata(current_row)
    )

    return result


# ---------------------------------------------------------------------------
# ALL-WARD / ALL-LOCATION INTERVENTION SCENARIO
# ---------------------------------------------------------------------------

@router.post(
    "/simulate/all"
)
def post_simulate_all(
    req: SimulateAllRequest,
):
    """
    Apply the same intervention scenario across all configured locations.

    Current modeled local AQI estimates come directly from
    live_fetcher.py.

    AQI is contextual only.

    The intervention engine does not predict future CPCB AQI.
    """

    location_rows = _get_current_location_rows()

    usable_rows = [

        row

        for row in location_rows

        if _row_is_usable_current_context(
            row
        )
    ]

    if not usable_rows:
        raise HTTPException(
            status_code=503,
            detail=(
                "No fresh, usable current modeled local AQI "
                "estimates are available."
            ),
        )

    ward_aqis = {

        row["name"]:
            row["aqi"]

        for row in usable_rows
    }

    results = simulate_all(
        ward_aqis,
        req.reductions,
    )

    row_lookup = {

        row["name"]:
            row

        for row in usable_rows
    }

    for result in results:

        row = row_lookup.get(
            result["ward"],
            {},
        )

        result[
            "lat"
        ] = row.get(
            "lat"
        )

        result[
            "lon"
        ] = row.get(
            "lon"
        )

        result[
            "current_aqi_context"
        ] = result.get(
            "base_aqi"
        )

        result[
            "aqi_context_source"
        ] = row.get(
            "source"
        )

        result.update(
            _aqi_context_metadata(row)
        )

    burden_reductions = [

        float(
            result.get(
                "estimated_burden_reduction_pct",
                0.0,
            )
        )

        for result in results
    ]

    avg_burden_reduction = (

        round(
            sum(
                burden_reductions
            ) / len(
                burden_reductions
            ),
            2,
        )

        if burden_reductions

        else 0.0
    )

    remaining_burden_index = round(

        max(
            0.0,
            100.0 - avg_burden_reduction,
        ),

        2,
    )

    return {

        "current_context_source":
            "live_fetcher_modeled_cpcb_method_estimates",

        "reductions":
            req.reductions,

        "wards":
            results,

        "summary": {

            "scenario_type":
                "source_weighted_particulate_burden",

            "estimated_burden_reduction_pct":
                avg_burden_reduction,

            "baseline_burden_index":
                100.0,

            "remaining_burden_index":
                remaining_burden_index,

            "future_aqi_predicted":
                False,

            "note":
                (
                    "This is a first-order source-reduction scenario. "
                    "It estimates relative change in source-weighted "
                    "particulate burden and does not predict future CPCB AQI."
                ),
        },

        "methodology": {

            "ward_aqi_role":
                "current_context_only",

            "ward_aqi_method":
                (
                    "current localized modeled CPCB-method AQI estimates "
                    "from live_fetcher; historical composite-AQI spatial "
                    "factors are applied to base modeled AQI when available"
                ),

            "historical_spatial_factors_applied":
                "when_available",

            "historical_factor_scope":
                "composite_base_modeled_aqi_only",

            "pollutants_adjusted_by_historical_factor":
                False,

            "intervention_model":
                "first_order_source_weighted_scenario",

            "ward_specific_source_profiles":
                False,

            "is_forecast":
                False,

            "same_relative_scenario_across_wards":
                True,

            "coarse_grid_note":
                (
                    "Configured locations may have identical current "
                    "AQI values when they resolve to the same coarse "
                    "atmospheric-model grid cell."
                ),
        },
    }


# ---------------------------------------------------------------------------
# ENFORCEMENT INTELLIGENCE
# ---------------------------------------------------------------------------

@router.get(
    "/enforce/{ward}"
)
def get_enforcement_plan(
    ward: str,
):
    """
    Generate an evidence-aware enforcement plan.

    Current AQI is obtained internally from live_fetcher.py.

    Ranking:
        Primary -> intervention potential

    Supporting context:
        Local spatial screening evidence when available

    Urgency:
        Current modeled AQI

    Missing local evidence:
        None, not zero
    """

    ward = _validate_ward_if_available(
        ward
    )

    current_row = _get_current_aqi_for_ward(
        ward
    )

    current_aqi = current_row[
        "aqi"
    ]

    try:

        result = recommend(
            ward,
            current_aqi,
        )

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to generate enforcement "
                f"intelligence: {str(exc)}"
            ),
        )

    if isinstance(
        result,
        dict,
    ):

        result[
            "current_aqi_context"
        ] = current_aqi

        result.update(
            _aqi_context_metadata(current_row)
        )

    return result


# ---------------------------------------------------------------------------
# SINGLE-WARD / SINGLE-LOCATION CITIZEN ADVISORY
# ---------------------------------------------------------------------------
@router.get(
    "/advisory/{ward}"
)
def get_advisory(
    ward: str,
):
    """
    Return a citizen health advisory using the validated current
    modeled AQI context from live_fetcher.

    The client cannot override AQI manually.
    Stale, unavailable, incomplete, or otherwise unusable current
    air-quality context is rejected by _get_current_aqi_for_ward().
    """

    row = _get_current_aqi_for_ward(
        ward
    )

    current_aqi = row["aqi"]

    result = advisory_for(
        ward,
        current_aqi,
    )

    # Preserve advisory_for() output while attaching the exact
    # provenance and freshness metadata of the AQI used.
    if not isinstance(result, dict):
        raise HTTPException(
            status_code=500,
            detail=(
                "Advisory engine returned an invalid response."
            ),
        )

    result.update(
        _aqi_context_metadata(row)
    )

    return result


# ---------------------------------------------------------------------------
# ALL-WARD / ALL-LOCATION CITIZEN ADVISORIES
# ---------------------------------------------------------------------------

@router.get(
    "/advisory"
)
def get_all_advisories():
    """
    Return citizen advisories for all configured locations.

    Current modeled local AQI estimates come directly from
    the same live_fetcher.py pipeline used by the AQI API.
    """

    location_rows = _get_current_location_rows()

    usable_rows = [

        row

        for row in location_rows

        if _row_is_usable_current_context(
            row
        )
    ]

    if not usable_rows:

        raise HTTPException(
            status_code=503,
            detail=(
                "No fresh, usable current modeled local AQI "
                "estimates are available."
            ),
        )

    ward_aqis = {

        row["name"]:
            row["aqi"]

        for row in usable_rows
    }

    return {

        "current_context_source":
            "live_fetcher_modeled_cpcb_method_estimates",

        "advisories":
            advisories_all(
                ward_aqis
            ),

        "methodology": {

            "aqi_role":
                "current_health_advisory_context",

            "ward_aqi_method":
                (
                    "current localized modeled CPCB-method AQI estimates "
                    "from live_fetcher; historical composite-AQI spatial "
                    "factors are applied to base modeled AQI when available"
                ),

            "historical_spatial_factors_applied":
                "when_available",

            "historical_factor_scope":
                "composite_base_modeled_aqi_only",

            "pollutants_adjusted_by_historical_factor":
                False,

            "is_direct_station_observation":
                False,

            "coarse_grid_note":
                (
                    "Configured locations may have identical AQI "
                    "values when they resolve to the same coarse "
                    "atmospheric-model grid cell."
                ),
        },
    }