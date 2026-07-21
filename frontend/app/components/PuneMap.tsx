"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

import DashboardHeader from "./DashboardHeader";
import InterventionPanel from "./InterventionPanel";
import WardCard from "./WardCard";

import {
  AqiResponse,
  Ward,
  categoryColor,
  isUsableCurrentWard,
} from "./sentinelTypes";

const BACKEND =
  process.env.NEXT_PUBLIC_BACKEND_URL ||
  "http://localhost:8000";

export default function PuneMap() {
  const mapContainerRef =
    useRef<HTMLDivElement | null>(null);

  const mapRef =
    useRef<maplibregl.Map | null>(null);

  const markersRef =
    useRef<maplibregl.Marker[]>([]);

  const abortControllerRef =
    useRef<AbortController | null>(null);

  const [wards, setWards] =
    useState<Ward[]>([]);

  const [selectedWard, setSelectedWard] =
    useState<Ward | null>(null);

  const [loading, setLoading] =
    useState(true);

  const [backendReachable, setBackendReachable] =
    useState(true);

  const [error, setError] =
    useState<string | null>(null);

  const [dataSource, setDataSource] =
    useState("Open-Meteo · CAMS Global");

  /* ============================================================
     REMOVE EXISTING MARKERS
     ============================================================ */

  const clearMarkers =
    useCallback(() => {
      markersRef.current.forEach(
        (marker) => marker.remove()
      );

      markersRef.current = [];
    }, []);

  /* ============================================================
     RENDER MAP PINS
     ============================================================ */

  const renderMarkers =
    useCallback(
      (
        locations: Ward[],
        map: maplibregl.Map
      ) => {
        clearMarkers();

        locations.forEach((ward) => {
          if (
            typeof ward.lat !== "number" ||
            typeof ward.lon !== "number"
          ) {
            return;
          }

          const usable =
            isUsableCurrentWard(ward);

          const markerColor =
            usable
              ? categoryColor(ward.category)
              : "#64748b";

          /*
           * Marker wrapper.
           *
           * This is a BUTTON so it is keyboard-accessible
           * and reliably clickable.
           */

          const markerElement =
            document.createElement("button");

          markerElement.type = "button";

          markerElement.className =
            "sentinel-location-marker";

          markerElement.style.setProperty(
            "--pin-color",
            markerColor
          );

          markerElement.setAttribute(
            "aria-label",
            usable
              ? `${ward.name}, AQI ${Math.round(
                  ward.aqi ?? 0
                )}, ${ward.category}`
              : `${ward.name}, current AQI unavailable`
          );

          /*
           * Actual visual map pin.
           */

          const pin =
            document.createElement("span");

          pin.className =
            "sentinel-location-pin";

          /*
           * Small AQI number inside the pin.
           */

          const value =
            document.createElement("span");

          value.className =
            "sentinel-location-pin-value";

          value.textContent =
            usable && ward.aqi != null
              ? String(Math.round(ward.aqi))
              : "—";

          pin.appendChild(value);

          markerElement.appendChild(pin);

          /*
           * IMPORTANT:
           *
           * This is what opens WardCard.
           *
           * WardCard then fetches:
           *   /api/advisory/{ward}
           *   /api/enforce/{ward}
           *
           * Therefore Citizen Health Advisory becomes
           * visible after clicking a location.
           */

          markerElement.addEventListener(
            "click",
            (event) => {
              event.preventDefault();
              event.stopPropagation();

              setSelectedWard(ward);
            }
          );

          const marker =
            new maplibregl.Marker({
              element: markerElement,
              anchor: "bottom",
            })
              .setLngLat([
                ward.lon,
                ward.lat,
              ])
              .addTo(map);

          markersRef.current.push(
            marker
          );
        });
      },
      [clearMarkers]
    );

  /* ============================================================
     FETCH AQI
     ============================================================ */

  const fetchAqi =
    useCallback(async () => {
      abortControllerRef.current?.abort();

      const controller =
        new AbortController();

      abortControllerRef.current =
        controller;

      setLoading(true);

      setError(null);

      try {
        const response =
          await fetch(
            `${BACKEND}/api/aqi/pune`,
            {
              cache: "no-store",
              signal: controller.signal,
            }
          );

        if (!response.ok) {
          throw new Error(
            `AQI API returned HTTP ${response.status}`
          );
        }

        const data: AqiResponse =
          await response.json();

        const locations =
          Array.isArray(data.locations)
            ? data.locations
            : [];

        if (locations.length === 0) {
          throw new Error(
            "No Pune AQI locations were returned."
          );
        }

        setBackendReachable(true);

        setWards(locations);

        /*
         * If a ward panel is already open,
         * update it with the newest AQI context.
         */

        setSelectedWard(
          (currentWard) => {
            if (!currentWard) {
              return null;
            }

            return (
              locations.find(
                (ward) =>
                  ward.name ===
                  currentWard.name
              ) ?? null
            );
          }
        );

        /*
         * Render markers only when map exists.
         */

        if (mapRef.current) {
          renderMarkers(
            locations,
            mapRef.current
          );
        }

        /*
         * Optional source metadata.
         *
         * This does not assume these fields
         * always exist in the backend response.
         */

        const metadata =
          data as unknown as {
            data_source?: {
              provider?: string;
              underlying_model?: string;
            };
          };

        const provider =
          metadata.data_source
            ?.provider;

        const model =
          metadata.data_source
            ?.underlying_model;

        if (provider && model) {
          setDataSource(
            `${provider} · ${model}`
          );
        } else if (provider) {
          setDataSource(provider);
        } else if (model) {
          setDataSource(model);
        }
      } catch (err) {
        if (
          err instanceof DOMException &&
          err.name === "AbortError"
        ) {
          return;
        }

        console.error(
          "AQI fetch failed:",
          err
        );

        setBackendReachable(false);

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load AQI context."
        );
      } finally {
        if (
          !controller.signal.aborted
        ) {
          setLoading(false);
        }
      }
    }, [renderMarkers]);

  /* ============================================================
     INITIALIZE MAP
     ============================================================ */

  useEffect(() => {
    if (
      !mapContainerRef.current ||
      mapRef.current
    ) {
      return;
    }

    const map =
      new maplibregl.Map({
        container:
          mapContainerRef.current,

        style: {
          version: 8,

          sources: {
            osm: {
              type: "raster",

              tiles: [
                "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
              ],

              tileSize: 256,

              attribution:
                "© OpenStreetMap contributors",
            },
          },

          layers: [
            {
              id: "osm",

              type: "raster",

              source: "osm",

              paint: {
                /*
                 * Keep the real map clearly visible.
                 *
                 * The previous broken version made
                 * the map too dark / visually empty.
                 */

                "raster-saturation":
                  -0.12,

                "raster-contrast":
                  0.02,

                "raster-brightness-min":
                  0.48,

                "raster-brightness-max":
                  1,
              },
            },
          ],
        },

        /*
         * Pune city center.
         */

        center: [
          73.8567,
          18.5204,
        ],

        zoom: 10.6,

        minZoom: 9,

        maxZoom: 16,

        attributionControl: true,
      });

    mapRef.current = map;

    /*
     * Navigation controls.
     */

    map.addControl(
      new maplibregl.NavigationControl({
        showCompass: true,
        showZoom: true,
      }),

      "bottom-right"
    );

    const handleLoad =
      () => {
        /*
         * Resize after MapLibre initializes.
         *
         * Prevents the blank / partially sized
         * map problem.
         */

        map.resize();

        fetchAqi();
      };

    map.on(
      "load",
      handleLoad
    );

    /*
     * Browser resize support.
     */

    const handleResize =
      () => {
        map.resize();
      };

    window.addEventListener(
      "resize",
      handleResize
    );

    /*
     * Extra resize after dashboard layout settles.
     */

    const firstResize =
      window.setTimeout(
        () => {
          map.resize();
        },
        100
      );

    const secondResize =
      window.setTimeout(
        () => {
          map.resize();
        },
        400
      );

    return () => {
      window.clearTimeout(
        firstResize
      );

      window.clearTimeout(
        secondResize
      );

      window.removeEventListener(
        "resize",
        handleResize
      );

      map.off(
        "load",
        handleLoad
      );

      abortControllerRef.current?.abort();

      clearMarkers();

      map.remove();

      mapRef.current = null;
    };
  }, [
    clearMarkers,
    fetchAqi,
  ]);

  /* ============================================================
     COUNTS
     ============================================================ */

  const totalCount =
    wards.length;

  const availableCount =
    wards.filter(
      (ward) =>
        ward.data_available === true
    ).length;

  const freshCount =
    wards.filter(
      (ward) =>
        ward.data_fresh === true
    ).length;

  const usableCount =
    wards.filter(
      isUsableCurrentWard
    ).length;

  /* ============================================================
     RENDER
     ============================================================ */

  return (
    <div className="sentinel-dashboard">

      {/* ======================================================
          HEADER
          ====================================================== */}

      <DashboardHeader
        availableCount={
          availableCount
        }
        usableCount={
          usableCount
        }
        freshCount={
          freshCount
        }
        totalCount={
          totalCount
        }
        dataSource={
          dataSource
        }
        loading={
          loading
        }
        backendReachable={
          backendReachable
        }
        onRefresh={
          fetchAqi
        }
      />

      {/* ======================================================
          FULL MAP
          ====================================================== */}

      <div
        ref={
          mapContainerRef
        }
        className="sentinel-map"
      />

      {/* ======================================================
          VERY LIGHT MAP OVERLAY

          This must never intercept marker clicks.
          ====================================================== */}

      <div className="sentinel-map-overlay" />

      {/* ======================================================
          LOADING
          ====================================================== */}

      {loading &&
        wards.length === 0 && (
          <div className="sentinel-center-state sentinel-panel">

            <div className="sentinel-spinner" />

            <strong>
              Loading Pune air-quality context
            </strong>

            <span>
              Fetching the latest modeled
              pollutant context…
            </span>

          </div>
        )}

      {/* ======================================================
          ERROR
          ====================================================== */}

      {error &&
        wards.length === 0 && (
          <div className="sentinel-center-state sentinel-panel sentinel-error-state">

            <strong>
              AQI context unavailable
            </strong>

            <span>
              {error}
            </span>

            <button
              type="button"
              onClick={
                fetchAqi
              }
            >
              Retry
            </button>

          </div>
        )}

      {/* ======================================================
          INTERVENTION SIMULATOR

          IMPORTANT:
          The current InterventionPanel receives the actual wards.

          Simulation output represents estimated pollution-burden
          reduction. It must NOT recolor current AQI markers.
          ====================================================== */}

      {wards.length > 0 && (
        <InterventionPanel
          wards={wards}
          onResult={() => {
            /*
             * Deliberate no-op.
             *
             * Current AQI map markers represent
             * current modeled context only.
             */
          }}
        />
      )}

      {/* ======================================================
          AQI LEGEND
          ====================================================== */}

      {wards.length > 0 && (
        <div className="sentinel-map-legend sentinel-panel">

          <div>
            <span
              style={{
                background:
                  "#22c55e",
              }}
            />

            Good
          </div>

          <div>
            <span
              style={{
                background:
                  "#84cc16",
              }}
            />

            Satisfactory
          </div>

          <div>
            <span
              style={{
                background:
                  "#eab308",
              }}
            />

            Moderate
          </div>

          <div>
            <span
              style={{
                background:
                  "#f97316",
              }}
            />

            Poor
          </div>

          <div>
            <span
              style={{
                background:
                  "#ef4444",
              }}
            />

            Very Poor
          </div>

          <div>
            <span
              style={{
                background:
                  "#a855f7",
              }}
            />

            Severe
          </div>

        </div>
      )}

      {/* ======================================================
          WARD INTELLIGENCE

          This is the existing working WardCard.

          Clicking a map pin sets selectedWard.

          WardCard then fetches:
          /api/advisory/{ward}
          /api/enforce/{ward}

          Citizen Health Advisory is already implemented
          inside WardCard.
          ====================================================== */}

      <WardCard
        selectedWard={
          selectedWard
        }
        onClose={() =>
          setSelectedWard(null)
        }
      />

      {/* ======================================================
          DATA DISCLAIMER
          ====================================================== */}

      <div className="sentinel-map-disclaimer">
        Modeled decision-support context ·
        not an official CPCB monitoring-station observation
      </div>

    </div>
  );
}