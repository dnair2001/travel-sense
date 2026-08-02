"use client";

import dynamic from "next/dynamic";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "../lib/AuthContext";
import { requestJson } from "../lib/api";
import { Activity, DayPlan, FeedbackRating, GeocodeResult, TripResponse } from "../lib/types";
import type { MapStop } from "./ItineraryMapView";

const ItineraryMapView = dynamic(() => import("./ItineraryMapView"), {
  ssr: false,
  loading: () => <div className="map-loading">Loading map…</div>,
});

const feedbackOptions: { rating: FeedbackRating; label: string }[] = [
  { rating: "love", label: "Love" },
  { rating: "not_for_me", label: "Not for me" },
  { rating: "too_expensive", label: "Too expensive" },
  { rating: "too_much_walking", label: "Too much walking" },
  { rating: "too_touristy", label: "Too touristy" },
];

export function ItineraryResult({
  destination,
  result,
  refinement,
  onChangeRefinement,
  onRefine,
  isRefining,
  onFeedback,
  feedbackStatus,
  error,
  onBack,
}: {
  destination: string;
  result: TripResponse;
  refinement: string;
  onChangeRefinement: (value: string) => void;
  onRefine: () => void;
  isRefining: boolean;
  onFeedback: (day: number, activity: Activity, rating: FeedbackRating) => void;
  feedbackStatus: Record<string, string>;
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
            <DayCard day={day} feedbackStatus={feedbackStatus} key={day.day} onFeedback={onFeedback} />
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
          {isRefining ? "Updating..." : "Refine itinerary"}
        </button>
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

function DayCard({
  day,
  feedbackStatus,
  onFeedback,
}: {
  day: DayPlan;
  feedbackStatus: Record<string, string>;
  onFeedback: (day: number, activity: Activity, rating: FeedbackRating) => void;
}) {
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
            <div className="feedback-row no-print" aria-label={`Feedback for ${activity.title}`}>
              {feedbackOptions.map((option) => {
                const key = getFeedbackKey(day.day, activity.title, option.rating);
                return (
                  <button
                    className="feedback-button"
                    key={option.rating}
                    onClick={() => onFeedback(day.day, activity, option.rating)}
                    type="button"
                  >
                    {feedbackStatus[key] ?? option.label}
                  </button>
                );
              })}
            </div>
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

function ItineraryMap({ destination, day }: { destination: string; day: DayPlan }) {
  const { stops, loading } = useDayStops(destination, day);

  if (loading && stops.length === 0) {
    return (
      <div className="itinerary-map">
        <div className="map-loading">Locating stops…</div>
      </div>
    );
  }

  if (!loading && stops.length === 0) {
    return (
      <div className="itinerary-map">
        <div className="empty-state">
          <span>No mappable stops</span>
          <p>We couldn&apos;t find map locations for this day&apos;s activities.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="itinerary-map">
      <div className="map-canvas">
        <ItineraryMapView stops={stops} />
      </div>

      <div className="map-legend">
        <div>
          <span>Day {day.day}</span>
          <strong>{day.theme}</strong>
        </div>
        <ul>
          {stops.map((stop) => (
            <li key={`${stop.label}-${stop.index}`}>
              <span>{stop.index}</span>
              <div>
                <strong>{stop.label}</strong>
                <p>{stop.detail ?? "Mapped from itinerary context"}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function getFeedbackKey(day: number, title: string, rating: FeedbackRating): string {
  return `${day}-${title}-${rating}`;
}
