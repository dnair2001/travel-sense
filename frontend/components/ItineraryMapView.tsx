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

export default function ItineraryMapView({ stops }: { stops: MapStop[] }) {
  const center: [number, number] = stops.length
    ? [stops[0].lat, stops[0].lng]
    : [35.6812, 139.7671];
  const line = stops.map((stop) => [stop.lat, stop.lng] as [number, number]);

  return (
    <MapContainer
      center={center}
      zoom={13}
      scrollWheelZoom={false}
      className="leaflet-map"
      style={{ height: "100%", width: "100%" }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
        url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
      />
      {line.length > 1 ? (
        <Polyline positions={line} pathOptions={{ color: "#1f6f54", weight: 4, opacity: 0.85, dashArray: "8 8" }} />
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
