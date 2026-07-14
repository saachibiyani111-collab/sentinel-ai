"""
intervention.py  (Sentinel AI)

"What-if" intervention simulator: shows how a ward's AQI would change if the
city cut emissions from a given source.

METHOD — source-apportionment wedge model
Split PM into source "wedges" using Pune's OWN published emission inventory,
then scale each wedge by the reduction the user applies:

    PM_new = PM_base * SUM_over_sources( share_s * (1 - reduction_s) )

Then convert PM back to AQI using the CPCB breakpoint scale.

SOURCE SHARES — from the MPCB "Air Quality Assessment, Emission Inventory &
Source Apportionment Study for Pune City" (R3, Dec 2021):
  - Vehicles contribute 18% of PM (of which 65% 2-wheelers, 15% cars, 13% autos)
  - Domestic fuel burning (incl. solid fuel): 7.5%
  - Hotels & bakeries: 3%
  - Industry: 1.25% (confined industrial areas, few polluting units)
  - The remaining balance is dominated by road & construction dust, which
    other Indian-city inventories consistently find to be the largest PM wedge.
This is a FIRST-ORDER LINEAR model. It deliberately ignores secondary aerosol
chemistry, meteorology, and cross-ward transport -- stated openly rather than
dressed up as a chemical-transport model.

EVERY NUMBER IN THIS FILE IS CITABLE. The source shares come from MPCB's
published Pune study. We deliberately do NOT invent per-ward source mixes,
because no ward-level apportionment study exists for Pune. Wards differ in
their absolute AQI (via alpha, from real CPCB station history), not in their
assumed source mix.
"""

from dataclasses import dataclass

# --- CPCB AQI breakpoints for PM2.5 (India National AQI) ---
# (C_low, C_high, I_low, I_high)
PM25_BREAKPOINTS = [
    (0.0, 30.0, 0, 50),
    (30.0, 60.0, 51, 100),
    (60.0, 90.0, 101, 200),
    (90.0, 120.0, 201, 300),
    (120.0, 250.0, 301, 400),
    (250.0, 500.0, 401, 500),
]

# --- City-wide PM source shares (MPCB Pune SA & EI Study, R3 Dec 2021) ---
# Exact published figures:
#   road dust 61%  | vehicles 18%  | domestic & slum fuel 7.5%
#   construction & brick kilns 4.5%  | hotels & bakeries 3%  | industry 1.25%
# These sum to 95.25%; the residual 4.75% is grouped as "other"
# (secondary aerosol, open waste burning, long-range transport).
# Re-confirmed as still current by Respirer Living Sciences' 2021-2024 PM10
# trend analysis (Apr 2025), which names construction, road dust and vehicular
# congestion as Pune's continuing dominant sources.
CITY_SHARES = {
    "road_dust":    0.61,    # MPCB: highest single contributor
    "vehicles":     0.18,    # MPCB: 18% (65% 2-wheelers, 15% cars, 13% autos)
    "domestic":     0.075,   # MPCB: domestic + slum fuel usage
    "construction": 0.045,   # MPCB: construction activity + brick kilns
    "hotels":       0.03,    # MPCB: hotels & bakeries
    "industry":     0.0125,  # MPCB: only 1.25% - confined industrial areas
    "other":        0.0475,  # residual: secondary aerosol, waste burning, transport
}

# --- Ward source profiles ---
# DELIBERATELY EMPTY.
#
# There is NO published ward-level source-apportionment study for Pune. Any
# per-ward multiplier (e.g. "Bhosari has 4x the industry share") would be an
# invented number we could not cite or defend. So every ward uses the city-wide
# MPCB shares above.
#
# Wards still differ in their ABSOLUTE AQI, because each ward's baseline comes
# from its own alpha factor, derived from that ward's real CPCB station history
# (see analyze_history.py). What we do NOT claim is a different source MIX per
# ward, because no data supports that.
#
# If a ward-level apportionment study is ever published, add its shares here.
WARD_PROFILES: dict[str, dict] = {}

# --- Interventions the user can apply, mapped to the wedges they cut ---
INTERVENTIONS = {
    "traffic_reduction": {
        "label": "Traffic reduction (odd-even / vehicle curbs)",
        "affects": ["vehicles"],
        "note": "MPCB: vehicles = 18% of Pune's PM; 65% of that is two-wheelers.",
    },
    "road_dust_control": {
        "label": "Road dust suppression (sweeping, water spraying, paving)",
        "affects": ["road_dust"],
        "note": "MPCB: road dust is Pune's LARGEST PM source at 61%.",
    },
    "construction_halt": {
        "label": "Construction halt + brick kiln curbs",
        "affects": ["construction"],
        "note": "MPCB: construction activity + brick kilns = 4.5% of PM.",
    },
    "industrial_throttle": {
        "label": "Industrial emission throttle",
        "affects": ["industry"],
        "note": "MPCB: industry is only 1.25% city-wide -- a weak lever in Pune.",
    },
    "clean_cooking": {
        "label": "Clean cooking fuel (LPG/electric) + hotel/bakery curbs",
        "affects": ["domestic", "hotels"],
        "note": "Domestic & slum fuel 7.5% + hotels/bakeries 3% of PM.",
    },
}


def aqi_from_pm25(pm25: float) -> float:
    """CPCB National AQI from a PM2.5 concentration (ug/m3)."""
    pm25 = max(0.0, pm25)
    for c_lo, c_hi, i_lo, i_hi in PM25_BREAKPOINTS:
        if c_lo <= pm25 <= c_hi:
            return round(i_lo + (i_hi - i_lo) * (pm25 - c_lo) / (c_hi - c_lo), 1)
    return 500.0


def pm25_from_aqi(aqi: float) -> float:
    """Inverse: PM2.5 concentration from a CPCB AQI value."""
    aqi = max(0.0, min(500.0, aqi))
    for c_lo, c_hi, i_lo, i_hi in PM25_BREAKPOINTS:
        if i_lo <= aqi <= i_hi:
            return round(c_lo + (c_hi - c_lo) * (aqi - i_lo) / (i_hi - i_lo), 2)
    return 500.0


def ward_shares(ward: str) -> dict:
    """City shares adjusted by the ward's profile, renormalised to sum to 1."""
    profile = WARD_PROFILES.get(ward, {})
    raw = {src: CITY_SHARES[src] * profile.get(src, 1.0) for src in CITY_SHARES}
    total = sum(raw.values())
    return {src: v / total for src, v in raw.items()}


def simulate(ward: str, base_aqi: float, reductions: dict) -> dict:
    """
    Apply interventions to one ward.

    Args:
        ward:       ward name (must match WARD_PROFILES / ward_bias factors)
        base_aqi:   the ward's current AQI (from ward_bias / live feed)
        reductions: {intervention_key: fraction 0.0-1.0}
                    e.g. {"traffic_reduction": 0.30} = cut traffic 30%

    Returns dict with before/after AQI, PM2.5, absolute + % drop, and a
    per-source breakdown so the UI can show WHERE the gain came from.
    """
    shares = ward_shares(ward)

    # Convert each intervention into a per-source cut fraction
    source_cut = {src: 0.0 for src in CITY_SHARES}
    for key, frac in (reductions or {}).items():
        spec = INTERVENTIONS.get(key)
        if not spec:
            continue
        frac = max(0.0, min(1.0, float(frac)))
        for src in spec["affects"]:
            # Multiple interventions hitting one source: take the strongest
            source_cut[src] = max(source_cut[src], frac)

    base_pm = pm25_from_aqi(base_aqi)

    # Wedge model: PM_new = PM_base * SUM(share * (1 - cut))
    retained = sum(shares[src] * (1.0 - source_cut[src]) for src in shares)
    new_pm = base_pm * retained
    new_aqi = aqi_from_pm25(new_pm)

    breakdown = []
    for src in sorted(shares, key=lambda s: -shares[s]):
        pm_before = base_pm * shares[src]
        pm_after = pm_before * (1.0 - source_cut[src])
        breakdown.append({
            "source": src,
            "share_pct": round(shares[src] * 100, 1),
            "pm25_before": round(pm_before, 2),
            "pm25_after": round(pm_after, 2),
            "pm25_saved": round(pm_before - pm_after, 2),
            "cut_applied_pct": round(source_cut[src] * 100, 1),
        })

    drop = round(base_aqi - new_aqi, 1)
    return {
        "ward": ward,
        "base_aqi": round(base_aqi, 1),
        "new_aqi": new_aqi,
        "aqi_drop": drop,
        "pct_drop": round(100 * drop / base_aqi, 1) if base_aqi else 0.0,
        "base_pm25": base_pm,
        "new_pm25": round(new_pm, 2),
        "reductions": reductions or {},
        "breakdown": breakdown,
    }


def simulate_all(ward_aqis: dict, reductions: dict) -> list[dict]:
    """Run the same intervention across every ward. ward_aqis = {ward: aqi}."""
    return [simulate(w, aqi, reductions) for w, aqi in ward_aqis.items()]


def list_interventions() -> list[dict]:
    """Intervention catalogue for the frontend to render sliders."""
    return [{"key": k, **v} for k, v in INTERVENTIONS.items()]


if __name__ == "__main__":
    print("SENTINEL AI - Intervention Simulator\n")

    # Scenario: Shivajinagar at AQI 138.6, cut traffic 30%
    r = simulate("Revenue Colony Shivajinagar", 138.6, {"traffic_reduction": 0.30})
    print(f"Ward: {r['ward']}")
    print(f"  Cut traffic 30%  ->  AQI {r['base_aqi']} -> {r['new_aqi']} "
          f"(down {r['aqi_drop']}, -{r['pct_drop']}%)")
    print(f"  PM2.5: {r['base_pm25']} -> {r['new_pm25']} ug/m3\n")
    print("  Where the reduction came from:")
    for b in r["breakdown"]:
        if b["pm25_saved"] > 0:
            print(f"    {b['source']:<12} {b['share_pct']:>5}% of PM  "
                  f"saved {b['pm25_saved']} ug/m3")

    # Scenario: Bhosari (industrial ward) - throttle industry
    print()
    r2 = simulate("Bhosari", 86.8, {"industrial_throttle": 0.50})
    print(f"Ward: {r2['ward']}")
    print(f"  Throttle industry 50%  ->  AQI {r2['base_aqi']} -> {r2['new_aqi']} "
          f"(-{r2['pct_drop']}%)")

    # Combined scenario
    print()
    r3 = simulate("Revenue Colony Shivajinagar", 138.6, {
        "traffic_reduction": 0.40,
        "road_dust_control": 0.50,
    })
    print(f"Ward: {r3['ward']}")
    print(f"  Traffic -40% + road dust -50%  ->  AQI {r3['base_aqi']} -> {r3['new_aqi']} "
          f"(-{r3['pct_drop']}%)")
