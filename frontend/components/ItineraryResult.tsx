"use client";

import dynamic from "next/dynamic";
import { useState } from "react";

import { Activity, DayPlan, FeedbackRating, TripResponse } from "../lib/types";
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

type MapPoint = {
  label: string;
  lat: number;
  lng: number;
  aliases: string[];
};

// Pins only exist for these 3 seed destinations. Any other free-text
// destination falls back to a "map not available yet" message rather than
// crashing — real geocoding is future work.
const CITY_MAPS: Record<string, { label: string; points: MapPoint[] }> = {
  tokyo: {
    label: "Tokyo",
    points: [
      { label: "Tsukiji Outer Market", lat: 35.6655, lng: 139.7707, aliases: ["tsukiji outer market", "tsukiji"] },
      { label: "Shinjuku", lat: 35.6938, lng: 139.7036, aliases: ["shinjuku"] },
      { label: "Omoide Yokocho", lat: 35.6932, lng: 139.6997, aliases: ["omoide yokocho"] },
      { label: "Daikanyama T-Site", lat: 35.6485, lng: 139.6989, aliases: ["daikanyama t-site", "daikanyama"] },
      { label: "Yanaka Ginza", lat: 35.7276, lng: 139.7665, aliases: ["yanaka ginza", "yanaka"] },
      { label: "Kichijoji", lat: 35.7032, lng: 139.5797, aliases: ["kichijoji"] },
      { label: "Ueno", lat: 35.7141, lng: 139.7774, aliases: ["ueno"] },
      { label: "Asakusa", lat: 35.7119, lng: 139.7967, aliases: ["asakusa"] },
      { label: "Senso-ji", lat: 35.7148, lng: 139.7967, aliases: ["senso-ji", "sensoji"] },
      { label: "Akihabara", lat: 35.6984, lng: 139.7731, aliases: ["akihabara"] },
      { label: "Shibuya", lat: 35.6595, lng: 139.7005, aliases: ["shibuya"] },
      { label: "Ameya-Yokocho", lat: 35.7100, lng: 139.7745, aliases: ["ameya-yokocho", "ameya yokocho"] },
    ],
  },
  paris: {
    label: "Paris",
    points: [
      { label: "Rue Cler", lat: 48.8566, lng: 2.3050, aliases: ["rue cler"] },
      { label: "Le Marais", lat: 48.8575, lng: 2.3610, aliases: ["marais"] },
      { label: "Louvre", lat: 48.8606, lng: 2.3376, aliases: ["louvre"] },
      { label: "Tuileries", lat: 48.8634, lng: 2.3275, aliases: ["tuileries"] },
      { label: "Saint-Germain-des-Prés", lat: 48.8539, lng: 2.3338, aliases: ["saint-germain-des-pres", "saint germain des pres"] },
      { label: "Montmartre", lat: 48.8867, lng: 2.3431, aliases: ["montmartre"] },
      { label: "Latin Quarter", lat: 48.8499, lng: 2.3470, aliases: ["latin quarter"] },
      { label: "Île de la Cité", lat: 48.8550, lng: 2.3470, aliases: ["ile de la cite", "île de la cité", "cite"] },
      { label: "Seine", lat: 48.8566, lng: 2.3522, aliases: ["seine"] },
    ],
  },
  "new york city": {
    label: "New York City",
    points: [
      { label: "Central Park", lat: 40.7829, lng: -73.9654, aliases: ["central park"] },
      { label: "Museum Mile", lat: 40.7790, lng: -73.9630, aliases: ["museum mile"] },
      { label: "Upper West Side", lat: 40.7870, lng: -73.9754, aliases: ["upper west side"] },
      { label: "Chelsea Market", lat: 40.7424, lng: -74.0061, aliases: ["chelsea market"] },
      { label: "SoHo", lat: 40.7233, lng: -74.0030, aliases: ["soho"] },
      { label: "Greenwich Village", lat: 40.7336, lng: -74.0027, aliases: ["greenwich village"] },
      { label: "Times Square", lat: 40.7580, lng: -73.9855, aliases: ["times square"] },
      { label: "Grand Central", lat: 40.7527, lng: -73.9772, aliases: ["grand central"] },
      { label: "DUMBO", lat: 40.7033, lng: -73.9881, aliases: ["dumbo"] },
      { label: "Brooklyn Heights", lat: 40.6959, lng: -73.9936, aliases: ["brooklyn heights"] },
    ],
  },
};

function getCityMap(destination: string): { label: string; points: MapPoint[] } | undefined {
  const normalized = destination.trim().toLowerCase();
  const aliased = normalized === "nyc" || normalized === "new york" ? "new york city" : normalized;
  return CITY_MAPS[aliased];
}

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
      <button className="step-back" onClick={onBack} type="button">
        ← Edit trip details
      </button>

      <section className="results-panel">
        <div className="panel-heading results-heading">
          <div>
            <p className="eyebrow">Generated plan</p>
            <h2>Itinerary</h2>
            <p>Each activity is grounded in retrieved destination and personal context.</p>
          </div>
          <span className="mode-pill">{result.generation_mode === "llm" ? "LLM-backed" : "Demo fallback"}</span>
        </div>

        <div className="summary-card">
          <span>Trip summary</span>
          <p className="summary-text">{result.summary}</p>
        </div>

        <div className="map-shell">
          <div className="map-shell-header">
            <div>
              <p className="eyebrow">Day map</p>
              <h3>{getCityMap(destination)?.label ?? destination}</h3>
              <p>Numbered stops are inferred from the itinerary titles and notes.</p>
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

      <section className="results-panel">
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
            <div className="feedback-row" aria-label={`Feedback for ${activity.title}`}>
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

function ItineraryMap({ destination, day }: { destination: string; day: DayPlan }) {
  if (!getCityMap(destination)) {
    return (
      <div className="itinerary-map">
        <div className="empty-state">
          <span>Map not available yet</span>
          <p>We don&apos;t have mapped stops for {destination || "this destination"} yet.</p>
        </div>
      </div>
    );
  }

  const stops = getStopsForDay(destination, day);
  const orderedStops = stops.length ? stops : getFallbackStops(destination, day);
  const mapStops: MapStop[] = orderedStops.map((stop, index) => ({
    label: stop.label,
    lat: stop.lat,
    lng: stop.lng,
    index: index + 1,
    detail: findActivityForStop(day, stop.label)?.title ?? undefined,
  }));

  return (
    <div className="itinerary-map">
      <div className="map-canvas">
        <ItineraryMapView stops={mapStops} />
      </div>

      <div className="map-legend">
        <div>
          <span>Day {day.day}</span>
          <strong>{day.theme}</strong>
        </div>
        <ul>
          {orderedStops.map((stop, index) => (
            <li key={`${stop.label}-${index}`}>
              <span>{index + 1}</span>
              <div>
                <strong>{stop.label}</strong>
                <p>{findActivityForStop(day, stop.label)?.title ?? "Mapped from itinerary context"}</p>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function getStopsForDay(destination: string, day: DayPlan): MapPoint[] {
  const catalog = getCityMap(destination)?.points ?? [];
  const matched = day.activities.flatMap((activity) => {
    const text = normalizeText(`${activity.title} ${activity.reason} ${activity.source_titles.join(" ")}`);
    return catalog.filter((point) => point.aliases.some((alias) => text.includes(alias)));
  });
  return dedupeStops(matched);
}

function getFallbackStops(destination: string, day: DayPlan): MapPoint[] {
  const catalog = getCityMap(destination)?.points ?? [];
  if (!catalog.length) {
    return [];
  }
  const fallback = [catalog[0], catalog[1] ?? catalog[0], catalog[2] ?? catalog[0]].filter(
    Boolean,
  ) as MapPoint[];
  return fallback.slice(0, Math.max(day.activities.length, 1));
}

function findActivityForStop(day: DayPlan, stopLabel: string): Activity | null {
  const normalizedStop = normalizeText(stopLabel);
  return (
    day.activities.find((activity) =>
      normalizeText(`${activity.title} ${activity.reason} ${activity.source_titles.join(" ")}`).includes(normalizedStop),
    ) ?? null
  );
}

function dedupeStops(stops: MapPoint[]): MapPoint[] {
  const seen = new Set<string>();
  return stops.filter((stop) => {
    if (seen.has(stop.label)) {
      return false;
    }
    seen.add(stop.label);
    return true;
  });
}

function normalizeText(value: string): string {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function getFeedbackKey(day: number, title: string, rating: FeedbackRating): string {
  return `${day}-${title}-${rating}`;
}
