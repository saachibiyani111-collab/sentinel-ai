"""
enforcement.py - Sentinel AI Enforcement Intelligence Engine

PURPOSE
Generate explainable enforcement priorities for a ward.

CONNECTED FLOW

intervention.py
    -> city-level source-weighted intervention potential

root_cause.py
    -> localized candidate-source screening
       (industry and construction only)

spatial_evidence.py
    -> standardizes local evidence
       available score OR None when unavailable

enforcement.py
    -> primary intervention ranking
    -> supporting local evidence
    -> AQI-based urgency
    -> concrete enforcement actions


CORE LOGIC

1. INTERVENTION POTENTIAL
   Primary ranking signal.

   Every intervention is tested at the same hypothetical source-reduction
   intensity so interventions can be compared consistently.

2. LOCAL SPATIAL EVIDENCE
   Supporting contextual evidence.

   Local evidence is NOT mathematically blended with intervention potential,
   because these scores represent different quantities.

   It is used only as a secondary tie-breaker if primary intervention
   potentials are equal.

3. AQI
   Determines enforcement urgency only.

   AQI severity does not identify the pollution source.

4. MISSING EVIDENCE
   Missing local evidence is represented as None, never zero.

IMPORTANT

- Priority scores are relative intervention-potential rankings.
- They are NOT pollution contribution percentages.
- They are NOT predicted AQI reductions.
- Local influence scores are heuristic screening scores.
- They do NOT establish causal source attribution.
"""

from intervention import (
    INTERVENTIONS,
    simulate,
)

from root_cause import (
    analyze_ward_current,
)

from spatial_evidence import (
    get_spatial_evidence,
    evidence_methodology,
)

try:
    from ward_bias import WARD_COORDS
except ImportError:
    WARD_COORDS = {}


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

# Common hypothetical source-reduction scenario.
#
# Example:
# 50% traffic scenario means:
# "What is the source-weighted particulate-burden potential if the
# traffic-source contribution were hypothetically reduced by 50%?"
#
# It does NOT claim enforcement will actually achieve 50%.
RANKING_INTENSITY = 0.50


# ---------------------------------------------------------------------------
# LOCALIZED SOURCE TYPE -> INTERVENTION
# ---------------------------------------------------------------------------

LOCALISED_TYPE_TO_LEVER = {
    "industry": "industrial_throttle",
    "construction": "construction_halt",
}


# ---------------------------------------------------------------------------
# ENFORCEMENT ACTIONS
# ---------------------------------------------------------------------------

ACTIONS = {

    "road_dust_control": [
        "Inspect high-dust road corridors and unpaved shoulders",
        "Prioritise mechanised sweeping where operationally feasible",
        "Apply appropriate dust-suppression measures",
        "Inspect uncovered soil, debris and material storage near identified hotspots",
    ],

    "traffic_reduction": [
        "Identify high-congestion corridors for targeted traffic management",
        "Strengthen PUC and visibly polluting vehicle enforcement",
        "Review heavy-vehicle routing and time restrictions where legally applicable",
        "Coordinate traffic-flow measures at persistent congestion hotspots",
    ],

    "construction_halt": [
        "Prioritise inspection of relevant active construction sites",
        "Check dust barriers and debris-handling compliance",
        "Verify covered transport of construction materials",
        "Escalate action against non-compliant sites under applicable regulations",
    ],

    "clean_cooking": [
        "Identify areas with significant solid-fuel combustion before targeted action",
        "Support transition to cleaner domestic and commercial fuels where applicable",
        "Inspect relevant commercial combustion sources where legally authorised",
    ],

    "industrial_throttle": [
        "Prioritise compliance inspection of relevant industrial units",
        "Review available stack-emission and consent-compliance records",
        "Escalate monitoring of visibly polluting or non-compliant units",
    ],
}


# ---------------------------------------------------------------------------
# WARD COORDINATES
# ---------------------------------------------------------------------------

def _get_ward_coordinates(ward: str):
    """
    Return latitude and longitude for a ward.

    Supports:
        (lat, lon)

    and:
        {"lat": ..., "lon": ...}
    """

    coords = WARD_COORDS.get(ward)

    if coords is None:
        return None, None

    if (
        isinstance(coords, (tuple, list))
        and len(coords) >= 2
    ):
        return (
            float(coords[0]),
            float(coords[1]),
        )

    if isinstance(coords, dict):

        lat = coords.get("lat")
        lon = coords.get("lon")

        if lat is not None and lon is not None:
            return (
                float(lat),
                float(lon),
            )

    return None, None


# ---------------------------------------------------------------------------
# AQI URGENCY
# ---------------------------------------------------------------------------

def _aqi_urgency(base_aqi):
    """
    Convert current CPCB AQI into enforcement urgency.

    AQI is used ONLY for urgency.

    It does not affect source attribution or intervention ranking.
    """

    try:
        aqi = float(base_aqi)

    except (TypeError, ValueError):

        return {
            "aqi": None,
            "category": "Unknown",
            "urgency": "Unknown",
            "urgency_score": None,
        }

    aqi = max(
        0.0,
        min(500.0, aqi),
    )

    if aqi <= 50:

        category = "Good"
        urgency = "Low"
        urgency_score = 1

    elif aqi <= 100:

        category = "Satisfactory"
        urgency = "Routine"
        urgency_score = 2

    elif aqi <= 200:

        category = "Moderate"
        urgency = "Elevated"
        urgency_score = 3

    elif aqi <= 300:

        category = "Poor"
        urgency = "High"
        urgency_score = 4

    elif aqi <= 400:

        category = "Very Poor"
        urgency = "Very High"
        urgency_score = 5

    else:

        category = "Severe"
        urgency = "Critical"
        urgency_score = 6

    return {
        "aqi": round(aqi, 1),
        "category": category,
        "urgency": urgency,
        "urgency_score": urgency_score,
    }


# ---------------------------------------------------------------------------
# INTERVENTION POTENTIAL
# ---------------------------------------------------------------------------

def _calculate_intervention_potentials(
    ward: str,
    base_aqi,
):
    """
    Evaluate every intervention using the same hypothetical intensity.

    Returns:
        {
            intervention_key:
            estimated source-weighted particulate-burden reduction %
        }

    This is NOT predicted AQI reduction.
    """

    potentials = {}

    for lever in INTERVENTIONS:

        result = simulate(
            ward=ward,
            base_aqi=base_aqi,
            reductions={
                lever: RANKING_INTENSITY
            },
        )

        potentials[lever] = result[
            "estimated_burden_reduction_pct"
        ]

    return potentials


# ---------------------------------------------------------------------------
# LOCALIZED SOURCE SCREENING
# ---------------------------------------------------------------------------

def _get_localised_screening(
    ward: str,
):
    """
    Run localized candidate-source screening.

    Only localized source categories are routed here.

    Distributed sources such as:
        traffic
        general road dust
        domestic/commercial combustion

    require network/area-level datasets and are not represented
    by individual candidate coordinates.
    """

    lat, lon = _get_ward_coordinates(
        ward
    )

    if lat is None or lon is None:

        return {
            "available": False,
            "wind_available": False,
            "wind_from_deg": None,
            "wind_speed": None,
            "wind_source": None,
            "by_lever": {},
        }

    analysis = analyze_ward_current(
        lat,
        lon,
    )

    if not analysis.get(
        "wind_available",
        False,
    ):

        return {
            "available": False,
            "wind_available": False,
            "wind_from_deg": None,
            "wind_speed": None,
            "wind_source": analysis.get(
                "wind_source"
            ),
            "by_lever": {},
        }

    by_lever = {}

    for source in analysis.get(
        "sources",
        [],
    ):

        lever = LOCALISED_TYPE_TO_LEVER.get(
            source.get("type")
        )

        if lever is None:
            continue

        by_lever.setdefault(
            lever,
            [],
        ).append(
            source
        )

    return {
        "available": True,

        "wind_available": True,

        "wind_from_deg": analysis.get(
            "wind_from_deg"
        ),

        "wind_speed": analysis.get(
            "wind_speed"
        ),

        "wind_source": analysis.get(
            "wind_source"
        ),

        "by_lever": by_lever,
    }


# ---------------------------------------------------------------------------
# STANDARDIZED SPATIAL EVIDENCE
# ---------------------------------------------------------------------------

def _build_spatial_evidence(
    ward: str,
):
    """
    Build spatial evidence for all intervention levers.

    LOCALIZED:
        industry
        construction

        -> candidate proximity
        -> current modeled wind
        -> spatial_evidence.py

    DISTRIBUTED:
        traffic
        road dust
        domestic/commercial

        -> no validated local dataset currently integrated
        -> score = None

    Missing evidence is NEVER converted to zero.
    """

    screening = _get_localised_screening(
        ward
    )

    evidence = {}

    for lever in INTERVENTIONS:

        candidates = screening[
            "by_lever"
        ].get(
            lever,
            [],
        )

        evidence[lever] = (
            get_spatial_evidence(

                lever=lever,

                ward=ward,

                localised_candidates=candidates,

                wind_is_live=screening[
                    "wind_available"
                ],

                # Distributed local datasets
                # are not currently integrated.
                distributed_score=None,
            )
        )

    return (
        evidence,
        screening,
    )


# ---------------------------------------------------------------------------
# PRIORITY LEVEL
# ---------------------------------------------------------------------------

def _priority_level(
    normalized_potential,
):
    """
    Human-readable relative intervention-potential category.

    This describes position within the current intervention catalogue.
    It is NOT an absolute scientific risk classification.
    """

    if normalized_potential >= 70:
        return "High"

    if normalized_potential >= 25:
        return "Medium"

    return "Lower"


# ---------------------------------------------------------------------------
# CONFIDENCE
# ---------------------------------------------------------------------------

def _overall_confidence(
    spatial,
):
    """
    Conservative evidence-availability description.

    This is NOT statistical confidence.
    """

    if not spatial[
        "available"
    ]:

        return (
            "City-level evidence; "
            "local evidence unavailable"
        )

    confidence = spatial.get(
        "confidence"
    )

    if confidence == "Moderate":

        return (
            "City-level evidence + "
            "moderate local screening evidence"
        )

    if confidence == (
        "Low to moderate"
    ):

        return (
            "City-level evidence + "
            "limited-to-moderate local screening evidence"
        )

    return (
        "City-level evidence + "
        "limited local screening evidence"
    )


# ---------------------------------------------------------------------------
# SORT KEY
# ---------------------------------------------------------------------------

def _sort_key(
    row,
):
    """
    Ranking hierarchy.

    PRIMARY:
        normalized city-level intervention potential

    SECONDARY:
        available local evidence score

    Local evidence is used only as a tie-breaker.

    This avoids mathematically blending scores that represent
    different concepts.
    """

    potential = row[
        "intervention_potential"
    ][
        "normalized_potential_score"
    ]

    local = row[
        "local_evidence"
    ]

    if (
        local["available"]
        and local["score"] is not None
    ):

        local_score = local[
            "score"
        ]

    else:

        # Missing evidence is not zero.
        # -1 is used only internally for tie sorting.
        local_score = -1

    return (
        potential,
        local_score,
    )


# ---------------------------------------------------------------------------
# MAIN ENGINE
# ---------------------------------------------------------------------------

def recommend(
    ward: str,
    base_aqi: float,
):
    """
    Generate an evidence-aware enforcement plan.

    LOGIC

    1. AQI
       -> determines urgency

    2. City-level intervention potential
       -> determines primary intervention ranking

    3. Local spatial evidence
       -> provides supporting context
       -> secondary tie-break only

    4. Missing local evidence
       -> represented as None
       -> does NOT reduce priority

    The result is an explainable decision-support ranking.
    """

    # -------------------------------------------------------
    # AQI URGENCY
    # -------------------------------------------------------

    urgency = _aqi_urgency(
        base_aqi
    )


    # -------------------------------------------------------
    # CITY-LEVEL INTERVENTION POTENTIAL
    # -------------------------------------------------------

    potentials = (
        _calculate_intervention_potentials(
            ward,
            base_aqi,
        )
    )

    max_potential = max(
        potentials.values(),
        default=0.0,
    )


    # -------------------------------------------------------
    # LOCAL SPATIAL EVIDENCE
    # -------------------------------------------------------

    (
        spatial_by_lever,
        screening,
    ) = _build_spatial_evidence(
        ward
    )


    # -------------------------------------------------------
    # BUILD RECOMMENDATIONS
    # -------------------------------------------------------

    recommendations = []

    for (
        lever,
        spec,
    ) in INTERVENTIONS.items():

        potential = potentials.get(
            lever,
            0.0,
        )


        # ---------------------------------------------------
        # NORMALIZE CITY-LEVEL POTENTIAL
        # ---------------------------------------------------

        if max_potential > 0:

            normalized_potential = (
                potential
                / max_potential
                * 100.0
            )

        else:

            normalized_potential = 0.0

        normalized_potential = round(
            normalized_potential,
            1,
        )


        # ---------------------------------------------------
        # SPATIAL EVIDENCE
        # ---------------------------------------------------

        spatial = spatial_by_lever[
            lever
        ]

        local_available = spatial[
            "available"
        ]

        local_score = spatial[
            "score"
        ]


        # ---------------------------------------------------
        # RANKING BASIS
        # ---------------------------------------------------

        if (
            local_available
            and local_score is not None
        ):

            ranking_basis = (
                "City-level intervention potential, "
                "with available local screening evidence "
                "reported as supporting context"
            )

        else:

            ranking_basis = (
                "City-level intervention potential; "
                "local evidence unavailable"
            )


        # ---------------------------------------------------
        # EXPLANATION
        # ---------------------------------------------------

        reasons = [

            (
                f"At the common "
                f"{int(RANKING_INTENSITY * 100)}% "
                f"source-reduction scenario, this lever "
                f"has an estimated {potential}% "
                f"source-weighted particulate-burden "
                f"reduction potential."
            )
        ]


        if (
            local_available
            and spatial[
                "top_candidate"
            ]
        ):

            candidate = spatial[
                "top_candidate"
            ]

            is_upwind = candidate.get(
                "approximately_upwind",
                candidate.get(
                    "upwind",
                    False,
                ),
            )

            direction_text = (
                "approximately upwind"
                if is_upwind
                else
                "not currently upwind"
            )

            reasons.append(

                (
                    f"Localized screening candidate: "
                    f"{candidate['name']} "
                    f"({candidate['distance_km']} km, "
                    f"{direction_text}, "
                    f"relative screening score "
                    f"{candidate['influence_score']}/100)."
                )
            )

        else:

            reasons.append(
                spatial[
                    "reason"
                ]
            )


        # ---------------------------------------------------
        # RECOMMENDATION OBJECT
        # ---------------------------------------------------

        recommendations.append(

            {
                "lever":
                    lever,

                "label":
                    spec[
                        "label"
                    ],

                # Backward-compatible field.
                #
                # This is now explicitly the normalized
                # intervention-potential score.
                "priority_score":
                    normalized_potential,

                "relative_intervention_potential":
                    normalized_potential,

                "priority_level":
                    _priority_level(
                        normalized_potential
                    ),

                "ranking_basis":
                    ranking_basis,

                "intervention_potential": {

                    "scenario_assumption_pct":
                        RANKING_INTENSITY
                        * 100,

                    "estimated_burden_reduction_pct":
                        potential,

                    "normalized_potential_score":
                        normalized_potential,
                },

                "local_evidence":
                    spatial,

                "confidence":
                    _overall_confidence(
                        spatial
                    ),

                "why":
                    reasons,

                "actions":
                    ACTIONS.get(
                        lever,
                        [],
                    ),
            }
        )


    # -------------------------------------------------------
    # RANK
    # -------------------------------------------------------

    recommendations.sort(
        key=_sort_key,
        reverse=True,
    )


    # -------------------------------------------------------
    # ASSIGN PRIORITY NUMBER
    # -------------------------------------------------------

    for (
        index,
        row,
    ) in enumerate(
        recommendations,
        start=1,
    ):

        row[
            "priority"
        ] = index


    # -------------------------------------------------------
    # SEPARATE DECISION VIEWS
    # -------------------------------------------------------
    #
    # `recommendations` remains the CITY-LEVEL POLICY INTERVENTION
    # ranking for backward compatibility. It is based on comparative
    # source-weighted scenario potential.
    #
    # Local investigation leads are intentionally ranked separately.
    # A local screening score is not a pollution-contribution estimate
    # and is therefore never mathematically blended with intervention
    # potential or AQI.

    policy_intervention_priorities = list(
        recommendations
    )

    local_investigation_priorities = []

    for row in recommendations:

        local = row.get(
            "local_evidence",
            {},
        )

        if not (
            local.get("available")
            and local.get("score") is not None
        ):
            continue

        local_investigation_priorities.append(
            {
                "lever":
                    row.get("lever"),

                "label":
                    row.get("label"),

                "screening_score":
                    local.get("score"),

                "top_candidate":
                    local.get("top_candidate"),

                "confidence":
                    row.get("confidence"),

                "current_aqi":
                    urgency["aqi"],

                "enforcement_urgency":
                    urgency["urgency"],

                "interpretation":
                    (
                        "Local screening lead for inspection or "
                        "verification. This ranking does not establish "
                        "causal pollution attribution and is not a "
                        "source-contribution percentage."
                    ),
            }
        )

    local_investigation_priorities.sort(
        key=lambda item: (
            item["screening_score"]
            if item["screening_score"] is not None
            else -1
        ),
        reverse=True,
    )

    for index, item in enumerate(
        local_investigation_priorities,
        start=1,
    ):
        item["investigation_priority"] = index


    # -------------------------------------------------------
    # GROUPS
    # -------------------------------------------------------

    high_priority = [

        row

        for row in recommendations

        if row[
            "priority_level"
        ] == "High"
    ]

    medium_priority = [

        row

        for row in recommendations

        if row[
            "priority_level"
        ] == "Medium"
    ]

    lower_priority = [

        row

        for row in recommendations

        if row[
            "priority_level"
        ] == "Lower"
    ]


    # -------------------------------------------------------
    # FINAL RESPONSE
    # -------------------------------------------------------

    return {

        "ward":
            ward,

        "current_aqi":
            urgency[
                "aqi"
            ],

        # Backward-compatible alias.
        "base_aqi":
            urgency[
                "aqi"
            ],

        "aqi_category":
            urgency[
                "category"
            ],

        "enforcement_urgency":
            urgency[
                "urgency"
            ],

        "urgency_score":
            urgency[
                "urgency_score"
            ],

        "wind": {

            "available":
                screening[
                    "wind_available"
                ],

            "direction_from_deg":
                screening[
                    "wind_from_deg"
                ],

            "speed":
                screening[
                    "wind_speed"
                ],

            "source":
                screening[
                    "wind_source"
                ],
        },

        # Backward-compatible city-level policy ranking.
        "recommended":
            recommendations,

        "policy_intervention_priorities":
            policy_intervention_priorities,

        "local_investigation_priorities":
            local_investigation_priorities,

        "high_priority":
            high_priority,

        "medium_priority":
            medium_priority,

        "lower_priority":
            lower_priority,

        # Backward-compatible field. Intentionally empty: a lower
        # city-level scenario priority does not mean an action is
        # scientifically or operationally "not recommended".
        "not_recommended":
            [],

        "methodology": {

            "type":
                "evidence_aware_enforcement_prioritisation",

            "policy_ranking_signal":
                (
                    "normalized city-level source-weighted "
                    "intervention potential"
                ),

            "local_investigation_ranking_signal":
                (
                    "available localized spatial screening evidence"
                ),

            "local_evidence_role":
                (
                    "separate local investigation lead; never "
                    "mathematically blended with policy intervention "
                    "potential or AQI"
                ),

            "aqi_role":
                "enforcement urgency only",

            "priority_logic":
                (
                    "Two decision views are kept separate. "
                    "Policy intervention priorities rank comparative "
                    "city-level source-weighted scenario potential. "
                    "Local investigation priorities rank only available "
                    "localized spatial screening leads. Missing local "
                    "evidence is represented as null and does not reduce "
                    "policy priority. Neither ranking establishes causal "
                    "source attribution."
                ),

            "missing_evidence_policy":
                "null_not_zero",

            "future_aqi_predicted":
                False,

            "causal_source_attribution":
                False,

            "spatial_evidence":
                evidence_methodology(),

            "limitations": [

                (
                    "Relative intervention-potential scores "
                    "are comparative decision-support scores, "
                    "not pollution contribution percentages."
                ),

                (
                    "Intervention percentages represent "
                    "hypothetical source-reduction scenarios, "
                    "not guaranteed policy effectiveness."
                ),

                (
                    "Localized candidate-source screening "
                    "does not establish causal attribution."
                ),

                (
                    "Distributed local evidence for traffic, "
                    "general road dust and domestic/commercial "
                    "combustion is not yet integrated."
                ),

                (
                    "Localized candidate coordinates and "
                    "heuristic strength priors require "
                    "further validation for production use."
                ),
            ],
        },
    }


# ---------------------------------------------------------------------------
# STANDALONE TEST
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    ward = (
        "Revenue Colony Shivajinagar"
    )

    base_aqi = 138.6

    plan = recommend(
        ward,
        base_aqi,
    )

    print(
        "SENTINEL AI - "
        "ENFORCEMENT INTELLIGENCE\n"
    )

    print(
        f"Ward: {plan['ward']}"
    )

    print(
        f"Current AQI: "
        f"{plan['current_aqi']} "
        f"({plan['aqi_category']})"
    )

    print(
        f"Enforcement urgency: "
        f"{plan['enforcement_urgency']}"
    )

    if plan[
        "wind"
    ][
        "available"
    ]:

        print(
            f"Current modeled wind from: "
            f"{plan['wind']['direction_from_deg']} "
            f"degrees"
        )

    print(
        "\nPrioritised actions:\n"
    )

    for row in plan[
        "recommended"
    ]:

        print(
            f"#{row['priority']} "
            f"{row['label']}"
        )

        print(
            f"   Relative intervention potential: "
            f"{row['relative_intervention_potential']}/100 "
            f"({row['priority_level']})"
        )

        print(
            f"   Scenario burden-reduction potential: "
            f"{row['intervention_potential']['estimated_burden_reduction_pct']}%"
        )

        print(
            f"   Ranking basis: "
            f"{row['ranking_basis']}"
        )

        local = row[
            "local_evidence"
        ]

        if (
            local[
                "available"
            ]
            and local[
                "score"
            ] is not None
        ):

            print(
                f"   Local screening evidence: "
                f"{local['score']}/100"
            )

        else:

            print(
                "   Local screening evidence: "
                "Unavailable "
                "(not treated as zero)"
            )

        print(
            f"   Evidence context: "
            f"{row['confidence']}"
        )

        for reason in row[
            "why"
        ]:

            print(
                f"   - {reason}"
            )

        print()


    print(
        "NOTE: Intervention-potential scores "
        "are relative decision-support rankings. "
        "Local screening scores are supporting "
        "context. Neither represents pollution "
        "contribution percentages or predicted "
        "AQI improvement."
    )