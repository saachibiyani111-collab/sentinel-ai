from decimal import Decimal, ROUND_HALF_UP
"""
intervention.py - Sentinel AI

First-order source intervention scenario engine.

PURPOSE
Estimate the relative change in source-weighted particulate burden under
hypothetical emission/source reductions.

IMPORTANT:
- This module does NOT predict a new CPCB AQI.
- Overall AQI cannot safely be converted to PM2.5 concentration because the
  dominant pollutant may be PM10, O3, NO2, etc.
- Intervention percentages are scenario assumptions, NOT guaranteed real-world
  policy effectiveness.
- Source shares must be interpreted according to the exact basis of the
  underlying Pune EI/SA study. They are used here only as relative scenario
  weights until pollutant-specific provenance is fully verified.

The model is:

    weighted_reduction =
        SUM(source_weight * assumed_reduction_for_source)

    remaining_burden_index =
        100 * (1 - weighted_reduction)

This is a transparent first-order scenario model. It does not model atmospheric
chemistry, dispersion, secondary aerosol formation, meteorological feedback,
or cross-boundary transport.
"""

# ---------------------------------------------------------------------------
# SOURCE WEIGHTS
# ---------------------------------------------------------------------------
#
# These values are retained from the project's existing Pune EI/SA-derived
# configuration so the prototype remains operational.
#
# IMPORTANT:
# Do NOT describe these in the UI as verified "PM2.5 contribution percentages"
# unless the exact pollutant and methodological basis is confirmed directly
# from the underlying MPCB report table.
#
# For the simulator they are treated as SOURCE WEIGHTS for a first-order
# particulate-burden scenario.
#
# They sum to 1.0.

SOURCE_WEIGHTS = {
    "road_dust": 0.61,
    "vehicles": 0.18,
    "domestic": 0.075,
    "construction": 0.045,
    "hotels": 0.03,
    "industry": 0.0125,
    "other": 0.0475,
}


# No invented ward-specific source multipliers.
#
# Until defensible ward-level source-apportionment evidence exists, every ward
# uses the same city-level source weights.
WARD_PROFILES: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# INTERVENTION CATALOGUE
# ---------------------------------------------------------------------------

INTERVENTIONS = {
    "traffic_reduction": {
        "label": "Traffic emission reduction scenario",
        "affects": ["vehicles"],
        "note": (
            "Scenario applies an assumed reduction to the vehicle-source "
            "weight. It does not claim that a given policy automatically "
            "achieves the selected percentage."
        ),
    },

    "road_dust_control": {
        "label": "Road dust control scenario",
        "affects": ["road_dust"],
        "note": (
            "Scenario applies an assumed reduction to the road-dust source "
            "weight through measures such as sweeping, dust suppression, "
            "or paving."
        ),
    },

    "construction_halt": {
        "label": "Construction dust control scenario",
        "affects": ["construction"],
        "note": (
            "Scenario applies an assumed reduction to the construction-source "
            "weight. This represents source reduction, not a guaranteed AQI "
            "response."
        ),
    },

    "industrial_throttle": {
        "label": "Industrial emission reduction scenario",
        "affects": ["industry"],
        "note": (
            "Scenario applies an assumed reduction to the industrial-source "
            "weight."
        ),
    },

    "clean_cooking": {
        "label": "Domestic and commercial fuel transition scenario",
        "affects": ["domestic", "hotels"],
        "note": (
            "Scenario applies an assumed reduction to domestic-fuel and "
            "hotel/bakery source weights."
        ),
    },
}


def ward_shares(ward: str) -> dict:
    """
    Return normalized source weights for a ward.

    No ward-specific profiles are currently applied because the project does
    not have a validated ward-level source-apportionment dataset.
    """

    profile = WARD_PROFILES.get(ward, {})

    raw = {
        source: weight * profile.get(source, 1.0)
        for source, weight in SOURCE_WEIGHTS.items()
    }

    total = sum(raw.values())

    if total <= 0:
        return dict(SOURCE_WEIGHTS)

    return {
        source: weight / total
        for source, weight in raw.items()
    }


def _safe_fraction(value) -> float:
    """
    Convert an intervention value to a bounded fraction between 0 and 1.
    Invalid values safely become 0.
    """

    try:
        value = float(value)
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, min(1.0, value))


def simulate(
    ward: str,
    base_aqi: float | None,
    reductions: dict | None,
) -> dict:
    """
    Run a first-order intervention scenario for one ward.

    base_aqi is retained only as CONTEXT for the UI.
    It is NOT converted to PM2.5 and is NOT used to calculate a new AQI.

    reductions:
        {
            "traffic_reduction": 0.30,
            "road_dust_control": 0.50
        }

    Returns:
        - current AQI context
        - source-weighted particulate burden reduction
        - remaining burden index
        - per-source scenario breakdown

    The baseline burden index is always 100.
    """

    shares = ward_shares(ward)

    source_cut = {
        source: 0.0
        for source in shares
    }

    applied_reductions = {}

    for key, raw_fraction in (reductions or {}).items():

        spec = INTERVENTIONS.get(key)

        if spec is None:
            continue

        fraction = _safe_fraction(raw_fraction)

        applied_reductions[key] = fraction

        for source in spec["affects"]:
            if source not in source_cut:
                continue

            # If future interventions overlap, use the strongest assumption
            # rather than double-counting the same source.
            source_cut[source] = max(
                source_cut[source],
                fraction,
            )

    breakdown = []

    total_weighted_reduction = 0.0

    for source in sorted(
        shares,
        key=lambda s: -shares[s],
    ):

        share = shares[source]
        cut = source_cut[source]

        weighted_reduction = share * cut

        total_weighted_reduction += weighted_reduction

        breakdown.append(
            {
                "source": source,

                "source_weight_pct": round(
                    share * 100,
                    2,
                ),

                "assumed_source_reduction_pct": round(
                    cut * 100,
                    1,
                ),

                "weighted_burden_reduction_pct": round(
                    weighted_reduction * 100,
                    2,
                ),
            }
        )

    total_weighted_reduction = max(
        0.0,
        min(1.0, total_weighted_reduction),
    )

    # Use one canonical, human-facing rounded percentage and derive the
    # displayed remaining burden from the same value. This prevents
    # 52.37 vs 52.38 inconsistencies across endpoint summaries.
    burden_reduction_pct = float(
        Decimal(str(total_weighted_reduction * 100)).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    )

    remaining_burden_index = float(
        (Decimal("100.00") - Decimal(str(burden_reduction_pct))).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )
    )

    try:
        current_aqi = (
            round(float(base_aqi), 1)
            if base_aqi is not None
            else None
        )
    except (TypeError, ValueError):
        current_aqi = None

    return {
        "ward": ward,

        # Context only.
        "base_aqi": current_aqi,

        # Explicitly no fabricated future AQI.
        "new_aqi": None,
        "aqi_drop": None,
        "pct_drop": None,

        # Correct scenario outputs.
        "baseline_burden_index": 100.0,
        "remaining_burden_index": remaining_burden_index,
        "estimated_burden_reduction_pct": burden_reduction_pct,

        "reductions": applied_reductions,

        "breakdown": breakdown,

        "model": {
            "type": "first_order_source_weighted_scenario",
            "output": "relative_particulate_burden",
            "is_aqi_forecast": False,
            "is_emission_measurement": False,
            "limitations": [
                "Does not predict future CPCB AQI.",
                "Does not model atmospheric chemistry.",
                "Does not model pollutant dispersion.",
                "Does not model meteorological feedback.",
                "Does not model cross-boundary pollution transport.",
                "Selected intervention percentages are scenario assumptions.",
            ],
        },
    }


def simulate_all(
    ward_aqis: dict,
    reductions: dict | None,
) -> list[dict]:
    """
    Run the same intervention scenario for every ward.

    Ward AQI is retained as current context only.
    """

    return [
        simulate(
            ward=ward,
            base_aqi=aqi,
            reductions=reductions,
        )
        for ward, aqi in ward_aqis.items()
    ]


def list_interventions() -> list[dict]:
    """
    Return intervention catalogue for the frontend.
    """

    return [
        {
            "key": key,
            **spec,
        }
        for key, spec in INTERVENTIONS.items()
    ]


if __name__ == "__main__":

    print(
        "SENTINEL AI - Source Intervention Scenario\n"
    )

    result = simulate(
        "Revenue Colony Shivajinagar",
        138.6,
        {
            "traffic_reduction": 0.30,
        },
    )

    print(
        f"Ward: {result['ward']}"
    )

    print(
        f"Current AQI (context only): "
        f"{result['base_aqi']}"
    )

    print(
        "Traffic source reduction assumption: 30%"
    )

    print(
        "Estimated source-weighted particulate "
        f"burden reduction: "
        f"{result['estimated_burden_reduction_pct']}%"
    )

    print(
        "Remaining burden index: "
        f"{result['remaining_burden_index']}/100"
    )

    print(
        "\nAffected sources:"
    )

    for row in result["breakdown"]:

        if row[
            "assumed_source_reduction_pct"
        ] > 0:

            print(
                f"  {row['source']}: "
                f"weight={row['source_weight_pct']}%, "
                f"assumed reduction="
                f"{row['assumed_source_reduction_pct']}%, "
                f"weighted impact="
                f"{row['weighted_burden_reduction_pct']}%"
            )
