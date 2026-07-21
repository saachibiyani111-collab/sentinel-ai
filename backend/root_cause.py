"""
root_cause.py - Sentinel AI Localized Source Screening Engine

PURPOSE
Screen known localized candidate pollution sources near a ward using:
- geographic proximity
- current modeled wind direction
- an explicitly labelled heuristic strength prior

THIS MODULE DOES NOT:
- perform source apportionment
- prove causation
- calculate pollution contribution percentages
- represent distributed sources such as general traffic or road dust

Distributed sources must be handled separately using network/area-level
datasets through spatial_evidence.py.

Current wind data is obtained from Open-Meteo model output.
It should be described as "current modeled wind", not an on-site measurement.
"""

import math
import requests


WEATHER_URL = "https://api.open-meteo.com/v1/forecast"


# ---------------------------------------------------------------------------
# LOCALISED CANDIDATE SOURCES ONLY
# ---------------------------------------------------------------------------
#
# IMPORTANT:
# These locations are prototype candidate locations.
#
# strength_prior values are heuristic screening priors.
# They are NOT measured emissions and NOT official contribution percentages.
#
# Production deployment should replace these priors with verified emissions,
# permits, industrial inventories or other authoritative activity data.
# ---------------------------------------------------------------------------

PUNE_LOCALISED_SOURCES = [

    {
        "name": "Pimpri-Chinchwad Industrial Area",
        "lat": 18.6280,
        "lon": 73.8000,
        "type": "industry",
        "strength_prior": 0.90,
    },

    {
        "name": "Bhosari MIDC",
        "lat": 18.6300,
        "lon": 73.8470,
        "type": "industry",
        "strength_prior": 0.80,
    },

    {
        "name": "Hadapsar Industrial Estate",
        "lat": 18.5010,
        "lon": 73.9400,
        "type": "industry",
        "strength_prior": 0.70,
    },

    {
        "name": "Nagar Road construction belt",
        "lat": 18.5520,
        "lon": 73.9100,
        "type": "construction",
        "strength_prior": 0.70,
    },

    {
        "name": "Hinjewadi IT construction",
        "lat": 18.5910,
        "lon": 73.7380,
        "type": "construction",
        "strength_prior": 0.60,
    },

    {
        "name": "Wagholi quarry/dust zone",
        "lat": 18.5800,
        "lon": 73.9800,
        "type": "quarry_dust",
        "strength_prior": 0.60,
    },
]


# ---------------------------------------------------------------------------
# CURRENT MODELLED WIND
# ---------------------------------------------------------------------------

def get_current_wind(
    lat: float,
    lon: float,
):
    """
    Fetch current modeled 10 m wind data from Open-Meteo.

    Returns:
        wind_direction_degrees,
        wind_speed

    Wind direction is treated using meteorological convention:
    direction FROM which wind is blowing.

    Returns (None, None) on failure.
    """

    try:

        params = {
            "latitude": lat,
            "longitude": lon,
            "current": (
                "wind_direction_10m,"
                "wind_speed_10m"
            ),
            "timezone": "Asia/Kolkata",
        }

        response = requests.get(
            WEATHER_URL,
            params=params,
            timeout=10,
        )

        response.raise_for_status()

        current = response.json().get(
            "current",
            {},
        )

        direction = current.get(
            "wind_direction_10m"
        )

        speed = current.get(
            "wind_speed_10m"
        )

        if direction is not None:
            direction = float(direction)

        if speed is not None:
            speed = float(speed)

        return direction, speed

    except (
        requests.exceptions.RequestException,
        ValueError,
        TypeError,
    ):

        return None, None


# ---------------------------------------------------------------------------
# GEOSPATIAL HELPERS
# ---------------------------------------------------------------------------

def _distance_km(
    lat1,
    lon1,
    lat2,
    lon2,
):

    radius = 6371.0

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    dlat = lat2 - lat1

    dlon = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(dlat / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin(dlon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a),
    )

    return radius * c


def _bearing(
    lat1,
    lon1,
    lat2,
    lon2,
):

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    dlon = math.radians(
        lon2 - lon1
    )

    y = (
        math.sin(dlon)
        * math.cos(lat2_rad)
    )

    x = (
        math.cos(lat1_rad)
        * math.sin(lat2_rad)
        -
        math.sin(lat1_rad)
        * math.cos(lat2_rad)
        * math.cos(dlon)
    )

    return (
        math.degrees(
            math.atan2(y, x)
        )
        + 360
    ) % 360


def _angular_difference(
    angle1,
    angle2,
):

    return abs(
        (
            angle1
            - angle2
            + 180
        )
        % 360
        - 180
    )


# ---------------------------------------------------------------------------
# SCREENING FACTORS
# ---------------------------------------------------------------------------

def _proximity_factor(
    distance_km,
):
    """
    Smooth distance decay.

    This is a heuristic screening function,
    not an atmospheric dispersion equation.
    """

    distance_km = max(
        0.0,
        distance_km,
    )

    return 1.0 / (
        1.0 + distance_km
    )


def _wind_factor(
    bearing_to_source,
    wind_from_deg,
):
    """
    Estimate directional relevance.

    If the direction from the ward TO the source is similar to the
    direction FROM which wind is blowing, the candidate is approximately
    upwind of the ward.

    Returns:
        wind_factor
        angular_difference
    """

    difference = (
        _angular_difference(
            bearing_to_source,
            wind_from_deg,
        )
    )

    alignment = (
        1.0
        + math.cos(
            math.radians(
                difference
            )
        )
    ) / 2.0

    # Preserve a small non-zero factor because this is only a
    # screening model and wind direction alone cannot prove zero influence.
    factor = (
        0.10
        + 0.90
        * alignment
    )

    return (
        factor,
        difference,
    )


def _influence_level(
    score,
):

    if score >= 70:
        return "High"

    if score >= 35:
        return "Medium"

    return "Low"


# ---------------------------------------------------------------------------
# LOCALISED SOURCE SCREENING
# ---------------------------------------------------------------------------

def analyze_ward(
    ward_lat,
    ward_lon,
    wind_from_deg,
):
    """
    Rank LOCALIZED candidate sources.

    Raw screening score:

        proximity
        x wind alignment
        x heuristic strength prior

    Scores are normalized relative to the strongest candidate.

    IMPORTANT:
    100 means "highest-ranked candidate in this candidate set".

    It does NOT mean:
        100% pollution contribution.
    """

    rows = []

    for source in (
        PUNE_LOCALISED_SOURCES
    ):

        distance = _distance_km(
            ward_lat,
            ward_lon,
            source["lat"],
            source["lon"],
        )

        bearing = _bearing(
            ward_lat,
            ward_lon,
            source["lat"],
            source["lon"],
        )

        proximity = (
            _proximity_factor(
                distance
            )
        )

        (
            wind_alignment,
            wind_difference,
        ) = _wind_factor(
            bearing,
            wind_from_deg,
        )

        raw_score = (
            proximity
            * wind_alignment
            * source[
                "strength_prior"
            ]
        )

        rows.append(
            {
                "name": source[
                    "name"
                ],

                "type": source[
                    "type"
                ],

                "distance_km": round(
                    distance,
                    2,
                ),

                "bearing_to_source_deg":
                    round(
                        bearing,
                        1,
                    ),

                "wind_difference_deg":
                    round(
                        wind_difference,
                        1,
                    ),

                "approximately_upwind":
                    (
                        wind_difference
                        < 90
                    ),

                # Backward-compatible alias.
                "upwind":
                    (
                        wind_difference
                        < 90
                    ),

                "proximity_factor":
                    round(
                        proximity,
                        4,
                    ),

                "wind_alignment_factor":
                    round(
                        wind_alignment,
                        4,
                    ),

                "strength_prior":
                    source[
                        "strength_prior"
                    ],

                "_raw_score":
                    raw_score,
            }
        )

    max_score = max(
        (
            row["_raw_score"]
            for row in rows
        ),
        default=0.0,
    )

    for row in rows:

        if max_score > 0:

            score = (
                row["_raw_score"]
                / max_score
                * 100
            )

        else:

            score = 0.0

        row[
            "influence_score"
        ] = round(
            score,
            1,
        )

        row[
            "influence_level"
        ] = _influence_level(
            score
        )

        del row[
            "_raw_score"
        ]

    return sorted(
        rows,
        key=lambda row:
            row[
                "influence_score"
            ],
        reverse=True,
    )


# ---------------------------------------------------------------------------
# CURRENT-WIND SCREENING
# ---------------------------------------------------------------------------

def analyze_ward_current(
    ward_lat,
    ward_lon,
):
    """
    Run localized candidate-source screening using current modeled wind.

    If current modeled wind is unavailable, no directional analysis is
    fabricated.

    This is intentionally different from the old implementation, which used
    a hard-coded 270-degree fallback. A fabricated fallback direction could
    materially change source rankings.
    """

    (
        wind_from,
        wind_speed,
    ) = get_current_wind(
        ward_lat,
        ward_lon,
    )

    if wind_from is None:

        return {
            "wind_available": False,

            "wind_from_deg": None,

            "wind_speed": None,

            "wind_source": (
                "Unavailable"
            ),

            "sources": [],

            "methodology": {
                "type": (
                    "localized_candidate_"
                    "source_screening"
                ),

                "status": (
                    "not_run_without_"
                    "current_wind"
                ),

                "is_source_apportionment":
                    False,

                "is_causal_attribution":
                    False,
            },
        }

    sources = analyze_ward(
        ward_lat,
        ward_lon,
        wind_from,
    )

    return {
        "wind_available": True,

        "wind_from_deg": round(
            wind_from,
            1,
        ),

        "wind_speed": (
            wind_speed
        ),

        "wind_source": (
            "Open-Meteo current "
            "modeled 10 m wind"
        ),

        "sources": sources,

        "methodology": {
            "type": (
                "localized_candidate_"
                "source_screening"
            ),

            "is_source_apportionment":
                False,

            "is_causal_attribution":
                False,

            "distributed_sources_included":
                False,

            "score_meaning": (
                "Relative screening rank "
                "among localized candidate "
                "sources represented in the "
                "prototype."
            ),

            "factors": [
                "geographic proximity",
                "current modeled wind alignment",
                "heuristic candidate strength prior",
            ],
        },
    }


# Backward-compatible function name.
# Existing code calling analyze_ward_live will still work.
def analyze_ward_live(
    ward_lat,
    ward_lon,
):
    return analyze_ward_current(
        ward_lat,
        ward_lon,
    )


# ---------------------------------------------------------------------------
# STANDALONE TEST
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    ward_name = (
        "Revenue Colony Shivajinagar"
    )

    ward_lat = 18.5308
    ward_lon = 73.8474

    print(
        "SENTINEL AI - "
        "LOCALIZED SOURCE SCREENING\n"
    )

    print(
        f"Ward: {ward_name}\n"
    )

    result = (
        analyze_ward_current(
            ward_lat,
            ward_lon,
        )
    )

    if not result[
        "wind_available"
    ]:

        print(
            "Current modeled wind "
            "unavailable."
        )

    else:

        print(
            "Current modeled wind "
            f"from: "
            f"{result['wind_from_deg']} "
            "degrees"
        )

        print(
            f"Wind speed: "
            f"{result['wind_speed']}"
        )

        print(
            "\nLocalized candidate "
            "source ranking:\n"
        )

        for source in (
            result[
                "sources"
            ][:5]
        ):

            direction = (
                "approximately upwind"
                if source[
                    "approximately_upwind"
                ]
                else
                "not currently upwind"
            )

            print(
                f"{source['influence_score']:>5.1f}/100  "
                f"{source['name']:<35} "
                f"{source['type']:<15} "
                f"{source['distance_km']:>5.1f} km  "
                f"{direction}"
            )

    print(
        "\nNOTE: Scores are relative "
        "localized-source screening "
        "scores, not pollution "
        "contribution percentages."
    )