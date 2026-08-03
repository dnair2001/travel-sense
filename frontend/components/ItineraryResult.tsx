"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "../lib/AuthContext";
import { requestJson } from "../lib/api";
import { Activity, DayPlan, GeocodeResult, RouteResponse, TripResponse } from "../lib/types";
import type { MapStop } from "./ItineraryMapView";

const ItineraryMapView = dynamic(() => import("./ItineraryMapView"), {
  ssr: false,
  loading: () => <div className="map-loading">Loading map…</div>,
});

export function ItineraryResult({
  destination,
  result,
  refinement,
  onChangeRefinement,
  onRefine,
  isRefining,
  error,
  onBack,
}: {
  destination: string;
  result: TripResponse;
  refinement: string;
  onChangeRefinement: (value: string) => void;
  onRefine: () => void;
  isRefining: boolean;
  error: string | null;
  onBack: () => void;
}) {
  const [activeDay, setActiveDay] = useState(result.itinerary[0]?.day ?? 1);
  const activeDayPlan = result.itinerary.find((day) => day.day === activeDay) ?? result.itinerary[0] ?? null;

  return (
    <div className="result-shell">
      <button className="step-back no-print" onClick={onBack} type="button">
        ← Edit trip details
      </button>

      <section className="results-panel">
        <div className="panel-heading results-heading">
          <div>
            <p className="eyebrow">Generated plan</p>
            <h2>Itinerary</h2>
            <p>Each activity is grounded in retrieved destination and personal context.</p>
          </div>
          <div className="results-heading-actions no-print">
            <span className="mode-pill">{result.generation_mode === "llm" ? "LLM-backed" : "Demo fallback"}</span>
            <button className="secondary-button" onClick={() => window.print()} type="button">
              Download PDF
            </button>
          </div>
        </div>

        <div className="summary-card">
          <span>Trip summary</span>
          <p className="summary-text">{result.summary}</p>
        </div>

        <div className="map-shell no-print">
          <div className="map-shell-header">
            <div>
              <p className="eyebrow">Day map</p>
              <h3>{destination}</h3>
              <p>Stops are located from the itinerary's activity titles.</p>
            </div>
            <div className="day-tabs" role="tablist" aria-label="Select itinerary day">
              {result.itinerary.map((day) => (
                <button
                  className={day.day === activeDay ? "day-tab active" : "day-tab"}
                  key={day.day}
                  onClick={() => setActiveDay(day.day)}
                  type="button"
                >
                  Day {day.day}
                </button>
              ))}
            </div>
          </div>

          {activeDayPlan ? <ItineraryMap destination={destination} day={activeDayPlan} /> : null}
        </div>

        <div className="days-stack">
          {result.itinerary.map((day) => (
            <DayCard day={day} key={day.day} />
          ))}
        </div>
      </section>

      <section className="results-panel no-print">
        <div className="panel-heading">
          <p className="eyebrow">Refinement</p>
          <h2>Edit the plan</h2>
          <p>Ask for a lighter day, more food stops, fewer transfers, or a different pace.</p>
        </div>
        <textarea
          rows={3}
          value={refinement}
          onChange={(event) => onChangeRefinement(event.target.value)}
          placeholder="Make day 2 more food-focused"
        />
        <button className="secondary-button" disabled={isRefining} onClick={onRefine} type="button">
          {isRefining ? (
            <span className="button-loading">
              <span className="spinner" aria-hidden="true" />
              Updating...
            </span>
          ) : (
            "Refine itinerary"
          )}
        </button>
        {isRefining ? <p className="status-text">Reworking your plan — this usually takes 10–20 seconds.</p> : null}
        {error ? <p className="error-text">{error}</p> : null}
      </section>

      <section className="results-panel">
        <div className="panel-heading">
          <p className="eyebrow">Retrieved Sources</p>
          <h2>Why this was suggested</h2>
          <p>These are the city guide and personal memory documents retrieved for the plan.</p>
        </div>

        {result.sources.length ? (
          <div className="source-grid">
            {result.sources.map((source) => (
              <article className="source-card" key={`${source.city}-${source.title}`}>
                <div className="source-meta">
                  <span className={source.city === "personal" ? "source-badge personal" : "source-badge"}>
                    {source.city === "personal" ? "Personal memory" : source.city}
                  </span>
                  <span>{source.category}</span>
                </div>
                <h3>{source.title}</h3>
                <p>{source.excerpt}</p>
              </article>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <span>No sources yet</span>
            <p>Source cards will appear after generation.</p>
          </div>
        )}
      </section>
    </div>
  );
}

function DayCard({ day }: { day: DayPlan }) {
  return (
    <article className="day-card">
      <div className="day-card-header">
        <span>Day {day.day}</span>
        <div>
          <h3>{day.theme}</h3>
          <p>{day.activities.length} planned blocks</p>
        </div>
      </div>
      <div className="activity-list">
        {day.activities.map((activity) => (
          <div className="activity-card" key={`${day.day}-${activity.period}-${activity.title}`}>
            <span className="activity-dot" />
            <div className="activity-header">
              <p>{activity.period}</p>
              <strong>{activity.title}</strong>
            </div>
            <p>{activity.reason}</p>
            <small>{activity.source_titles.join(", ")}</small>
          </div>
        ))}
      </div>
    </article>
  );
}

// Geocodes each activity in the active day (title + destination) via the
// backend's Nominatim proxy, cached per query string so re-visiting a day
// tab doesn't re-fetch. Activities that don't resolve to a place just don't
// get a pin, rather than blocking the whole map.
function useDayStops(destination: string, day: DayPlan | null): { stops: MapStop[]; loading: boolean } {
  const { user } = useAuth();
  const [stops, setStops] = useState<MapStop[]>([]);
  const [loading, setLoading] = useState(false);
  const cacheRef = useRef<Map<string, GeocodeResult | null>>(new Map());

  useEffect(() => {
    if (!day || !destination.trim()) {
      setStops([]);
      setLoading(false);
      return;
    }

    let cancelled = false;
    // Clear any stale stops from the previously active day immediately, so
    // switching days always shows the loading state rather than leaving the
    // old day's map/legend sitting on screen (looking frozen) until the new
    // day's geocoding finishes.
    setStops([]);
    setLoading(true);

    async function resolve(activity: Activity): Promise<{ label: string; detail: string; result: GeocodeResult } | null> {
      const query = `${activity.title}, ${destination}`;
      const cache = cacheRef.current;
      if (cache.has(query)) {
        const cached = cache.get(query);
        return cached ? { label: activity.title, detail: activity.reason, result: cached } : null;
      }
      try {
        const geocoded = await requestJson<GeocodeResult>(`/api/geocode?query=${encodeURIComponent(query)}`, user);
        cache.set(query, geocoded);
        return { label: activity.title, detail: activity.reason, result: geocoded };
      } catch {
        cache.set(query, null);
        return null;
      }
    }

    Promise.all(day.activities.map(resolve)).then((resolved) => {
      if (cancelled) {
        return;
      }
      const nextStops: MapStop[] = resolved
        .filter((item): item is NonNullable<typeof item> => item !== null)
        .map((item, index) => ({
          label: item.label,
          lat: item.result.lat,
          lng: item.result.lng,
          index: index + 1,
          detail: item.detail,
          isApproximate: item.result.is_approximate,
        }));
      setStops(nextStops);
      setLoading(false);
    });

    return () => {
      cancelled = true;
    };
  }, [destination, day, user]);

  return { stops, loading };
}

// Fetches a real walking route through the resolved stops, in order, once
// there are at least two. Cached per exact coordinate sequence so re-visiting
// a day tab doesn't re-fetch. Falls back to no route (straight line, no leg
// details) if OSRM can't find one -- the map and legend still work without it.
function useDayRoute(stops: MapStop[]): { route: RouteResponse | null; loading: boolean } {
  const { user } = useAuth();
  const [route, setRoute] = useState<RouteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const cacheRef = useRef<Map<string, RouteResponse | null>>(new Map());

  const key = stops.map((stop) => `${stop.lat.toFixed(5)},${stop.lng.toFixed(5)}`).join(";");

  useEffect(() => {
    if (stops.length < 2) {
      setRoute(null);
      setLoading(false);
      return;
    }

    const cache = cacheRef.current;
    if (cache.has(key)) {
      setRoute(cache.get(key) ?? null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    requestJson<RouteResponse>("/api/directions", user, {
      payload: { coordinates: stops.map((stop) => [stop.lat, stop.lng]) },
    })
      .then((result) => {
        if (cancelled) return;
        cache.set(key, result);
        setRoute(result);
      })
      .catch(() => {
        if (cancelled) return;
        cache.set(key, null);
        setRoute(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, user]);

  return { route, loading };
}

function ItineraryMap({ destination, day }: { destination: string; day: DayPlan }) {
  const { stops, loading } = useDayStops(destination, day);
  const { route, loading: routeLoading } = useDayRoute(stops);

  if (loading) {
    return (
      <div className="itinerary-map">
        <div className="map-loading">
          <span className="spinner spinner-muted" aria-hidden="true" />
          Locating stops…
        </div>
      </div>
    );
  }

  if (stops.length === 0) {
    return (
      <div className="itinerary-map">
        <div className="empty-state">
          <span>No mappable stops</span>
          <p>We couldn&apos;t find map locations for this day&apos;s activities.</p>
        </div>
      </div>
    );
  }

  const mapsUrl = stops.length >= 2 ? buildGoogleMapsUrl(stops) : null;

  return (
    <div className="itinerary-map">
      <div className="map-canvas">
        <ItineraryMapView routeGeometry={route?.geometry} stops={stops} />
      </div>

      <div className="map-legend">
        <div>
          <span>Day {day.day}</span>
          <strong>{day.theme}</strong>
          {mapsUrl ? (
            <a className="google-maps-link" href={mapsUrl} target="_blank" rel="noopener noreferrer">
              Open full day in Google Maps ↗
            </a>
          ) : null}
        </div>
        <ul>
          {stops.map((stop, index) => (
            <li key={`${stop.label}-${stop.index}`}>
              <div className="map-legend-stop">
                <span>{stop.index}</span>
                <div>
                  <strong>{stop.label}</strong>
                  <p>{stop.detail ?? "Mapped from itinerary context"}</p>
                  {stop.isApproximate ? <small className="approx-badge">Approximate area</small> : null}
                </div>
              </div>
              {route?.legs[index] ? <RouteLegSummary leg={route.legs[index]} /> : null}
            </li>
          ))}
        </ul>
        {routeLoading ? <p className="status-text">Finding directions…</p> : null}
      </div>
    </div>
  );
}

// Deep link into Google Maps' multi-stop directions, in visiting order.
// No API key needed -- this is the documented consumer URL scheme, not the
// paid Directions API. Lets the rider pick walking/transit/driving live
// with Google's own (real, always up to date) routing for each mode.
function buildGoogleMapsUrl(stops: MapStop[]): string {
  const points = stops.map((stop) => `${stop.lat},${stop.lng}`);
  const waypoints = points.slice(1, -1);
  const params = new URLSearchParams({
    api: "1",
    origin: points[0],
    destination: points[points.length - 1],
    travelmode: "walking",
  });
  if (waypoints.length) {
    params.set("waypoints", waypoints.join("|"));
  }
  return `https://www.google.com/maps/dir/?${params.toString()}`;
}

function RouteLegSummary({ leg }: { leg: RouteResponse["legs"][number] }) {
  return (
    <p className="directions-leg">
      ↳ {formatDistance(leg.distance_m)} · Walk {formatDuration(leg.walking_duration_s)} · Drive{" "}
      {formatDuration(leg.driving_duration_s)}
    </p>
  );
}

function formatDistance(meters: number): string {
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)} km` : `${Math.round(meters)} m`;
}

function formatDuration(seconds: number): string {
  const minutes = Math.round(seconds / 60);
  if (minutes < 1) return "<1 min";
  if (minutes < 60) return `${minutes} min`;
  return `${Math.floor(minutes / 60)} hr ${minutes % 60} min`;
}
