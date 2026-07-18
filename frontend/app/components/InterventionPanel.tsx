"use client";

import {
  useEffect,
  useState,
  useCallback,
  useRef,
} from "react";

type Lever = {
  key: string;
  label: string;
  affects: string[];
  note: string;
};

type WardResult = {
  ward: string;
  lat: number;
  lon: number;
  base_aqi: number;
  new_aqi: number;
  aqi_drop: number;
  pct_drop: number;
};

type SimulateResponse = {
  wards: WardResult[];

  summary: {
    avg_aqi_before: number;
    avg_aqi_after: number;
    avg_drop: number;
    avg_pct_drop: number;
    best_ward: string;
  };
};

const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

type Props = {
  cityAqi: number;

  onResult?: (
    result: SimulateResponse | null
  ) => void;
};

export default function InterventionPanel({
  cityAqi,
  onResult,
}: Props) {
  const [levers, setLevers] =
    useState<Lever[]>([]);

  const [values, setValues] =
    useState<Record<string, number>>({});

  const [result, setResult] =
    useState<SimulateResponse | null>(null);

  const [loading, setLoading] =
    useState(false);

  const debounceRef =
    useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    fetch(`${BACKEND}/api/interventions`)
      .then((r) => r.json())

      .then((d) =>
        setLevers(d.interventions || [])
      )

      .catch((err) =>
        console.error(
          "Failed to load interventions:",
          err
        )
      );
  }, []);

  const runSimulation = useCallback(
    (
      currentValues: Record<string, number>
    ) => {
      const reductions: Record<string, number> = {};

      for (const [k, v] of Object.entries(currentValues)) {
        if (v > 0) {
          reductions[k] = v / 100;
        }
      }

      setLoading(true);

      fetch(`${BACKEND}/api/simulate/all`, {
        method: "POST",

        headers: {
          "Content-Type": "application/json",
        },

        body: JSON.stringify({
          city_aqi: cityAqi,
          reductions,
        }),
      })
        .then((r) => r.json())

        .then((d: SimulateResponse) => {
          setResult(d);

          onResult?.(d);
        })

        .catch((err) =>
          console.error(
            "Simulation failed:",
            err
          )
        )

        .finally(() =>
          setLoading(false)
        );
    },
    [cityAqi, onResult]
  );

  const handleSlider = (
    key: string,
    value: number
  ) => {
    const next = {
      ...values,
      [key]: value,
    };

    setValues(next);

    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    debounceRef.current = setTimeout(
      () => runSimulation(next),
      300
    );
  };

  const reset = () => {
    setValues({});
    setResult(null);
    onResult?.(null);
  };

  return (
    <div
      style={{
        position: "absolute",
        top: 74,
        left: 16,
        width: 320,
        background: "rgba(15, 23, 42, 0.96)",
        color: "#f8fafc",
        border: "1px solid rgba(148, 163, 184, 0.16)",
        borderRadius: 12,
        padding: 16,
        fontFamily: "sans-serif",
        fontSize: 13,
        zIndex: 10,
        maxHeight: "calc(100vh - 100px)",
        overflowY: "auto",
        boxShadow: "0 8px 24px rgba(15, 23, 42, 0.18)",
        boxSizing: "border-box",
      }}
    >
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 3,
        }}
      >
        <strong
          style={{
            fontSize: 15,
          }}
        >
          Intervention Simulator
        </strong>

        <button
          onClick={reset}
          style={{
            background: "rgba(255,255,255,0.03)",
            border: "1px solid #475569",
            color: "#cbd5e1",
            borderRadius: 6,
            padding: "3px 9px",
            cursor: "pointer",
            fontSize: 10,
          }}
        >
          Reset
        </button>
      </div>

      <div
        style={{
          color: "#64748b",
          fontSize: 10,
          marginBottom: 15,
        }}
      >
        Explore projected AQI impact under different policy
        interventions.
      </div>

      {levers.map((lever) => (
        <div
          key={lever.key}
          style={{
            marginBottom: 15,
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              gap: 10,
            }}
          >
            <label
              style={{
                fontSize: 11,
                color: "#e2e8f0",
                lineHeight: 1.4,
              }}
            >
              {lever.label}
            </label>

            <span
              style={{
                minWidth: 32,
                textAlign: "right",
                fontSize: 11,
                color:
                  (values[lever.key] || 0) > 0
                    ? "#4ade80"
                    : "#94a3b8",
                fontWeight: 600,
              }}
            >
              {values[lever.key] || 0}%
            </span>
          </div>

          <input
            type="range"
            min={0}
            max={100}
            value={values[lever.key] || 0}
            onChange={(e) =>
              handleSlider(
                lever.key,
                Number(e.target.value)
              )
            }
            style={{
              width: "100%",
              marginTop: 5,
            }}
          />

          <div
            style={{
              fontSize: 9,
              color: "#64748b",
              marginTop: 2,
              lineHeight: 1.4,
            }}
          >
            {lever.note}
          </div>
        </div>
      ))}

      {loading && (
        <div
          style={{
            color: "#94a3b8",
            fontSize: 11,
            paddingTop: 4,
          }}
        >
          Calculating projected impact...
        </div>
      )}

      {result && !loading && (
        <div
          style={{
            marginTop: 12,
            padding: 12,
            background: "rgba(34, 197, 94, 0.08)",
            border: "1px solid rgba(74, 222, 128, 0.25)",
            borderRadius: 8,
          }}
        >
          <div
            style={{
              color: "#94a3b8",
              fontSize: 9,
              fontWeight: 600,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: 6,
            }}
          >
            City-wide projected impact
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <strong
              style={{
                fontSize: 18,
                color: "#e2e8f0",
              }}
            >
              {result.summary.avg_aqi_before}
            </strong>

            <span
              style={{
                color: "#64748b",
                fontSize: 16,
              }}
            >
              &rarr;
            </span>

            <strong
              style={{
                color: "#4ade80",
                fontSize: 22,
              }}
            >
              {result.summary.avg_aqi_after}
            </strong>
          </div>

          <div
            style={{
              color: "#4ade80",
              fontSize: 12,
              fontWeight: 600,
              marginTop: 3,
            }}
          >
            &darr; {result.summary.avg_pct_drop}% projected
            improvement
          </div>

          <div
            style={{
              color: "#64748b",
              fontSize: 9,
              marginTop: 6,
              lineHeight: 1.4,
            }}
          >
            What-if estimate based on the selected intervention
            scenario.
          </div>
        </div>
      )}
    </div>
  );
}