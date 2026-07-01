"use client";
import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

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
};

const BACKEND = process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8000";

function categoryColor(category: string): string {
  switch (category) {
    case "Good": return "#15803d";
    case "Satisfactory": return "#4d7c0f";
    case "Moderate": return "#ca8a04";
    case "Poor": return "#c2410c";
    case "Very Poor": return "#b91c1c";
    case "Severe": return "#6b21a8";
    default: return "#4b5563";
  }
}

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
            attribution: "OpenStreetMap contributors",
          },
        },
        layers: [{ id: "osm", type: "raster", source: "osm" }],
      },
      center: [73.8567, 18.5204],
      zoom: 11,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl(), "top-right");

    map.on("load", async () => {
      try {
        const res = await fetch(`${BACKEND}/api/aqi/pune`);
        const data = await res.json();
        const wards: Ward[] = data.stations || [];
        wards.forEach((w) => {
          if (w.lat == null || w.lon == null) return;
          const color = categoryColor(w.category);
          const popup = new maplibregl.Popup({ offset: 12 }).setHTML(
            `<div style="color:#111827; font-family:sans-serif; font-size:13px; line-height:1.6; padding:4px 6px; min-width:150px;">
              <strong style="font-size:15px; color:#000;">${w.name}</strong><br/>
              AQI: <b style="color:${color}; font-size:14px;">${w.aqi ?? "-"}</b> <span style="color:#374151;">(${w.category})</span><br/>
              Dominant: <b>${w.dominant ?? "-"}</b><br/>
              PM2.5: ${w.pm25 ?? "-"} &nbsp;|&nbsp; PM10: ${w.pm10 ?? "-"}
            </div>`
          );
          new maplibregl.Marker({ color })
            .setLngLat([w.lon, w.lat])
            .setPopup(popup)
            .addTo(map);
        });
      } catch (err) {
        console.error("Failed to load wards:", err);
      }
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  return <div ref={mapContainer} style={{ width: "100%", height: "100vh" }} />;
}