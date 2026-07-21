// ============================================================
// SENTINEL AI — SHARED FRONTEND TYPES & HELPERS
// ============================================================

export type PollutantAggregation = {
  value?: number | null;
  raw_value?: number | null;
  raw_unit?: string | null;
  calculator_value?: number | null;
  calculator_unit?: string | null;

  api_timesteps_available?: number | null;
  api_timesteps_required?: number | null;

  window_hours?: number | null;
  complete_enough?: boolean;

  window_start?: string | null;
  window_end?: string | null;
};


export type Ward = {
  // Location
  name: string;
  lat: number;
  lon: number;

  // Model grid
  model_lat?: number | null;
  model_lon?: number | null;
  model_elevation?: number | null;

  // AQI
  aqi?: number | null;
  base_modeled_aqi?: number | null;
  category?: string | null;
  dominant?: string | null;

  sub_indices?: Record<
    string,
    number | null
  >;

  aqi_sufficient_data?: boolean;
  valid_pollutant_count?: number;

  // Pollutants
  pm25?: number | null;
  pm10?: number | null;
  no2?: number | null;
  so2?: number | null;
  ozone?: number | null;
  co?: number | null;

  pollutant_aggregation?: Record<
    string,
    PollutantAggregation
  >;

  // Historical spatial adjustment
  historical_spatial_factor?: number | null;

  historical_factor_role?: string | null;

  historical_factor_applied_to_current_aqi?: boolean;

  // Time / freshness
  reading_time?: string | null;
  aqi_context_time?: string | null;
  latest_model_time?: string | null;

  data_age_hours?: number | null;

  freshness_status?: string | null;

  freshness_threshold_hours?: number | null;
  stale_cutoff_hours?: number | null;

  data_fresh?: boolean;
  data_usable?: boolean;
  data_available?: boolean;
  is_current_context?: boolean;

  // Legacy compatibility
  is_live?: boolean;

  // Provenance
  value_type?: string | null;
  observed?: boolean;
  official_cpcb_aqi?: boolean;

  source?: string | null;

  provenance?: Record<
    string,
    unknown
  >;

  aqi_method?: Record<
    string,
    unknown
  >;

  error?: string | null;
};


export type AqiResponse = {
  locations: Ward[];

  generated_at?: string | null;

  source?: string | null;

  methodology?: Record<
    string,
    unknown
  >;

  [key: string]: unknown;
};


// ============================================================
// WARD VALIDITY
// ============================================================

export function isUsableCurrentWard(
  ward: Ward
): boolean {
  return (
    ward.aqi !== null &&
    ward.aqi !== undefined &&
    Number.isFinite(ward.aqi) &&

    ward.data_available === true &&
    ward.data_usable === true &&
    ward.data_fresh === true &&
    ward.is_current_context === true
  );
}


// ============================================================
// AQI CATEGORY COLORS
// ============================================================

export function categoryColor(
  category?: string | null
): string {
  const normalized =
    category
      ?.trim()
      .toLowerCase();

  switch (normalized) {
    case "good":
      return "#22c55e";

    case "satisfactory":
      return "#84cc16";

    case "moderate":
      return "#eab308";

    case "poor":
      return "#f97316";

    case "very poor":
      return "#ef4444";

    case "severe":
      return "#991b1b";

    default:
      return "#64748b";
  }
}


// ============================================================
// NUMBER FORMATTING
// ============================================================

export function formatNumber(
  value: number | null | undefined,
  digits = 1
): string {
  if (
    value === null ||
    value === undefined ||
    !Number.isFinite(value)
  ) {
    return "—";
  }

  return value.toFixed(digits);
}


// ============================================================
// CONTEXT TIME FORMATTING
// ============================================================

export function formatContextTime(
  value?: string | null
): string {
  if (!value) {
    return "Unavailable";
  }

  const date =
    new Date(value);

  if (
    Number.isNaN(
      date.getTime()
    )
  ) {
    return value;
  }

  return date.toLocaleString(
    "en-IN",
    {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
      hour12: true,
    }
  );
}