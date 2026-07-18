"use client";

import { useEffect, useState } from "react";

type ActionItem = {
  lever: string;
  label: string;
  evidence: string;
  projected_aqi: number;
  pct_drop: number;
  actions: string[];
  priority?: number;
  reason?: string;
};

type EnforcementPlan = {
  ward: string;
  base_aqi: number;
  recommended: ActionItem[];
  not_recommended: ActionItem[];
};

type Advisory = {
  ward: string;
  aqi: number;

  category: {
    en: string;
    mr: string;
  };

  advisory: {
    en: string;
    mr: string;
  };

  sensitive_groups: {
    en: string;
    mr: string;
  };
};

const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type Props = {
  ward: string | null;

  // Original baseline AQI.
  baseAqi: number;

  // Existing simulator output.
  // Used ONLY for UI display.
  simulatedAqi: number | null;

  onClose: () => void;
};

export default function WardCard({
  ward,
  baseAqi,
  simulatedAqi,
  onClose,
}: Props) {
  const [plan, setPlan] =
    useState<EnforcementPlan | null>(null);

  const [advisory, setAdvisory] =
    useState<Advisory | null>(null);

  const [loading, setLoading] =
    useState(false);

  useEffect(() => {
    if (!ward) {
      setPlan(null);
      setAdvisory(null);
      return;
    }

    setLoading(true);

    const encoded = encodeURIComponent(ward);

    // IMPORTANT:
    // Both calls intentionally use baseAqi.
    // simulatedAqi does not affect these APIs.
    Promise.all([
      fetch(
        `${BACKEND}/api/enforce/${encoded}?base_aqi=${baseAqi}`
      ).then((r) => r.json()),

      fetch(
        `${BACKEND}/api/advisory/${encoded}?aqi=${baseAqi}`
      ).then((r) => r.json()),
    ])
      .then(([enforceData, advisoryData]) => {
        setPlan(enforceData);
        setAdvisory(advisoryData);
      })

      .catch((err) =>
        console.error(
          "Failed to load ward detail:",
          err
        )
      )

      .finally(() =>
        setLoading(false)
      );
  }, [ward, baseAqi]);

  if (!ward) return null;

  const hasSimulation =
    simulatedAqi != null;

  const simulationDrop =
    hasSimulation && baseAqi > 0
      ? (
          ((baseAqi - simulatedAqi) / baseAqi) *
          100
        ).toFixed(1)
      : null;

  return (
    <div
      style={{
        position: "absolute",
        top: 74,
        right: 16,
        width: 360,
        maxHeight: "calc(100vh - 100px)",
        overflowY: "auto",
        background: "rgba(15, 23, 42, 0.97)",
        color: "#f8fafc",
        border: "1px solid rgba(148, 163, 184, 0.16)",
        borderRadius: 12,
        padding: 16,
        fontFamily: "sans-serif",
        fontSize: 13,
        zIndex: 10,
        boxShadow: "0 8px 24px rgba(15, 23, 42, 0.2)",
        boxSizing: "border-box",
      }}
    >
      {/* HEADER */}

      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 12,
        }}
      >
        <div>
          <strong
            style={{
              fontSize: 16,
            }}
          >
            {ward}
          </strong>

          <div
            style={{
              color: "#64748b",
              fontSize: 9,
              marginTop: 3,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
            }}
          >
            Ward Intelligence
          </div>
        </div>

        <button
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            color: "#94a3b8",
            cursor: "pointer",
            fontSize: 18,
            lineHeight: 1,
          }}
        >
          &times;
        </button>
      </div>

      {/* ACTIVE WHAT-IF SCENARIO */}

      {hasSimulation && (
        <div
          style={{
            background: "rgba(34, 197, 94, 0.08)",
            border: "1px solid rgba(74, 222, 128, 0.28)",
            borderRadius: 8,
            padding: 11,
            marginBottom: 12,
          }}
        >
          <div
            style={{
              color: "#4ade80",
              fontSize: 9,
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.07em",
              marginBottom: 8,
            }}
          >
            What-if scenario active
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 10,
            }}
          >
            <div>
              <div
                style={{
                  color: "#94a3b8",
                  fontSize: 9,
                  marginBottom: 1,
                }}
              >
                Current AQI
              </div>

              <strong
                style={{
                  fontSize: 20,
                }}
              >
                {baseAqi.toFixed(1)}
              </strong>
            </div>

            <div
              style={{
                color: "#64748b",
                fontSize: 18,
              }}
            >
              &rarr;
            </div>

            <div>
              <div
                style={{
                  color: "#94a3b8",
                  fontSize: 9,
                  marginBottom: 1,
                }}
              >
                Projected AQI
              </div>

              <strong
                style={{
                  fontSize: 20,
                  color: "#4ade80",
                }}
              >
                {simulatedAqi.toFixed(1)}
              </strong>
            </div>
          </div>

          <div
            style={{
              color: "#4ade80",
              fontSize: 11,
              fontWeight: 600,
              marginTop: 5,
            }}
          >
            &darr; {simulationDrop}% projected improvement
          </div>

          <div
            style={{
              color: "#64748b",
              fontSize: 9,
              marginTop: 4,
            }}
          >
            Based on the active intervention scenario
          </div>
        </div>
      )}

      {loading && (
        <div
          style={{
            color: "#94a3b8",
            fontSize: 11,
          }}
        >
          Loading ward intelligence...
        </div>
      )}

      {/* CITIZEN HEALTH ADVISORY */}

      {advisory && !loading && (
        <div
          style={{
            background: "rgba(255,255,255,0.045)",
            border: "1px solid rgba(148, 163, 184, 0.1)",
            borderRadius: 8,
            padding: 10,
            marginBottom: 14,
          }}
        >
          <div
            style={{
              color: "#94a3b8",
              fontSize: 9,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.05em",
              marginBottom: 5,
            }}
          >
            Citizen Health Advisory
          </div>

          <div
            style={{
              fontSize: 11,
              color: "#94a3b8",
              marginBottom: 6,
            }}
          >
            Current AQI {advisory.aqi}
            {" · "}
            {advisory.category.en}
            {" / "}
            {advisory.category.mr}
          </div>

          <div
            style={{
              marginBottom: 5,
              color: "#f1f5f9",
              fontSize: 12,
              lineHeight: 1.5,
            }}
          >
            {advisory.advisory.en}
          </div>

          <div
            style={{
              color: "#cbd5e1",
              fontSize: 12,
              lineHeight: 1.5,
            }}
          >
            {advisory.advisory.mr}
          </div>

          <div
            style={{
              fontSize: 10,
              color: "#64748b",
              marginTop: 7,
              lineHeight: 1.4,
            }}
          >
            {advisory.sensitive_groups.en}
          </div>
        </div>
      )}

      {/* ENFORCEMENT INTELLIGENCE */}

      {plan && !loading && (
        <>
          <div
            style={{
              fontSize: 11,
              fontWeight: 700,
              marginBottom: 9,
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              color: "#cbd5e1",
            }}
          >
            Enforcement Priorities
          </div>

          {plan.recommended.map((a, index) => (
            <div
              key={a.lever}
              style={{
                borderLeft:
                  index === 0
                    ? "3px solid #4ade80"
                    : "2px solid #334155",

                background:
                  index === 0
                    ? "rgba(74, 222, 128, 0.05)"
                    : "transparent",

                padding:
                  index === 0
                    ? "8px 8px 8px 10px"
                    : "4px 0 4px 9px",

                borderRadius:
                  index === 0
                    ? "0 6px 6px 0"
                    : 0,

                marginBottom: 10,
              }}
            >
              <div
                style={{
                  fontWeight: 600,
                  fontSize: 12,
                }}
              >
                #{a.priority} {a.label}
              </div>

              <div
                style={{
                  color: "#4ade80",
                  fontSize: 11,
                  marginTop: 2,
                }}
              >
                AQI {plan.base_aqi}
                {" → "}
                {a.projected_aqi}
                {" "}
                (−{a.pct_drop}%)
              </div>

              <ul
                style={{
                  margin: "5px 0",
                  paddingLeft: 16,
                  fontSize: 11,
                  color: "#cbd5e1",
                  lineHeight: 1.5,
                }}
              >
                {a.actions.map((act, i) => (
                  <li key={i}>
                    {act}
                  </li>
                ))}
              </ul>

              <div
                style={{
                  fontSize: 9,
                  color: "#64748b",
                  lineHeight: 1.4,
                }}
              >
                {a.evidence}
              </div>
            </div>
          ))}

          {plan.not_recommended.length > 0 && (
            <>
              <div
                style={{
                  fontSize: 9,
                  fontWeight: 700,
                  marginTop: 14,
                  marginBottom: 7,
                  color: "#64748b",
                  textTransform: "uppercase",
                  letterSpacing: "0.06em",
                }}
              >
                Not Worth Enforcement Effort
              </div>

              {plan.not_recommended.map((a) => (
                <div
                  key={a.lever}
                  style={{
                    borderLeft: "2px solid #475569",
                    paddingLeft: 8,
                    marginBottom: 8,
                  }}
                >
                  <div
                    style={{
                      fontSize: 11,
                      color: "#94a3b8",
                    }}
                  >
                    {a.label}
                  </div>

                  <div
                    style={{
                      fontSize: 9,
                      color: "#64748b",
                      marginTop: 2,
                      lineHeight: 1.4,
                    }}
                  >
                    {a.reason}
                  </div>
                </div>
              ))}
            </>
          )}
        </>
      )}
    </div>
  );
}