"use client";

import {
  useCallback,
  useEffect,
  useState,
} from "react";


type Lever = {
  key: string;
  label: string;
  affects?: string[];
  note?: string;
};


type BaselineWard = {
  name: string;
  lat: number | null;
  lon: number | null;
  aqi: number | null;
};


type BreakdownItem = {
  source: string;
  source_weight_pct: number;
  assumed_source_reduction_pct: number;
  weighted_burden_reduction_pct: number;
};


type WardScenarioResult = {
  ward: string;

  base_aqi?: number | null;
  current_aqi_context?: number | null;

  new_aqi?: null;
  aqi_drop?: null;
  pct_drop?: null;

  baseline_burden_index: number;
  remaining_burden_index: number;
  estimated_burden_reduction_pct: number;

  reductions?: Record<string, number>;

  breakdown?: BreakdownItem[];

  lat?: number | null;
  lon?: number | null;

  aqi_context_source?: string;
  aqi_context_reading_time?: string | null;
  aqi_context_method?: string;

  model?: {
    type?: string;
    output?: string;
    is_aqi_forecast?: boolean;
    is_emission_measurement?: boolean;
    limitations?: string[];
  };
};


type SimulateAllResponse = {
  wards?: WardScenarioResult[];
  results?: WardScenarioResult[];

  summary?: {
    average_burden_reduction_pct?: number;
    avg_burden_reduction_pct?: number;

    average_remaining_burden_index?: number;
    avg_remaining_burden_index?: number;

    best_ward?: string | null;
  };

  model?: {
    type?: string;
    output?: string;
    is_aqi_forecast?: boolean;
    is_emission_measurement?: boolean;
    limitations?: string[];
  };

  disclaimer?: string;
};


type Props = {
  wards: BaselineWard[];

  onResult?: (
    result: SimulateAllResponse | null
  ) => void;
};


const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://localhost:8000";


function formatNumber(
  value: number | null | undefined,
  digits = 1
): string {
  if (
    value == null ||
    !Number.isFinite(value)
  ) {
    return "—";
  }

  return value.toFixed(digits);
}


function sourceLabel(
  source: string
): string {
  const labels:
    Record<string, string> = {
      road_dust:
        "Road Dust",

      vehicles:
        "Traffic",

      domestic:
        "Domestic",

      construction:
        "Construction",

      hotels:
        "Hotels / Commercial",

      industry:
        "Industry",

      other:
        "Other",
    };

  return (
    labels[source] ||
    source
      .replaceAll("_", " ")
      .replace(
        /\b\w/g,
        (letter) =>
          letter.toUpperCase()
      )
  );
}


export default function InterventionPanel({
  wards,
  onResult,
}: Props) {
  const [levers, setLevers] =
    useState<Lever[]>([]);

  const [values, setValues] =
    useState<Record<string, number>>(
      {}
    );

  const [result, setResult] =
    useState<SimulateAllResponse | null>(
      null
    );

  const [loadingLevers, setLoadingLevers] =
    useState(true);

  const [running, setRunning] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);


  // ------------------------------------------------------------
  // LOAD INTERVENTION LEVERS
  // ------------------------------------------------------------

  useEffect(() => {
    let cancelled = false;


    async function loadLevers() {
      try {
        setLoadingLevers(true);
        setError(null);


        const response =
          await fetch(
            `${BACKEND}/api/interventions`,
            {
              cache: "no-store",
            }
          );


        if (!response.ok) {
          throw new Error(
            `Intervention API returned HTTP ${response.status}`
          );
        }


        const data =
          await response.json();


        const interventions:
          Lever[] =
            data.interventions ?? [];


        if (!cancelled) {
          setLevers(
            interventions
          );


          const initial:
            Record<string, number> =
              {};


          interventions.forEach(
            (lever) => {
              initial[
                lever.key
              ] = 0;
            }
          );


          setValues(
            initial
          );
        }
      } catch (err) {
        console.error(
          "Failed to load interventions:",
          err
        );


        if (!cancelled) {
          setError(
            "Unable to load intervention controls."
          );
        }
      } finally {
        if (!cancelled) {
          setLoadingLevers(
            false
          );
        }
      }
    }


    loadLevers();


    return () => {
      cancelled = true;
    };
  }, []);


  // ------------------------------------------------------------
  // SLIDER CHANGE
  // ------------------------------------------------------------

  const handleSlider = (
    key: string,
    value: number
  ) => {
    setValues(
      (current) => ({
        ...current,
        [key]: value,
      })
    );


    /*
     * A changed slider represents a new scenario.
     * Clear the previous result so the UI never presents
     * an old result as belonging to the new slider values.
     */
    setResult(null);
    setError(null);

    onResult?.(null);
  };


  // ------------------------------------------------------------
  // RUN CITY-WIDE SCENARIO
  // ------------------------------------------------------------

  const runSimulation =
    useCallback(async () => {
      const reductions:
        Record<string, number> =
          {};


      Object.entries(
        values
      ).forEach(
        ([key, value]) => {
          reductions[key] =
            Math.min(
              1,
              Math.max(
                0,
                value / 100
              )
            );
        }
      );


      const hasIntervention =
        Object.values(
          reductions
        ).some(
          (value) =>
            value > 0
        );


      if (!hasIntervention) {
        setError(
          "Set at least one intervention above 0% to run a scenario."
        );

        return;
      }


      if (wards.length === 0) {
        setError(
          "Current ward/locality context is unavailable."
        );

        return;
      }


      try {
        setRunning(true);
        setError(null);


        const response =
          await fetch(
            `${BACKEND}/api/simulate/all`,
            {
              method: "POST",

              headers: {
                "Content-Type":
                  "application/json",
              },

              /*
               * The backend owns current AQI retrieval.
               *
               * Do NOT send frontend AQI values or coordinates
               * as scenario baselines.
               */
              body:
                JSON.stringify({
                  reductions,
                }),
            }
          );


        if (!response.ok) {
          const message =
            await response.text();


          throw new Error(
            `Scenario API returned HTTP ${response.status}: ${message}`
          );
        }


        const data:
          SimulateAllResponse =
            await response.json();


        setResult(
          data
        );

        onResult?.(
          data
        );
      } catch (err) {
        console.error(
          "Scenario simulation failed:",
          err
        );


        setError(
          "Unable to run the intervention scenario. Check that the backend is running and try again."
        );
      } finally {
        setRunning(
          false
        );
      }
    }, [
      values,
      wards,
      onResult,
    ]);


  // ------------------------------------------------------------
  // RESET
  // ------------------------------------------------------------

  const reset = () => {
    const cleared:
      Record<string, number> =
        {};


    levers.forEach(
      (lever) => {
        cleared[
          lever.key
        ] = 0;
      }
    );


    setValues(
      cleared
    );

    setResult(
      null
    );

    setError(
      null
    );

    onResult?.(
      null
    );
  };


  // ------------------------------------------------------------
  // RESULT NORMALISATION
  // ------------------------------------------------------------

  const wardResults =
    result?.wards ??
    result?.results ??
    [];


  const validResults =
    wardResults.filter(
      (item) =>
        Number.isFinite(
          item.estimated_burden_reduction_pct
        ) &&
        Number.isFinite(
          item.remaining_burden_index
        )
    );


  const averageReduction =
    result?.summary
      ?.average_burden_reduction_pct ??
    result?.summary
      ?.avg_burden_reduction_pct ??
    (
      validResults.length > 0
        ? validResults.reduce(
            (
              total,
              item
            ) =>
              total +
              item
                .estimated_burden_reduction_pct,
            0
          ) /
          validResults.length

        : null
    );


  const averageRemaining =
    result?.summary
      ?.average_remaining_burden_index ??
    result?.summary
      ?.avg_remaining_burden_index ??
    (
      validResults.length > 0
        ? validResults.reduce(
            (
              total,
              item
            ) =>
              total +
              item
                .remaining_burden_index,
            0
          ) /
          validResults.length

        : null
    );


  /*
   * Source weights are currently city-level in the backend,
   * so one valid result is sufficient to show the common
   * scenario breakdown.
   */
  const breakdown =
    validResults[0]
      ?.breakdown ??
    [];


  const sortedBreakdown =
    [...breakdown].sort(
      (a, b) =>
        b.weighted_burden_reduction_pct -
        a.weighted_burden_reduction_pct
    );


  const hasActiveIntervention =
    Object.values(values).some(
      (value) => Number.isFinite(value) && value > 0
    );

  const analyzedCount = validResults.length;
  const backendLimitations = result?.model?.limitations ?? [];
  const resultDisclaimer = result?.disclaimer ?? null;

  // ------------------------------------------------------------
  // RENDER
  // ------------------------------------------------------------

  return (
    <aside
      className="sentinel-panel"
      style={{
        position:
          "absolute",

        top:
          80,

        left:
          16,

        zIndex:
          10,

        width:
          350,

        maxWidth:
          "calc(100vw - 32px)",

        maxHeight:
          "calc(100vh - 110px)",

        overflowY:
          "auto",

        padding:
          18,

        color:
          "#f8fafc",
      }}
    >

      {/* ------------------------------------------------------ */}
      {/* HEADER */}
      {/* ------------------------------------------------------ */}

      <div
        style={{
          display:
            "flex",

          alignItems:
            "flex-start",

          justifyContent:
            "space-between",

          gap:
            14,

          marginBottom:
            5,
        }}
      >
        <div>
          <div
            className="sentinel-label"
            style={{
              color:
                "#38bdf8",

              marginBottom:
                5,
            }}
          >
            Scenario Lab
          </div>


          <h2
            style={{
              margin:
                0,

              color:
                "#f8fafc",

              fontSize:
                18,

              fontWeight:
                750,

              letterSpacing:
                "-0.025em",
            }}
          >
            Intervention Simulator
          </h2>
        </div>


        <button
          type="button"
          onClick={
            reset
          }
          disabled={
            running
          }
          style={{
            padding:
              "6px 10px",

            border:
              "1px solid rgba(148,163,184,0.2)",

            borderRadius:
              8,

            background:
              "rgba(148,163,184,0.06)",

            color:
              "#cbd5e1",

            fontSize:
              10,

            fontWeight:
              650,
          }}
        >
          Reset
        </button>
      </div>


      <p
        style={{
          margin:
            "0 0 16px",

          color:
            "#94a3b8",

          fontSize:
            10,

          lineHeight:
            1.55,
        }}
      >
        Test first-order intervention
        assumptions across Sentinel AI&apos;s
        configured Pune analysis locations.
        Current AQI remains unchanged.
      </p>


      {/* ------------------------------------------------------ */}
      {/* LEVERS */}
      {/* ------------------------------------------------------ */}

      {loadingLevers ? (
        <div
          style={{
            padding:
              "16px 0",

            color:
              "#94a3b8",

            fontSize:
              11,
          }}
        >
          Loading intervention controls…
        </div>
      ) : levers.length === 0 ? (
        <div
          style={{
            padding: "14px 0",
            color: "#94a3b8",
            fontSize: 10,
            lineHeight: 1.5,
          }}
        >
          No intervention controls are currently available.
        </div>
      ) : (
        <div>
          {levers.map(
            (lever) => {
              const value =
                values[
                  lever.key
                ] ?? 0;


              return (
                <div
                  key={
                    lever.key
                  }
                  style={{
                    marginBottom:
                      16,
                  }}
                >
                  <div
                    style={{
                      display:
                        "flex",

                      alignItems:
                        "center",

                      justifyContent:
                        "space-between",

                      gap:
                        12,

                      marginBottom:
                        6,
                    }}
                  >
                    <label
                      htmlFor={
                        `intervention-${lever.key}`
                      }
                      style={{
                        color:
                          "#e2e8f0",

                        fontSize:
                          11,

                        fontWeight:
                          650,
                      }}
                    >
                      {
                        lever.label
                      }
                    </label>


                    <span
                      style={{
                        minWidth:
                          44,

                        padding:
                          "3px 7px",

                        borderRadius:
                          999,

                        background:
                          value > 0
                            ? "rgba(56,189,248,0.12)"
                            : "rgba(148,163,184,0.08)",

                        color:
                          value > 0
                            ? "#7dd3fc"
                            : "#94a3b8",

                        fontSize:
                          10,

                        fontWeight:
                          750,

                        textAlign:
                          "center",
                      }}
                    >
                      {value}%
                    </span>
                  </div>


                  <input
                    id={
                      `intervention-${lever.key}`
                    }
                    type="range"
                    min={
                      0
                    }
                    max={
                      100
                    }
                    step={
                      5
                    }
                    value={
                      value
                    }
                    disabled={
                      running
                    }
                    onChange={
                      (event) =>
                        handleSlider(
                          lever.key,
                          Number(
                            event
                              .target
                              .value
                          )
                        )
                    }
                    style={{
                      width:
                        "100%",

                      accentColor:
                        "#38bdf8",
                    }}
                  />


                  {lever.note && (
                    <div
                      style={{
                        marginTop:
                          4,

                        color:
                          "#64748b",

                        fontSize:
                          9,

                        lineHeight:
                          1.45,
                      }}
                    >
                      {
                        lever.note
                      }
                    </div>
                  )}
                </div>
              );
            }
          )}
        </div>
      )}


      {/* ------------------------------------------------------ */}
      {/* RUN BUTTON */}
      {/* ------------------------------------------------------ */}

      {!loadingLevers &&
        levers.length > 0 && (
          <button
            type="button"
            onClick={
              runSimulation
            }
            disabled={
              running ||
              !hasActiveIntervention ||
              wards.length === 0
            }
            style={{
              width:
                "100%",

              padding:
                "10px 14px",

              marginTop:
                2,

              borderRadius:
                9,

              background:
                running
                  ? "rgba(56,189,248,0.18)"
                  : "linear-gradient(135deg, #0284c7, #0ea5e9)",

              color:
                "#ffffff",

              fontSize:
                11,

              fontWeight:
                750,

              letterSpacing:
                "0.02em",

              boxShadow:
                running
                  ? "none"
                  : "0 8px 24px rgba(14,165,233,0.2)",

              opacity:
                running
                  ? 0.7
                  : 1,
            }}
          >
            {running
              ? "Running scenario…"
              : "Run City-wide Scenario"}
          </button>
        )}


      {/* ------------------------------------------------------ */}
      {/* ERROR */}
      {/* ------------------------------------------------------ */}

      {error && (
        <div
          style={{
            marginTop:
              12,

            padding:
              10,

            border:
              "1px solid rgba(248,113,113,0.2)",

            borderRadius:
              8,

            background:
              "rgba(127,29,29,0.16)",

            color:
              "#fca5a5",

            fontSize:
              10,

            lineHeight:
              1.5,
          }}
        >
          {error}
        </div>
      )}


      {/* ------------------------------------------------------ */}
      {/* SCENARIO RESULT */}
      {/* ------------------------------------------------------ */}

      {result &&
        !running && (
          <div
            style={{
              marginTop:
                16,

              padding:
                14,

              border:
                "1px solid rgba(34,197,94,0.22)",

              borderRadius:
                12,

              background:
                "linear-gradient(145deg, rgba(34,197,94,0.10), rgba(15,23,42,0.25))",
            }}
          >
            <div
              className="sentinel-label"
              style={{
                marginBottom:
                  10,

                color:
                  "#86efac",
              }}
            >
              Scenario Result
            </div>

            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                gap: 10,
                marginBottom: 12,
                padding: "7px 9px",
                borderRadius: 8,
                background: "rgba(15,23,42,0.30)",
                border: "1px solid rgba(148,163,184,0.10)",
                color: "#94a3b8",
                fontSize: 9,
              }}
            >
              <span>Locations analyzed</span>
              <strong style={{ color: "#e2e8f0" }}>
                {analyzedCount}/{wards.length}
              </strong>
            </div>

            <div
              style={{
                display:
                  "grid",

                gridTemplateColumns:
                  "1fr auto 1fr",

                alignItems:
                  "center",

                gap:
                  10,
              }}
            >
              <div>
                <div
                  style={{
                    color:
                      "#94a3b8",

                    fontSize:
                      9,

                    marginBottom:
                      3,
                  }}
                >
                  Baseline burden
                </div>

                <strong
                  style={{
                    color:
                      "#f8fafc",

                    fontSize:
                      23,
                  }}
                >
                  100
                </strong>
              </div>


              <div
                style={{
                  color:
                    "#64748b",

                  fontSize:
                    18,
                }}
              >
                →
              </div>


              <div
                style={{
                  textAlign:
                    "right",
                }}
              >
                <div
                  style={{
                    color:
                      "#94a3b8",

                    fontSize:
                      9,

                    marginBottom:
                      3,
                  }}
                >
                  Remaining burden
                </div>

                <strong
                  style={{
                    color:
                      "#86efac",

                    fontSize:
                      23,
                  }}
                >
                  {
                    formatNumber(
                      averageRemaining,
                      2
                    )
                  }
                </strong>
              </div>
            </div>


            <div
              style={{
                marginTop:
                  12,

                paddingTop:
                  11,

                borderTop:
                  "1px solid rgba(134,239,172,0.14)",
              }}
            >
              <div
                style={{
                  color:
                    "#94a3b8",

                  fontSize:
                    9,

                  marginBottom:
                    3,
                }}
              >
                Estimated relative
                particulate-burden reduction
              </div>


              <strong
                style={{
                  color:
                    "#4ade80",

                  fontSize:
                    24,

                  letterSpacing:
                    "-0.03em",
                }}
              >
                ↓{" "}
                {
                  formatNumber(
                    averageReduction,
                    2
                  )
                }
                %
              </strong>
            </div>


            {/* ------------------------------------------------ */}
            {/* SOURCE BREAKDOWN */}
            {/* ------------------------------------------------ */}

            {sortedBreakdown.length >
              0 && (
              <div
                style={{
                  marginTop:
                    15,
                }}
              >
                <div
                  className="sentinel-label"
                  style={{
                    marginBottom:
                      9,
                  }}
                >
                  Modeled reduction breakdown
                </div>


                {sortedBreakdown.map(
                  (item) => {
                    const width =
                      Math.min(
                        100,
                        Math.max(
                          0,
                          item
                            .weighted_burden_reduction_pct *
                            2.5
                        )
                      );


                    return (
                      <div
                        key={
                          item.source
                        }
                        style={{
                          marginBottom:
                            8,
                        }}
                      >
                        <div
                          style={{
                            display:
                              "flex",

                            justifyContent:
                              "space-between",

                            gap:
                              10,

                            marginBottom:
                              3,

                            color:
                              "#cbd5e1",

                            fontSize:
                              9,
                          }}
                        >
                          <span>
                            {
                              sourceLabel(
                                item.source
                              )
                            }
                          </span>

                          <strong
                            style={{
                              color:
                                "#e2e8f0",
                            }}
                          >
                            {
                              formatNumber(
                                item
                                  .weighted_burden_reduction_pct,
                                2
                              )
                            }
                            %
                          </strong>
                        </div>


                        <div
                          style={{
                            height:
                              4,

                            overflow:
                              "hidden",

                            borderRadius:
                              999,

                            background:
                              "rgba(148,163,184,0.12)",
                          }}
                        >
                          <div
                            style={{
                              width:
                                `${width}%`,

                              height:
                                "100%",

                              borderRadius:
                                999,

                              background:
                                "#38bdf8",

                              transition:
                                "width 300ms ease",
                            }}
                          />
                        </div>
                      </div>
                    );
                  }
                )}
              </div>
            )}


            {/* ------------------------------------------------ */}
            {/* MODEL BOUNDARY */}
            {/* ------------------------------------------------ */}

            <div
              style={{
                marginTop:
                  13,

                padding:
                  9,

                borderRadius:
                  8,

                background:
                  "rgba(15,23,42,0.38)",

                color:
                  "#94a3b8",

                fontSize:
                  9,

                lineHeight:
                  1.5,
              }}
            >
              <strong
                style={{
                  color:
                    "#cbd5e1",
                }}
              >
                Scenario estimate only.
              </strong>
              {" "}
              {resultDisclaimer ||
                "This represents relative source-weighted particulate-burden change. It does not predict future CPCB AQI, atmospheric dispersion, chemistry, or meteorological feedback."}

              {backendLimitations.length > 0 && (
                <div
                  style={{
                    marginTop: 7,
                    paddingTop: 7,
                    borderTop: "1px solid rgba(148,163,184,0.10)",
                  }}
                >
                  {backendLimitations.slice(0, 3).map((limitation) => (
                    <div key={limitation} style={{ marginTop: 3 }}>
                      • {limitation}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
    </aside>
  );
}