"""
Sentinel AI - Indian AQI Sub-Index Calculator

PURPOSE
-------
Calculates Indian CPCB-style pollutant sub-indices from concentrations that
have ALREADY been aggregated over the required temporal window.

IMPORTANT
---------
This module does NOT fetch data and does NOT perform temporal averaging.

The caller is responsible for supplying AQI-ready concentrations.

Sentinel currently uses:
    PM2.5 : trailing 24-hour modeled mean
    PM10  : trailing 24-hour modeled mean
    NO2   : trailing 24-hour modeled mean
    SO2   : trailing 24-hour modeled mean
    OZONE : trailing 8-hour modeled mean
    CO    : trailing 8-hour modeled mean

Because Sentinel currently uses CAMS modeled concentrations rather than
direct CPCB monitoring-station observations, outputs must be described as
modeled CPCB-method AQI context, NOT official CPCB AQI observations.

Units:
    PM2.5, PM10, NO2, SO2, OZONE, NH3 -> µg/m³
    CO -> mg/m³
"""

import math


BREAKPOINTS = {
    "PM2.5": [
        (0, 30, 0, 50),
        (31, 60, 51, 100),
        (61, 90, 101, 200),
        (91, 120, 201, 300),
        (121, 250, 301, 400),
        (251, 500, 401, 500),
    ],

    "PM10": [
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 250, 101, 200),
        (251, 350, 201, 300),
        (351, 430, 301, 400),
        (431, 600, 401, 500),
    ],

    "NO2": [
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 180, 101, 200),
        (181, 280, 201, 300),
        (281, 400, 301, 400),
        (401, 1000, 401, 500),
    ],

    "SO2": [
        (0, 40, 0, 50),
        (41, 80, 51, 100),
        (81, 380, 101, 200),
        (381, 800, 201, 300),
        (801, 1600, 301, 400),
        (1601, 2000, 401, 500),
    ],

    "CO": [
        (0, 1.0, 0, 50),
        (1.1, 2.0, 51, 100),
        (2.1, 10.0, 101, 200),
        (10.1, 17.0, 201, 300),
        (17.1, 34.0, 301, 400),
        (34.1, 50.0, 401, 500),
    ],

    "OZONE": [
        (0, 50, 0, 50),
        (51, 100, 51, 100),
        (101, 168, 101, 200),
        (169, 208, 201, 300),
        (209, 748, 301, 400),
        (749, 1000, 401, 500),
    ],

    "NH3": [
        (0, 200, 0, 50),
        (201, 400, 51, 100),
        (401, 800, 101, 200),
        (801, 1200, 201, 300),
        (1201, 1800, 301, 400),
        (1801, 2000, 401, 500),
    ],
}


CATEGORIES = [
    (0, 50, "Good"),
    (51, 100, "Satisfactory"),
    (101, 200, "Moderate"),
    (201, 300, "Poor"),
    (301, 400, "Very Poor"),
    (401, 500, "Severe"),
]


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


def _normalize_concentration(pollutant, concentration):
    """
    Normalize concentrations to the precision used by the breakpoint tables.

    CPCB breakpoint tables are represented with integer concentrations for
    pollutants other than CO and one decimal place for CO.

    This prevents continuous model values such as 30.6 from falling into the
    apparent numerical gap between breakpoint labels 30 and 31.
    """

    concentration = _safe_float(concentration)

    if concentration is None:
        return None

    if pollutant == "CO":
        return round(concentration, 1)

    return round(concentration)


def sub_index(pollutant, concentration):
    """
    Calculate one pollutant sub-index.

    Returns None if the pollutant or concentration is invalid.
    """

    if pollutant not in BREAKPOINTS:
        return None

    concentration = _normalize_concentration(
        pollutant,
        concentration,
    )

    if concentration is None:
        return None

    bands = BREAKPOINTS[pollutant]

    # Above highest represented concentration -> cap at AQI 500.
    if concentration > bands[-1][1]:
        return 500

    for c_low, c_high, i_low, i_high in bands:

        if c_low <= concentration <= c_high:

            if c_high == c_low:
                return int(i_high)

            value = (
                (i_high - i_low)
                / (c_high - c_low)
                * (concentration - c_low)
                + i_low
            )

            return int(round(value))

    # Defensive fallback.
    #
    # After normalization there should normally be no meaningful gap.
    # If a value somehow lands between represented breakpoint bands,
    # interpolate using the nearest surrounding endpoints rather than
    # incorrectly returning AQI 500.

    for index in range(len(bands) - 1):

        left = bands[index]
        right = bands[index + 1]

        left_high = left[1]
        left_index = left[3]

        right_low = right[0]
        right_index = right[2]

        if left_high < concentration < right_low:

            fraction = (
                (concentration - left_high)
                / (right_low - left_high)
            )

            value = (
                left_index
                + fraction
                * (right_index - left_index)
            )

            return int(round(value))

    return None


def category(aqi):
    """
    Return Indian AQI category.

    Accepts integer or decimal AQI values.
    Decimal AQI estimates are classified using the continuous
    CPCB category boundaries.
    """

    if aqi is None:
        return "Unknown"

    try:
        aqi = float(aqi)
    except (TypeError, ValueError):
        return "Unknown"

    if not math.isfinite(aqi):
        return "Unknown"

    if aqi < 0:
        return "Unknown"

    if aqi <= 50:
        return "Good"

    if aqi <= 100:
        return "Satisfactory"

    if aqi <= 200:
        return "Moderate"

    if aqi <= 300:
        return "Poor"

    if aqi <= 400:
        return "Very Poor"

    return "Severe"


def calculate_aqi(
    readings,
    require_min_pollutants=True,
):
    """
    Calculate overall modeled CPCB-method AQI context.

    Parameters
    ----------
    readings:
        Dictionary containing AQI-ready temporally aggregated concentrations.

        Example:

        {
            "PM2.5": 42.1,
            "PM10": 68.4,
            "NO2": 24.5,
            "SO2": 8.2,
            "OZONE": 37.1,
            "CO": 0.7
        }

    require_min_pollutants:
        If True, require at least 3 valid pollutant sub-indices and at least
        one particulate pollutant (PM2.5 or PM10).

    Returns
    -------
    Dictionary with:
        aqi
        category
        dominant
        sub_indices
        valid_pollutant_count
        has_pm
        sufficient_data
    """

    if not isinstance(readings, dict):
        readings = {}

    sub_indices = {}

    for pollutant, concentration in readings.items():

        if pollutant not in BREAKPOINTS:
            continue

        value = sub_index(
            pollutant,
            concentration,
        )

        if value is not None:
            sub_indices[pollutant] = value

    has_pm = (
        "PM2.5" in sub_indices
        or "PM10" in sub_indices
    )

    valid_count = len(sub_indices)

    sufficient_data = (
        valid_count >= 3
        and has_pm
    )

    if (
        require_min_pollutants
        and not sufficient_data
    ):
        return {
            "aqi": None,
            "category": "Insufficient data",
            "dominant": None,
            "sub_indices": sub_indices,
            "valid_pollutant_count": valid_count,
            "has_pm": has_pm,
            "sufficient_data": False,
        }

    if not sub_indices:
        return {
            "aqi": None,
            "category": "Insufficient data",
            "dominant": None,
            "sub_indices": {},
            "valid_pollutant_count": 0,
            "has_pm": False,
            "sufficient_data": False,
        }

    dominant = max(
        sub_indices,
        key=sub_indices.get,
    )

    overall = sub_indices[dominant]

    return {
        "aqi": overall,
        "category": category(overall),
        "dominant": dominant,
        "sub_indices": sub_indices,
        "valid_pollutant_count": valid_count,
        "has_pm": has_pm,
        "sufficient_data": sufficient_data,
    }


if __name__ == "__main__":

    # ---------------------------------------------------------
    # BASIC BREAKPOINT TESTS
    # ---------------------------------------------------------

    assert sub_index("PM2.5", 31) == 51
    assert sub_index("PM2.5", 60) == 100
    assert sub_index("PM2.5", 45) == 75

    assert sub_index("PM10", 50) == 50
    assert sub_index("PM10", 51) == 51

    assert sub_index("PM2.5", None) is None
    assert sub_index("PM2.5", -1) is None
    assert sub_index("INVALID", 50) is None

    # Decimal values must not accidentally become AQI 500.
    assert sub_index("PM2.5", 30.4) != 500
    assert sub_index("PM2.5", 30.5) != 500
    assert sub_index("PM10", 50.5) != 500
    assert sub_index("NO2", 40.5) != 500

    print("AQI calculator basic tests passed.")

    sample = {
        "PM2.5": 75.0,
        "PM10": 130.0,
        "NO2": 35.0,
        "SO2": 10.0,
        "OZONE": 40.0,
        "CO": 0.8,
    }

    result = calculate_aqi(sample)

    print("\nSample AQI-ready concentrations:")
    print(sample)

    print("\nResult:")
    print(result)