"""
spatial_evidence.py - Sentinel AI

Central spatial-evidence layer for enforcement prioritisation.

PURPOSE
Provide a consistent interface between geospatial evidence and the
root-cause / enforcement engines.

DESIGN PRINCIPLES

1. Missing evidence is NOT zero evidence.

   None:
       We do not currently have sufficient local data.

   0:
       We have a valid local evidence dataset and it indicates very low
       relevance.

2. Distributed pollution sources and localised pollution sources are
   treated differently.

   DISTRIBUTED:
       traffic
       road dust
       domestic/commercial combustion

   LOCALISED:
       industry
       construction
       quarry/dust point sources

3. This module does NOT claim source apportionment.

4. This module does NOT calculate pollution contribution percentages.

5. Evidence provenance is returned with every result.

For the current prototype:
- Localised candidate-source evidence comes from root_cause.py.
- Distributed-source evidence remains unavailable unless a validated local
  dataset is supplied.
- City-level source potential remains the responsibility of intervention.py.

Future datasets can be added here without changing the enforcement API.
"""

from typing import Optional


# ---------------------------------------------------------------------------
# SOURCE CLASSIFICATION
# ---------------------------------------------------------------------------

DISTRIBUTED_SOURCE_TYPES = {
    "traffic",
    "road_dust",
    "domestic_commercial",
}


LOCALISED_SOURCE_TYPES = {
    "industry",
    "construction",
    "quarry_dust",
}


# ---------------------------------------------------------------------------
# INTERVENTION -> EVIDENCE CATEGORY
# ---------------------------------------------------------------------------

LEVER_EVIDENCE_CONFIG = {

    "traffic_reduction": {
        "source_type": "traffic",
        "spatial_type": "distributed",
    },

    "road_dust_control": {
        "source_type": "road_dust",
        "spatial_type": "distributed",
    },

    "construction_halt": {
        "source_type": "construction",
        "spatial_type": "localised",
    },

    "industrial_throttle": {
        "source_type": "industry",
        "spatial_type": "localised",
    },

    "clean_cooking": {
        "source_type": "domestic_commercial",
        "spatial_type": "distributed",
    },
}


# ---------------------------------------------------------------------------
# EVIDENCE OBJECT
# ---------------------------------------------------------------------------

def make_evidence(
    source_type: str,
    spatial_type: str,
    score: Optional[float],
    available: bool,
    confidence: str,
    provenance: str,
    reason: str,
    top_candidate: Optional[dict] = None,
    supporting_candidates: Optional[list] = None,
) -> dict:
    """
    Build a standardized evidence result.

    score:
        Relative evidence score from 0-100, or None if local evidence
        is unavailable.

    IMPORTANT:
        None != 0.

        None means insufficient data.
        0 means valid evidence indicates very low relevance.
    """

    if score is not None:
        score = max(
            0.0,
            min(
                100.0,
                float(score),
            ),
        )

        score = round(
            score,
            1,
        )

    return {

        "source_type": source_type,

        "spatial_type": spatial_type,

        "available": bool(
            available
        ),

        "score": score,

        "confidence": confidence,

        "provenance": provenance,

        "reason": reason,

        "top_candidate": (
            top_candidate
        ),

        "supporting_candidates": (
            supporting_candidates
            or []
        ),
    }


# ---------------------------------------------------------------------------
# MISSING / UNAVAILABLE EVIDENCE
# ---------------------------------------------------------------------------

def unavailable_evidence(
    lever: str,
    reason: str,
) -> dict:
    """
    Return an explicit unavailable-evidence object.

    This must never be converted into score = 0.
    """

    config = LEVER_EVIDENCE_CONFIG.get(
        lever,
        {},
    )

    return make_evidence(

        source_type=config.get(
            "source_type",
            "unknown",
        ),

        spatial_type=config.get(
            "spatial_type",
            "unknown",
        ),

        score=None,

        available=False,

        confidence="Insufficient data",

        provenance=(
            "No validated local dataset "
            "currently integrated"
        ),

        reason=reason,
    )


# ---------------------------------------------------------------------------
# LOCALISED SOURCE EVIDENCE
# ---------------------------------------------------------------------------

def localised_candidate_evidence(
    lever: str,
    candidates: list,
    wind_is_live: bool,
) -> dict:
    """
    Build localised-source evidence from candidate-source influence results.

    Expected candidate structure:

        {
            "name": ...,
            "type": ...,
            "distance_km": ...,
            "upwind": ...,
            "influence_score": ...
        }

    The strongest candidate is used as the primary evidence score.

    IMPORTANT:
    influence_score is a RELATIVE HEURISTIC SCORE.
    It is not a pollution contribution percentage.
    """

    config = LEVER_EVIDENCE_CONFIG.get(
        lever
    )

    if not config:

        return unavailable_evidence(
            lever,
            (
                "No evidence configuration "
                "exists for this intervention."
            ),
        )

    if not candidates:

        return unavailable_evidence(
            lever,
            (
                "No validated candidate sources "
                "are represented for this source "
                "category."
            ),
        )

    ranked = sorted(

        candidates,

        key=lambda row:
        row.get(
            "influence_score",
            0.0,
        ),

        reverse=True,
    )

    top = ranked[0]

    score = float(
        top.get(
            "influence_score",
            0.0,
        )
    )

    if (
        wind_is_live
        and score >= 60
    ):

        confidence = (
            "Moderate"
        )

    elif score >= 25:

        confidence = (
            "Low to moderate"
        )

    else:

        confidence = (
            "Low"
        )

    return make_evidence(

        source_type=config[
            "source_type"
        ],

        spatial_type="localised",

        score=score,

        available=True,

        confidence=confidence,

        provenance=(
            "Candidate-source geospatial "
            "proximity + wind-alignment "
            "heuristic"
        ),

        reason=(
            "Relative local influence is based "
            "on candidate-source proximity and "
            "wind alignment. This is screening "
            "evidence, not causal attribution."
        ),

        top_candidate=top,

        supporting_candidates=(
            ranked[:3]
        ),
    )


# ---------------------------------------------------------------------------
# DISTRIBUTED SOURCE EVIDENCE
# ---------------------------------------------------------------------------

def distributed_source_evidence(
    lever: str,
    ward: str,
    local_score: Optional[float] = None,
    dataset_name: Optional[str] = None,
    dataset_note: Optional[str] = None,
) -> dict:
    """
    Build evidence for a distributed source.

    Examples:
        traffic
        road dust
        domestic/commercial combustion

    Distributed sources should NOT be represented by a single point-source
    coordinate.

    Until a validated ward-level dataset is integrated, local_score should
    remain None.
    """

    config = LEVER_EVIDENCE_CONFIG.get(
        lever
    )

    if not config:

        return unavailable_evidence(
            lever,
            (
                "No evidence configuration "
                "exists for this intervention."
            ),
        )

    if local_score is None:

        return unavailable_evidence(

            lever,

            (
                f"Local distributed-source evidence "
                f"is not currently available for "
                f"{ward}. City-level intervention "
                f"potential can still be evaluated, "
                f"but absence of local evidence must "
                f"not be interpreted as zero relevance."
            ),
        )

    score = max(
        0.0,
        min(
            100.0,
            float(local_score),
        ),
    )

    return make_evidence(

        source_type=config[
            "source_type"
        ],

        spatial_type="distributed",

        score=score,

        available=True,

        confidence=(
            "Dataset dependent"
        ),

        provenance=(
            dataset_name
            or
            "Local distributed-source dataset"
        ),

        reason=(
            dataset_note
            or
            "Local relevance derived from an "
            "integrated distributed-source dataset."
        ),
    )


# ---------------------------------------------------------------------------
# PUBLIC INTERFACE
# ---------------------------------------------------------------------------

def get_spatial_evidence(
    lever: str,
    ward: str,
    localised_candidates: Optional[list] = None,
    wind_is_live: bool = False,
    distributed_score: Optional[float] = None,
    distributed_dataset: Optional[str] = None,
    distributed_note: Optional[str] = None,
) -> dict:
    """
    Main spatial-evidence interface.

    Correctly routes the intervention to either:

        LOCALISED evidence
            -> candidate proximity + wind

    or

        DISTRIBUTED evidence
            -> ward-level distributed dataset

    Missing distributed data returns score=None,
    NOT score=0.
    """

    config = LEVER_EVIDENCE_CONFIG.get(
        lever
    )

    if config is None:

        return unavailable_evidence(
            lever,
            (
                "Unknown intervention lever."
            ),
        )

    spatial_type = config[
        "spatial_type"
    ]

    if spatial_type == "localised":

        return localised_candidate_evidence(

            lever=lever,

            candidates=(
                localised_candidates
                or []
            ),

            wind_is_live=(
                wind_is_live
            ),
        )

    if spatial_type == "distributed":

        return distributed_source_evidence(

            lever=lever,

            ward=ward,

            local_score=(
                distributed_score
            ),

            dataset_name=(
                distributed_dataset
            ),

            dataset_note=(
                distributed_note
            ),
        )

    return unavailable_evidence(

        lever,

        (
            "Unsupported spatial evidence type."
        ),
    )


# ---------------------------------------------------------------------------
# METHODOLOGY
# ---------------------------------------------------------------------------

def evidence_methodology() -> dict:
    """
    Explain the spatial-evidence methodology for API/frontend use.
    """

    return {

        "model": (
            "hybrid_spatial_evidence_layer"
        ),

        "distributed_sources": list(
            DISTRIBUTED_SOURCE_TYPES
        ),

        "localised_sources": list(
            LOCALISED_SOURCE_TYPES
        ),

        "principles": [

            (
                "Missing local evidence is represented "
                "as null, never as zero relevance."
            ),

            (
                "Localised candidate sources may use "
                "distance and wind-alignment screening."
            ),

            (
                "Distributed sources require area or "
                "network-level spatial evidence."
            ),

            (
                "Spatial evidence scores are not "
                "pollution contribution percentages."
            ),

            (
                "The evidence layer supports "
                "prioritisation and does not establish "
                "causal source attribution."
            ),
        ],
    }


# ---------------------------------------------------------------------------
# STANDALONE TEST
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    print(
        "SENTINEL AI - "
        "SPATIAL EVIDENCE LAYER\n"
    )

    ward = (
        "Revenue Colony Shivajinagar"
    )

    print(
        "TEST 1: Traffic with no "
        "local road-network dataset\n"
    )

    traffic = get_spatial_evidence(

        lever=(
            "traffic_reduction"
        ),

        ward=ward,
    )

    print(
        traffic
    )

    print(
        "\nTEST 2: Industry with "
        "candidate evidence\n"
    )

    industry = get_spatial_evidence(

        lever=(
            "industrial_throttle"
        ),

        ward=ward,

        localised_candidates=[
            {
                "name": (
                    "Example industrial "
                    "candidate"
                ),

                "type": "industry",

                "distance_km": 5.2,

                "upwind": True,

                "influence_score": 62.0,
            }
        ],

        wind_is_live=True,
    )

    print(
        industry
    )

    print(
        "\nNOTE:"
    )

    print(
        "Traffic evidence score should "
        "be None, not 0."
    )

    print(
        "Industry candidate score is "
        "relative screening evidence, "
        "not a pollution contribution "
        "percentage."
    )