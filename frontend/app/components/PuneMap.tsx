"use client";

import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

type Station = {
  id: number;
  name: string;
  lat: number | null;
  lon: number | null;
  sensors: string[];
};

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

export default function PuneMap() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);

  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

   const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {
          osm: {
            type: "raster",
            tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
            tileSize: 256,
            attribution: "© OpenStreetMap contributors",
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

    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("load", async () => {
      try {
        const res = await fetch(`${BACKEND}/api/aqi/pune`);
        const data = await res.json();
        const stations: Station[] = data.stations || [];

        stations.forEach((s) => {
          if (s.lat == null || s.lon == null) return;

          const popup = new maplibregl.Popup({ offset: 12 }).setHTML(
            `<strong>${s.name}</strong><br/>${s.sensors.join(", ")}`
          );

          new maplibregl.Marker({ color: "#2563eb" })
            .setLngLat([s.lon, s.lat])
            .setPopup(popup)
            .addTo(map);
        });
      } catch (err) {
        console.error("Failed to load stations:", err);
      }
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  return <div ref={mapContainer} style={{ width: "100%", height: "100vh" }} />;
}