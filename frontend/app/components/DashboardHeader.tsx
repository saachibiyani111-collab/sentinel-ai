"use client";

type Props = {
  cityAqi: number;
};

function aqiCategory(aqi: number): string {
  if (aqi <= 50) return "Good";
  if (aqi <= 100) return "Satisfactory";
  if (aqi <= 200) return "Moderate";
  if (aqi <= 300) return "Poor";
  if (aqi <= 400) return "Very Poor";
  return "Severe";
}

function categoryColor(category: string): string {
  switch (category) {
    case "Good":
      return "#22c55e";
    case "Satisfactory":
      return "#84cc16";
    case "Moderate":
      return "#eab308";
    case "Poor":
      return "#f97316";
    case "Very Poor":
      return "#ef4444";
    case "Severe":
      return "#a855f7";
    default:
      return "#94a3b8";
  }
}

export default function DashboardHeader({ cityAqi }: Props) {
  const category = aqiCategory(cityAqi);
  const color = categoryColor(category);

  return (
    <header
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        height: 58,
        zIndex: 20,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 20px",
        background: "rgba(15, 23, 42, 0.97)",
        borderBottom: "1px solid rgba(148, 163, 184, 0.16)",
        color: "#f8fafc",
        fontFamily: "sans-serif",
        boxSizing: "border-box",
      }}
    >
      <div>
        <div
          style={{
            fontSize: 16,
            fontWeight: 700,
            letterSpacing: "0.06em",
          }}
        >
          SENTINEL AI
        </div>

        <div
          style={{
            fontSize: 10,
            color: "#94a3b8",
            marginTop: 2,
          }}
        >
          Urban Air Quality Intelligence
        </div>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 18,
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 6,
            fontSize: 10,
            color: "#86efac",
            fontWeight: 700,
            letterSpacing: "0.05em",
          }}
        >
          <span
            style={{
              width: 7,
              height: 7,
              borderRadius: "50%",
              background: "#22c55e",
              display: "inline-block",
              boxShadow: "0 0 8px rgba(34,197,94,0.7)",
            }}
          />

          LIVE
        </div>

        <div
          style={{
            fontSize: 12,
            color: "#cbd5e1",
          }}
        >
          Pune
        </div>

        {cityAqi > 0 && (
          <div
            style={{
              borderLeft: "1px solid #334155",
              paddingLeft: 18,
              display: "flex",
              alignItems: "center",
              gap: 7,
            }}
          >
            <span
              style={{
                fontSize: 9,
                color: "#94a3b8",
                letterSpacing: "0.05em",
              }}
            >
              CITY AQI
            </span>

            <strong
              style={{
                fontSize: 16,
              }}
            >
              {cityAqi.toFixed(1)}
            </strong>

            <span
              style={{
                fontSize: 10,
                color,
                fontWeight: 600,
              }}
            >
              {category}
            </span>
          </div>
        )}
      </div>
    </header>
  );
}