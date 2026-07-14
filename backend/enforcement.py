"""
enforcement.py  (Sentinel AI)

PS Item 3 -- Enforcement Intelligence & Prioritisation:
"generates prioritised, evidence-backed enforcement action recommendations
for municipal and pollution control authorities."

METHOD
For a given ward, run every intervention lever through the existing
simulate() engine at a standard enforcement intensity, rank levers by AQI
impact, and return an ordered action plan. Every number traces to the MPCB
Pune Source Apportionment Study (Dec 2021) via intervention.py -- nothing
here invents data; this module only *ranks* what the simulator computes.

Also flags NEGATIVE recommendations (levers NOT worth enforcement effort),
which is where the counter-intuitive insight lives: industry throttling in
Pune yields <1% AQI improvement because industry is only 1.25% of PM.
"""

from intervention import INTERVENTIONS, simulate

# Standard enforcement intensity used for ranking. 50% is a realistic
# "strong municipal action" level (e.g. odd-even ~ halves traffic).
RANKING_INTENSITY = 0.50

# Concrete municipal actions per lever -- what an inspector actually does.
ACTIONS = {
    "road_dust_control": [
        "Deploy mechanised sweepers + water sprinklers on arterial roads",
        "Enforce paving/compaction of unpaved shoulders and open plots",
    ],
    "traffic_reduction": [
        "Odd-even or heavy-vehicle time restrictions in the ward",
        "Reroute freight; enforce PUC checks at ward entry points",
    ],
    "construction_halt": [
        "Inspect active construction sites for dust-barrier compliance",
        "Suspend non-compliant sites; enforce covered material transport",
    ],
    "clean_cooking": [
        "LPG-subsidy outreach in slum pockets; curb open solid-fuel use",
        "Inspect hotel/bakery chimneys for fuel compliance",
    ],
    "industrial_throttle": [
        "Stack-emission audit of registered units",
    ],
}

# Below this AQI-improvement (%) at ranking intensity, a lever is flagged
# as NOT worth enforcement effort in this ward.
LOW_IMPACT_THRESHOLD_PCT = 3.0


def recommend(ward: str, base_aqi: float) -> dict:
    """
    Prioritised enforcement plan for one ward.

    Returns levers ranked by AQI impact at RANKING_INTENSITY, each with
    projected AQI, PM2.5 saved, and concrete municipal actions -- plus a
    'not_recommended' list for low-impact levers (evidence-backed negatives).
    """
    ranked = []
    for key, spec in INTERVENTIONS.items():
        r = simulate(ward, base_aqi, {key: RANKING_INTENSITY})
        pm_saved = round(sum(b["pm25_saved"] for b in r["breakdown"]), 2)
        ranked.append({
            "lever": key,
            "label": spec["label"],
            "evidence": spec["note"],
            "projected_aqi": r["new_aqi"],
            "aqi_drop": r["aqi_drop"],
            "pct_drop": r["pct_drop"],
            "pm25_saved_ugm3": pm_saved,
            "actions": ACTIONS.get(key, []),
        })

    ranked.sort(key=lambda x: -x["pct_drop"])
    recommended = [r for r in ranked if r["pct_drop"] >= LOW_IMPACT_THRESHOLD_PCT]
    not_recommended = [r for r in ranked if r["pct_drop"] < LOW_IMPACT_THRESHOLD_PCT]

    for i, r in enumerate(recommended, 1):
        r["priority"] = i

    return {
        "ward": ward,
        "base_aqi": round(base_aqi, 1),
        "ranking_intensity_pct": RANKING_INTENSITY * 100,
        "recommended": recommended,
        "not_recommended": [
            {**r, "reason": f"Only {r['pct_drop']}% AQI improvement at "
                            f"{int(RANKING_INTENSITY*100)}% enforcement -- "
                            "effort better spent on higher-impact levers."}
            for r in not_recommended
        ],
        "methodology": "Levers ranked by simulated AQI impact at a standard "
                       "50% enforcement intensity. Source shares: MPCB Pune "
                       "SA&EI Study (Dec 2021). Ward baseline: live city AQI "
                       "x ward alpha (CPCB station history 2017-2023).",
    }


if __name__ == "__main__":
    plan = recommend("Revenue Colony Shivajinagar", 138.6)
    print(f"ENFORCEMENT PLAN -- {plan['ward']} (AQI {plan['base_aqi']})\n")
    for r in plan["recommended"]:
        print(f"  #{r['priority']} {r['label']}")
        print(f"      -> AQI {plan['base_aqi']} => {r['projected_aqi']} "
              f"(-{r['pct_drop']}%), saves {r['pm25_saved_ugm3']} ug/m3 PM2.5")
        for a in r["actions"]:
            print(f"      * {a}")
    print("\n  NOT WORTH ENFORCEMENT EFFORT:")
    for r in plan["not_recommended"]:
        print(f"    x {r['label']} -- {r['reason']}")
