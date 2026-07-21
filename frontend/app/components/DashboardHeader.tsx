"use client";

type Props = {
  availableCount?: number;
  usableCount?: number;
  freshCount?: number;
  totalCount?: number;
  dataSource?: string;
  loading?: boolean;
  backendReachable?: boolean;
  onRefresh?: () => void;
};

export default function DashboardHeader({
  availableCount = 0,
  usableCount = 0,
  freshCount = 0,
  totalCount = 0,
  dataSource = "Open-Meteo · CAMS Global",
  loading = false,
  backendReachable = true,
  onRefresh,
}: Props) {
  const hasLocations = totalCount > 0;

  const allCurrent =
    hasLocations &&
    usableCount === totalCount;

  const partial =
    usableCount > 0 &&
    usableCount < totalCount;

  /*
   * UI/system status colors are intentionally
   * separate from AQI category colors.
   *
   * Cyan  = normal system operation
   * Yellow = partial data coverage
   * Orange = no usable context
   * Red    = backend unavailable
   */

  const status = loading
    ? {
        label: "UPDATING CONTEXT",
        detail:
          "Fetching latest modeled data",
        tone: "#38bdf8",
      }
    : !backendReachable
      ? {
          label: "SYSTEM UNAVAILABLE",
          detail:
            "Backend connection failed",
          tone: "#ef4444",
        }
      : allCurrent
        ? {
            label:
              "CURRENT CONTEXT READY",
            detail:
              `${usableCount}/${totalCount} locations usable`,
            tone: "#38bdf8",
          }
        : partial
          ? {
              label:
                "PARTIAL COVERAGE",
              detail:
                `${usableCount}/${totalCount} locations usable`,
              tone: "#eab308",
            }
          : {
              label:
                "CONTEXT UNAVAILABLE",
              detail:
                "No usable current AQI context",
              tone: "#f97316",
            };

  return (
    <header className="sentinel-header">

      {/* ======================================================
          BRAND
          ====================================================== */}

      <div className="sentinel-brand">

        <div className="sentinel-logo">
          S
        </div>

        <div>

          <div className="sentinel-brand-row">

            <span className="sentinel-brand-name">
              SENTINEL AI
            </span>

            <span className="sentinel-brand-badge">
              DECISION INTELLIGENCE
            </span>

          </div>

          <div className="sentinel-brand-subtitle">
            Urban Air Quality Decision Support
          </div>

        </div>

      </div>

      {/* ======================================================
          STATUS AREA
          ====================================================== */}

      <div className="sentinel-header-status">

        {/* Analysis Area */}

        <div className="sentinel-header-stat sentinel-hide-mobile">

          <span>
            Analysis Area
          </span>

          <strong>
            Pune, Maharashtra
          </strong>

        </div>


        <div className="sentinel-header-divider sentinel-hide-mobile" />


        {/* AQI Context */}

        <div className="sentinel-header-stat sentinel-hide-tablet">

          <span>
            AQI Context
          </span>

          <strong>
            Modeled · {dataSource}
          </strong>

        </div>


        <div className="sentinel-header-divider sentinel-hide-tablet" />


        {/* Coverage */}

        <div className="sentinel-header-stat">

          <span>
            Coverage
          </span>

          <strong>
            {availableCount}/{totalCount || 0} available
            {" · "}
            {freshCount} fresh
          </strong>

        </div>


        {/* Refresh */}

        {onRefresh && (
          <button
            type="button"
            className="sentinel-refresh"
            onClick={onRefresh}
            disabled={loading}
            aria-label="Refresh AQI context"
            title="Refresh AQI context"
          >
            {loading ? "…" : "↻"}
          </button>
        )}


        {/* System Status */}

        <div
          className="sentinel-system-pill"
          style={{
            borderColor:
              `${status.tone}33`,

            background:
              `${status.tone}0D`,
          }}
        >

          <span
            className="sentinel-system-dot"
            style={{
              background:
                status.tone,

              boxShadow:
                `0 0 0 4px ${status.tone}20`,
            }}
          />


          <div>

            <div
              className="sentinel-system-label"
              style={{
                color:
                  status.tone,
              }}
            >
              {status.label}
            </div>

            <div className="sentinel-system-detail">
              {status.detail}
            </div>

          </div>

        </div>

      </div>

    </header>
  );
}