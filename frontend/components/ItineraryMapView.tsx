"use client";

import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect } from "react";
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from "react-leaflet";

export type MapStop = {
  label: string;
  lat: number;
  lng: number;
  index: number;
  detail?: string;
};

function numberedIcon(index: number): L.DivIcon {
  return L.divIcon({
    className: "stop-marker",
    html: `<span>${index}</span>`,
    iconSize: [30, 30],
    iconAnchor: [15, 15],
    popupAnchor: [0, -16],
  });
}

function FitBounds({ stops }: { stops: MapStop[] }) {
  const map = useMap();

  useEffect(() => {
    if (!stops.length) {
      return;
    }

    if (stops.length === 1) {
      map.setView([stops[0].lat, stops[0].lng], 14, { animate: false });
      return;
    }

    const bounds = L.latLngBounds(stops.map((stop) => [stop.lat, stop.lng] as [number, number]));
    map.fitBounds(bounds, { padding: [44, 44], maxZoom: 15, animate: false });
  }, [map, stops]);

  return null;
}

export default function ItineraryMapView({
  stops,
  routeGeometry,
}: {
  stops: MapStop[];
  // Real street-following path from /api/directions. GeoJSON coordinates are
  // [lng, lat]; falls back to a straight line between stops when absent
  // (routing failed, or there's nothing to route between yet).
  routeGeometry?: GeoJSON.LineString | null;
}) {
  const center: [number, number] = stops.length ? [stops[0].lat, stops[0].lng] : [20, 0];
  const line: [number, number][] = routeGeometry
    ? routeGeometry.coordinates.map(([lng, lat]) => [lat, lng])
    : stops.map((stop) => [stop.lat, stop.lng]);

  return (
    <MapContainer
      center={center}
      zoom={stops.length ? 13 : 2}
      scrollWheelZoom={false}
      className="leaflet-map"
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
      />
      {line.length > 1 ? (
        <Polyline
          // Keyed on route presence: Leaflet's setStyle() merges pathOptions
          // rather than replacing them, so dropping dashArray between
          // renders wouldn't otherwise clear it from an existing layer.
          key={routeGeometry ? "route" : "fallback"}
          positions={line}
          pathOptions={
            routeGeometry
              ? { color: "#0e7c86", weight: 4, opacity: 0.85 }
              : { color: "#0e7c86", weight: 4, opacity: 0.85, dashArray: "8 8" }
          }
        />
      ) : null}
      {stops.map((stop) => (
        <Marker key={`${stop.label}-${stop.index}`} position={[stop.lat, stop.lng]} icon={numberedIcon(stop.index)}>
          <Popup>
            <strong>{stop.label}</strong>
            {stop.detail ? <div>{stop.detail}</div> : null}
          </Popup>
        </Marker>
      ))}
      <FitBounds stops={stops} />
    </MapContainer>
  );
}
