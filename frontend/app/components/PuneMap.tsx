"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import InterventionPanel from "./InterventionPanel";
import WardCard from "./WardCard";
import DashboardHeader from "./DashboardHeader";

type Ward = {
  name: string;
  lat: number | null;
  lon: number | null;
  aqi: number | null;
  category: string;
  dominant: string | null;
  pm25: number | null;
  pm10: number | null;
  is_live: boolean;
  reading_time: string | null;
  alpha?: number;
  city_aqi?: number;
};

type SimWardResult = {
  ward: string;
  new_aqi: number;
  pct_drop: number;
};

type SimulateResponse = {
  wards: SimWardResult[];
  summary: {
    avg_aqi_before: number;
    avg_aqi_after: number;
    avg_pct_drop: number;
  };
};

const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

function categoryColor(category: string): string {
  switch (category) {
    case "Good":
      return "#15803d";
    case "Satisfactory":
      return "#4d7c0f";
    case "Moderate":
      return "#ca8a04";
    case "Poor":
      return "#c2410c";
    case "Very Poor":
      return "#b91c1c";
    case "Severe":
      return "#6b21a8";
    default:
      return "#4b5563";
  }
}

function aqiToCategory(aqi: number): string {
  if (aqi <= 50) return "Good";
  if (aqi <= 100) return "Satisfactory";
  if (aqi <= 200) return "Moderate";
  if (aqi <= 300) return "Poor";
  if (aqi <= 400) return "Very Poor";
  return "Severe";
}

export default function PuneMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<Record<string, maplibregl.Marker>>({});
  const wardsRef = useRef<Ward[]>([]);

  // Simulation results are stored separately.
  // Original ward data is never overwritten.
  const simulationOverridesRef = useRef<Record<string, number>>({});

  const [cityAqi, setCityAqi] = useState<number>(0);

  const [selectedWard, setSelectedWard] =
    useState<string | null>(null);

  // Always the original baseline AQI.
  const [selectedWardAqi, setSelectedWardAqi] =
    useState<number>(0);

  // Simulation output, used for display only.
  const [selectedWardSimAqi, setSelectedWardSimAqi] =
    useState<number | null>(null);

  const renderMarkers = useCallback(
    (
      wards: Ward[],
      overrides?: Record<string, number>
    ) => {
      const map = mapRef.current;

      if (!map) return;

      Object.values(markersRef.current).forEach((marker) =>
        marker.remove()
      );

      markersRef.current = {};

      wards.forEach((w) => {
        if (w.lat == null || w.lon == null) return;

        const simulatedAqi = overrides?.[w.name];
        const hasSimulation = simulatedAqi != null;

        const effectiveAqi = hasSimulation
          ? simulatedAqi
          : w.aqi ?? 0;

        const category = hasSimulation
          ? aqiToCategory(effectiveAqi)
          : w.category;

        const color = categoryColor(category);

        let aqiDisplay = "";

        if (hasSimulation && w.aqi != null) {
          const pctDrop =
            w.aqi > 0
              ? ((w.aqi - effectiveAqi) / w.aqi) * 100
              : 0;

          aqiDisplay = `
            <div
              style="
                margin-top:6px;
                margin-bottom:7px;
                padding:8px;
                background:#f0fdf4;
                border:1px solid #bbf7d0;
                border-radius:7px;
              "
            >
              <div
                style="
                  color:#166534;
                  font-size:9px;
                  font-weight:700;
                  text-transform:uppercase;
                  letter-spacing:0.5px;
                  margin-bottom:4px;
                "
              >
                What-if scenario
              </div>

              <div style="font-size:12px;">
                Current AQI:
                <b style="color:#111827;">
                  ${w.aqi.toFixed(1)}
                </b>
              </div>

              <div style="font-size:12px;">
                Projected AQI:
                <b style="color:${color};">
                  ${effectiveAqi.toFixed(1)}
                </b>

                <span style="color:#374151;">
                  (${category})
                </span>
              </div>

              <div
                style="
                  color:#15803d;
                  font-size:11px;
                  font-weight:600;
                  margin-top:3px;
                "
              >
                ↓ ${pctDrop.toFixed(1)}% projected improvement
              </div>
            </div>
          `;
        } else {
          aqiDisplay = `
            <div style="margin-top:3px; margin-bottom:4px;">
              AQI:
              <b
                style="
                  color:${color};
                  font-size:14px;
                "
              >
                ${effectiveAqi.toFixed(1)}
              </b>

              <span style="color:#374151;">
                (${category})
              </span>
            </div>
          `;
        }

        const popup = new maplibregl.Popup({
          offset: 12,
        }).setHTML(
          `
          <div
            style="
              color:#111827;
              font-family:sans-serif;
              font-size:12px;
              line-height:1.6;
              padding:5px 6px;
              min-width:190px;
            "
          >
            <strong
              style="
                font-size:15px;
                color:#000;
              "
            >
              ${w.name}
            </strong>

            ${aqiDisplay}

            Dominant:
            <b>${w.dominant ?? "-"}</b>

            <br/>

            PM2.5:
            ${w.pm25 ?? "-"}

            &nbsp;|&nbsp;

            PM10:
            ${w.pm10 ?? "-"}

            ${
              w.alpha != null
                ? `
                  <br/>
                  <span
                    style="
                      color:#9ca3af;
                      font-size:10px;
                    "
                  >
                    Historical calibration α ${w.alpha}
                    &middot;
                    city baseline ${w.city_aqi}
                  </span>
                `
                : ""
            }
          </div>
          `
        );

        const marker = new maplibregl.Marker({
          color,
        })
          .setLngLat([w.lon, w.lat])
          .setPopup(popup)
          .addTo(map);

        marker.getElement().style.cursor = "pointer";

        marker.getElement().addEventListener("click", () => {
          // Always preserve original baseline AQI.
          setSelectedWard(w.name);
          setSelectedWardAqi(w.aqi ?? 0);

          // Simulation result is display-only.
          setSelectedWardSimAqi(
            simulatedAqi != null ? simulatedAqi : null
          );
        });

        markersRef.current[w.name] = marker;
      });
    },
    []
  );

  const handleSimResult = useCallback(
    (result: SimulateResponse | null) => {
      // Reset simulation.
      if (!result) {
        simulationOverridesRef.current = {};

        renderMarkers(wardsRef.current);

        setSelectedWardSimAqi(null);

        return;
      }

      const overrides: Record<string, number> = {};

      result.wards.forEach((w) => {
        overrides[w.ward] = w.new_aqi;
      });

      simulationOverridesRef.current = overrides;

      // Re-render map using projected AQI.
      renderMarkers(wardsRef.current, overrides);

      // Update the open WardCard with the projected value.
      if (selectedWard) {
        const simulatedWard = result.wards.find(
          (w) => w.ward === selectedWard
        );

        setSelectedWardSimAqi(
          simulatedWard?.new_aqi ?? null
        );
      }
    },
    [renderMarkers, selectedWard]
  );

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,

      style: {
        version: 8,

        sources: {
          osm: {
            type: "raster",

            tiles: [
              "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            ],

            tileSize: 256,

            attribution: "OpenStreetMap contributors",
          },
        },

        layers: [
          {
            id: "osm",
            type: "raster",
            source: "osm",
          },
        ],
      },

      center: [73.8567, 18.5204],
      zoom: 11,
    });

    mapRef.current = map;

    map.addControl(
      new maplibregl.NavigationControl(),
      "top-right"
    );

    map.on("load", async () => {
      try {
        const res = await fetch(`${BACKEND}/api/aqi/pune`);

        const data = await res.json();

        const wards: Ward[] = data.stations || [];

        if (wards.length === 0) {
          console.warn(
            "No wards returned from /api/aqi/pune -- check backend is running"
          );

          return;
        }

        // Store backend data exactly as returned.
        wardsRef.current = wards;

        setCityAqi(wards[0]?.city_aqi ?? 0);

        renderMarkers(wards);
      } catch (err) {
        console.error(
          "Failed to load wards:",
          err
        );
      }
    });

    return () => {
      map.remove();
      mapRef.current = null;
      markersRef.current = {};
    };
  }, [renderMarkers]);

  const legendItems = [
    ["#15803d", "Good"],
    ["#4d7c0f", "Satisfactory"],
    ["#ca8a04", "Moderate"],
    ["#c2410c", "Poor"],
    ["#b91c1c", "Very Poor"],
    ["#6b21a8", "Severe"],
  ];

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100vh",
        overflow: "hidden",
        background: "#0f172a",
      }}
    >
      <DashboardHeader cityAqi={cityAqi} />

      <div
        ref={mapContainer}
        style={{
          position: "absolute",
          top: 58,
          left: 0,
          right: 0,
          bottom: 0,
        }}
      />

      {cityAqi > 0 && (
        <InterventionPanel
          cityAqi={cityAqi}
          onResult={handleSimResult}
        />
      )}

      <WardCard
        ward={selectedWard}
        baseAqi={selectedWardAqi}
        simulatedAqi={selectedWardSimAqi}
        onClose={() => {
          setSelectedWard(null);
          setSelectedWardSimAqi(null);
        }}
      />

      {/* AQI LEGEND */}
      <div
        style={{
          position: "absolute",
          bottom: 38,
          left: 360,
          zIndex: 10,
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "7px 10px",
          background: "rgba(15, 23, 42, 0.93)",
          border: "1px solid rgba(148, 163, 184, 0.18)",
          borderRadius: 8,
          color: "#cbd5e1",
          fontFamily: "sans-serif",
          fontSize: 9,
          boxShadow: "0 4px 12px rgba(0,0,0,0.12)",
        }}
      >
        <strong
          style={{
            color: "#f8fafc",
          }}
        >
          AQI
        </strong>

        {legendItems.map(([color, label]) => (
          <span
            key={label}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
          >
            <span
              style={{
                width: 7,
                height: 7,
                borderRadius: "50%",
                background: color,
              }}
            />

            {label}
          </span>
        ))}
      </div>

      {/* DATA PROVENANCE */}
      <div
        style={{
          position: "absolute",
          bottom: 8,
          left: "50%",
          transform: "translateX(-50%)",
          zIndex: 10,
          padding: "5px 10px",
          background: "rgba(15, 23, 42, 0.9)",
          border: "1px solid rgba(148, 163, 184, 0.12)",
          borderRadius: 6,
          color: "#94a3b8",
          fontFamily: "sans-serif",
          fontSize: 9,
          whiteSpace: "nowrap",
        }}
      >
        Live AQI: Open-Meteo · Historical calibration: CPCB · Source
        model: MPCB
      </div>
    </div>
  );
}