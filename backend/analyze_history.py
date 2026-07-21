"""
analyze_history.py - Sentinel AI

Builds historical spatial-context indicators from historical composite-AQI
series for eight Pune monitoring / analysis locations.

PURPOSE
-------
This module does NOT predict current ward AQI.

Instead, it estimates whether each monitoring location historically tended
to experience higher or lower composite AQI relative to other simultaneously
reporting Pune monitoring locations.

For each location S and valid hour t:

    relative_ratio(t) =
        AQI_S(t)
        ---------------------------------
        mean(AQI of OTHER stations at t)

The station being evaluated is deliberately excluded from its own reference
(leave-one-out comparison).

The Historical Relative Burden Index is:

    median(relative_ratio(t))

over all valid paired hours.

INTERPRETATION
--------------
index > 1:
    The location historically tended to have higher composite AQI than the
    simultaneously reporting comparison stations.

index < 1:
    The location historically tended to have lower composite AQI than the
    simultaneously reporting comparison stations.

index ~= 1:
    The location historically tended to be near the comparison-station level.

IMPORTANT LIMITATIONS
---------------------
- Input data contain composite AQI, not pollutant concentrations.
- AQI is a nonlinear index and its dominant pollutant may change over time.
- This is historical spatial context, NOT current AQI.
- This is NOT a forecast.
- This is NOT official ward-level AQI.
- Monitoring locations are not automatically equivalent to administrative wards.
- Historical spatial relationships may not hold under current meteorology.

Run:

    python analyze_history.py

Output:

    historical_spatial_factors.json
"""

import csv
import json
import math
import os
import statistics
from collections import Counter


# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------

DATA_DIR = os.environ.get(
    "SENTINEL_DATA_DIR",
    ".",
)

# Require at least three OTHER reporting stations
# to create the leave-one-out reference.
MIN_OTHER_STATIONS = 3

# Minimum number of paired hourly comparisons
# required to produce a historical index.
MIN_PAIRS = 500


FILES = {

    "Bhosari":
        "bhosari.csv",

    "Hadapsar":
        "hadapsar.csv",

    "Katraj Dairy":
        "katraj_dairy.csv",

    "Mhada Colony":
        "mhada_colony.csv",

    "MIT Kothrud":
        "MIT_Kothrud.csv",

    "Revenue Colony Shivajinagar":
        "revenue_colony_shivajinagar.csv",

    "Savitribai Phule University":
        "savitribai_phule_university.csv",

    "Transport Nagar Nigdi":
        "transport_nagar_nigdi.csv",
}


MONTHS = [

    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
]


# ---------------------------------------------------------------------------
# PARSE HISTORICAL CSV
# ---------------------------------------------------------------------------

def parse_keyed(
    path: str,
) -> dict:
    """
    Parse one station CSV.

    Expected layout:
        year markers
        month blocks
        day rows
        24 hourly AQI columns

    Returns:

        {
            (year, month, day, hour): composite_aqi
        }

    Only finite positive AQI values are retained.
    """

    if not os.path.exists(
        path
    ):

        raise FileNotFoundError(
            f"Historical AQI file not found: {path}"
        )


    output = {}

    year = None
    month = None


    with open(
        path,
        newline="",
        encoding="utf-8-sig",
    ) as file:

        reader = csv.reader(
            file
        )


        for row in reader:

            if not row:

                continue


            first_cell = (
                row[0]
                .strip()
            )


            # ---------------------------------------------------------------
            # YEAR
            # ---------------------------------------------------------------

            if (
                first_cell.startswith(
                    "Year"
                )
                and len(row) > 1
            ):

                year_value = (
                    row[1]
                    .strip()
                )

                if year_value.isdigit():

                    year = int(
                        year_value
                    )

                continue


            # ---------------------------------------------------------------
            # MONTH
            # ---------------------------------------------------------------

            joined = ",".join(
                row
            ).lower()


            detected_month = None


            for (
                month_number,
                month_name,
            ) in enumerate(
                MONTHS,
                start=1,
            ):

                if month_name in joined:

                    detected_month = (
                        month_number
                    )

                    break


            if detected_month is not None:

                month = (
                    detected_month
                )


            # ---------------------------------------------------------------
            # DAY + HOURLY VALUES
            # ---------------------------------------------------------------

            if not (
                first_cell.isdigit()
                and year is not None
                and month is not None
            ):

                continue


            day = int(
                first_cell
            )


            if not (
                1 <= day <= 31
            ):

                continue


            for (
                hour,
                cell,
            ) in enumerate(
                row[1:25]
            ):

                cleaned = (
                    cell
                    .strip()
                    .strip('"')
                )


                try:

                    value = float(
                        cleaned
                    )

                except (
                    TypeError,
                    ValueError,
                ):

                    continue


                if not math.isfinite(
                    value
                ):

                    continue


                if value <= 0:

                    continue


                # CPCB AQI scale normally lies between 0 and 500.
                # Values above 500 are excluded from this historical
                # comparison because they may represent malformed or
                # exceptional source-file values requiring manual review.

                if value > 500:

                    continue


                key = (
                    year,
                    month,
                    day,
                    hour,
                )


                output[
                    key
                ] = value


    return output


# ---------------------------------------------------------------------------
# PERCENTILE HELPER
# ---------------------------------------------------------------------------

def percentile(
    values: list[float],
    p: float,
) -> float:
    """
    Linear-interpolated percentile.

    p must be between 0 and 1.
    """

    if not values:

        raise ValueError(
            "Cannot calculate percentile "
            "of an empty sequence."
        )


    ordered = sorted(
        values
    )


    if len(
        ordered
    ) == 1:

        return ordered[
            0
        ]


    position = (
        len(
            ordered
        )
        - 1
    ) * p


    lower_index = int(
        math.floor(
            position
        )
    )


    upper_index = int(
        math.ceil(
            position
        )
    )


    if (
        lower_index
        == upper_index
    ):

        return ordered[
            lower_index
        ]


    fraction = (
        position
        - lower_index
    )


    return (

        ordered[
            lower_index
        ]

        +

        (
            ordered[
                upper_index
            ]

            -

            ordered[
                lower_index
            ]
        )

        * fraction
    )


# ---------------------------------------------------------------------------
# INTERPRETATION
# ---------------------------------------------------------------------------

def burden_band(
    index: float,
) -> str:
    """
    Convert historical relative index into a simple qualitative band.

    These thresholds are prototype interpretation bands,
    NOT CPCB categories and NOT regulatory thresholds.
    """

    if index >= 1.25:

        return "Historically much higher"


    if index >= 1.10:

        return "Historically higher"


    if index >= 0.90:

        return "Historically near reference"


    if index >= 0.75:

        return "Historically lower"


    return "Historically much lower"


# ---------------------------------------------------------------------------
# BUILD HISTORICAL SPATIAL CONTEXT
# ---------------------------------------------------------------------------

def build():
    """
    Generate historical relative-burden indicators.

    Each location is compared against a leave-one-out
    mean of simultaneously reporting OTHER stations.
    """


    # -----------------------------------------------------------------------
    # LOAD ALL STATIONS
    # -----------------------------------------------------------------------

    stations = {}


    print(
        "Loading historical composite-AQI data...\n"
    )


    for (
        name,
        filename,
    ) in FILES.items():

        path = os.path.join(
            DATA_DIR,
            filename,
        )


        station_data = parse_keyed(
            path
        )


        stations[
            name
        ] = station_data


        print(

            f"  {name:<32} "

            f"{len(station_data):>7} "

            "valid hourly observations"
        )


    # -----------------------------------------------------------------------
    # ANALYSE EACH LOCATION
    # -----------------------------------------------------------------------

    locations = {}

    skipped = []


    for (
        target_name,
        target_data,
    ) in stations.items():


        hourly_ratios = []

        target_values = []

        reference_values = []

        valid_keys = []

        comparison_station_counts = []


        for (
            key,
            target_aqi,
        ) in target_data.items():


            # Leave-one-out reference:
            # target station is NOT included.

            other_values = [

                station_data[
                    key
                ]

                for (
                    other_name,
                    station_data,
                ) in stations.items()

                if (
                    other_name
                    != target_name
                    and key
                    in station_data
                )
            ]


            if len(
                other_values
            ) < MIN_OTHER_STATIONS:

                continue


            reference_aqi = statistics.mean(
                other_values
            )


            if reference_aqi <= 0:

                continue


            ratio = (
                target_aqi
                / reference_aqi
            )


            if not math.isfinite(
                ratio
            ):

                continue


            hourly_ratios.append(
                ratio
            )

            target_values.append(
                target_aqi
            )

            reference_values.append(
                reference_aqi
            )

            valid_keys.append(
                key
            )

            comparison_station_counts.append(
                len(
                    other_values
                )
            )


        # -------------------------------------------------------------------
        # SAMPLE REQUIREMENT
        # -------------------------------------------------------------------

        if len(
            hourly_ratios
        ) < MIN_PAIRS:

            skipped.append({

                "location":
                    target_name,

                "reason":
                    "too_few_valid_paired_hours",

                "n_paired_hours":
                    len(
                        hourly_ratios
                    ),
            })

            continue


        # -------------------------------------------------------------------
        # ROBUST HISTORICAL INDEX
        # -------------------------------------------------------------------

        median_ratio = statistics.median(
            hourly_ratios
        )


        mean_ratio = statistics.mean(
            hourly_ratios
        )


        q1 = percentile(
            hourly_ratios,
            0.25,
        )


        q3 = percentile(
            hourly_ratios,
            0.75,
        )


        iqr = (
            q3
            - q1
        )


        # -------------------------------------------------------------------
        # TEMPORAL COVERAGE
        # -------------------------------------------------------------------

        years = sorted(
            {
                key[
                    0
                ]
                for key
                in valid_keys
            }
        )


        year_month_pairs = sorted(
            {
                (
                    key[
                        0
                    ],
                    key[
                        1
                    ],
                )
                for key
                in valid_keys
            }
        )


        months_of_year = sorted(
            {
                key[
                    1
                ]
                for key
                in valid_keys
            }
        )


        year_counts = Counter(

            key[
                0
            ]

            for key
            in valid_keys
        )


        avg_comparison_stations = (
            statistics.mean(
                comparison_station_counts
            )
        )


        # -------------------------------------------------------------------
        # STORE RESULT
        # -------------------------------------------------------------------

        locations[
            target_name
        ] = {

            # Primary robust indicator
            "historical_relative_burden_index":
                round(
                    median_ratio,
                    3,
                ),

            "historical_relative_burden_band":
                burden_band(
                    median_ratio
                ),

            # Diagnostics
            "median_hourly_ratio":
                round(
                    median_ratio,
                    3,
                ),

            "mean_hourly_ratio":
                round(
                    mean_ratio,
                    3,
                ),

            "ratio_q1":
                round(
                    q1,
                    3,
                ),

            "ratio_q3":
                round(
                    q3,
                    3,
                ),

            "ratio_iqr":
                round(
                    iqr,
                    3,
                ),

            "median_location_aqi":
                round(
                    statistics.median(
                        target_values
                    ),
                    1,
                ),

            "median_reference_aqi":
                round(
                    statistics.median(
                        reference_values
                    ),
                    1,
                ),

            "n_paired_hours":
                len(
                    hourly_ratios
                ),

            "average_other_stations_reporting":
                round(
                    avg_comparison_stations,
                    2,
                ),

            "years_covered":
                years,

            "year_months_covered":
                len(
                    year_month_pairs
                ),

            "months_of_year_covered":
                months_of_year,

            "paired_hours_by_year": {

                str(
                    year
                ):
                    count

                for (
                    year,
                    count,
                ) in sorted(
                    year_counts.items()
                )
            },

            "data_type":
                "historical_composite_aqi",

            "is_current_aqi":
                False,

            "is_forecast":
                False,

            "is_official_ward_aqi":
                False,
        }


    # -----------------------------------------------------------------------
    # SORT HIGHEST HISTORICAL INDEX FIRST
    # -----------------------------------------------------------------------

    sorted_locations = dict(

        sorted(

            locations.items(),

            key=lambda item:
                -item[
                    1
                ][
                    "historical_relative_burden_index"
                ],
        )
    )


    # -----------------------------------------------------------------------
    # FINAL OUTPUT
    # -----------------------------------------------------------------------

    output = {

        "_meta": {

            "description":
                (
                    "Historical relative composite-AQI burden "
                    "indicators for Sentinel AI analysis locations."
                ),

            "method":
                (
                    "Median of paired hourly ratios: target-location "
                    "composite AQI divided by the mean composite AQI "
                    "of at least three simultaneously reporting OTHER "
                    "monitoring locations."
                ),

            "reference_method":
                "leave_one_out_simultaneous_station_mean",

            "primary_statistic":
                "median_hourly_ratio",

            "minimum_other_stations":
                MIN_OTHER_STATIONS,

            "minimum_paired_hours":
                MIN_PAIRS,

            "number_of_input_locations":
                len(
                    stations
                ),

            "number_of_output_locations":
                len(
                    sorted_locations
                ),

            "limitations": [

                (
                    "Input series contain composite AQI rather than "
                    "pollutant-specific concentrations."
                ),

                (
                    "Composite AQI is nonlinear and its dominant "
                    "pollutant may vary over time."
                ),

                (
                    "Historical relative burden does not represent "
                    "current local AQI."
                ),

                (
                    "Historical relative burden is not a forecast."
                ),

                (
                    "Monitoring or analysis locations are not "
                    "automatically equivalent to administrative wards."
                ),

                (
                    "Historical spatial relationships may change "
                    "under different meteorological and emissions "
                    "conditions."
                ),
            ],

            "interpretation":
                (
                    "Values above 1 indicate historically higher "
                    "composite AQI relative to simultaneously reporting "
                    "comparison locations; values below 1 indicate "
                    "historically lower relative composite AQI."
                ),
        },


        "locations":
            sorted_locations,


        "skipped":
            skipped,
    }


    # -----------------------------------------------------------------------
    # WRITE OUTPUT
    # -----------------------------------------------------------------------

    output_path = os.path.join(

        DATA_DIR,

        "historical_spatial_factors.json",
    )


    with open(

        output_path,

        "w",

        encoding="utf-8",

    ) as file:

        json.dump(

            output,

            file,

            indent=2,

            ensure_ascii=False,
        )


    # -----------------------------------------------------------------------
    # CONSOLE SUMMARY
    # -----------------------------------------------------------------------

    print(
        "\nSENTINEL AI - "
        "HISTORICAL SPATIAL CONTEXT\n"
    )


    for (
        name,
        result,
    ) in sorted_locations.items():


        print(

            f"{name:<32} "

            f"index="
            f"{result['historical_relative_burden_index']:.3f}  "

            f"pairs="
            f"{result['n_paired_hours']:<6}  "

            f"{result['historical_relative_burden_band']}"
        )


    if skipped:

        print(
            "\nSkipped locations:"
        )


        for item in skipped:

            print(

                f"  {item['location']} "

                f"({item['n_paired_hours']} paired hours)"
            )


    print(

        "\nNOTE: These values represent historical "
        "relative composite-AQI patterns. They are not "
        "current AQI estimates or forecasts."
    )


    print(

        f"\nWrote: {output_path}"
    )


# ---------------------------------------------------------------------------
# ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":

    build()