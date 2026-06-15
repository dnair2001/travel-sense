"use client";

import dynamic from "next/dynamic";
import { FormEvent, useState } from "react";

import { apiPost } from "../lib/api";
import { Activity, DayPlan, FeedbackRating, TripRequest, TripResponse } from "../lib/types";
import type { MapStop } from "./ItineraryMapView";

const ItineraryMapView = dynamic(() => import("./ItineraryMapView"), {
  ssr: false,
  loading: () => <div className="map-loading">Loading map…</div>,
});

const defaultTrip: TripRequest = {
  destination: "Tokyo",
  days: 4,
  budget: "mid-range",
  interests: ["food", "museums"],
  travel_style: "personalized traveler",
  pace: "balanced",
  constraints: "Avoid overly packed transit-heavy afternoons.",
};

const feedbackOptions: { rating: FeedbackRating; label: string }[] = [
  { rating: "love", label: "Love" },
  { rating: "not_for_me", label: "Not for me" },
  { rating: "too_expensive", label: "Too expensive" },
  { rating: "too_much_walking", label: "Too much walking" },
  { rating: "too_touristy", label: "Too touristy" },
];

type MapCity = "Tokyo" | "Paris" | "New York City";

type MapPoint = {
  label: string;
  lat: number;
  lng: number;
  aliases: string[];
};

const CITY_MAPS: Record<MapCity, { label: string; points: MapPoint[] }> = {
  Tokyo: {
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
  Paris: {
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
  "New York City": {
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

export function TripPlanner() {
  const [trip, setTrip] = useState<TripRequest>(defaultTrip);
  const [interestInput, setInterestInput] = useState(defaultTrip.interests.join(", "));
  const [refinement, setRefinement] = useState("Make day 2 less walking-heavy and add more local food.");
  const [result, setResult] = useState<TripResponse | null>(null);
  const [activeDay, setActiveDay] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefining, setIsRefining] = useState(false);
  const [feedbackStatus, setFeedbackStatus] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsLoading(true);

    const payload = { ...trip, interests: splitInterests(interestInput) };
    setTrip(payload);

    try {
      const data = await apiPost<TripResponse>("/api/itinerary", payload, "Failed to generate itinerary.");
      setResult(data);
      setActiveDay(data.itinerary[0]?.day ?? 1);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Something went wrong.");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleRefine() {
    if (!result) {
      return;
    }

    setError(null);
    setIsRefining(true);
    try {
      const data = await apiPost<TripResponse>(
        "/api/itinerary/refine",
        {
          trip: { ...trip, interests: splitInterests(interestInput) },
          current_summary: result.summary,
          current_itinerary: result.itinerary,
          instruction: refinement,
        },
        "Failed to refine itinerary.",
      );
      setResult(data);
      setActiveDay(data.itinerary[0]?.day ?? activeDay);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Something went wrong.");
    } finally {
      setIsRefining(false);
    }
  }

  async function handleFeedback(day: number, activity: Activity, rating: FeedbackRating) {
    const key = getFeedbackKey(day, activity.title, rating);
    setFeedbackStatus((current) => ({ ...current, [key]: "Saving..." }));
    setError(null);

    try {
      await apiPost(
        "/api/feedback",
        {
          destination: trip.destination,
          day,
          period: activity.period,
          title: activity.title,
          rating,
          note: "",
          source_titles: activity.source_titles,
        },
        "Failed to save feedback.",
      );

      setFeedbackStatus((current) => ({ ...current, [key]: "Saved" }));
    } catch (feedbackError) {
      setFeedbackStatus((current) => ({ ...current, [key]: "Try again" }));
      setError(feedbackError instanceof Error ? feedbackError.message : "Failed to save feedback.");
    }
  }

  const activeDayPlan = result?.itinerary.find((day) => day.day === activeDay) ?? result?.itinerary[0] ?? null;

  return (
    <section className="planner-grid">
      <form className="planner-panel" onSubmit={handleSubmit}>
        <div className="panel-heading">
          <p className="eyebrow">Trip brief</p>
          <h2>Plan a trip</h2>
          <p>Tell TravelSense what changes for this trip. Your saved memory handles the rest.</p>
        </div>

        <div className="field-row">
          <label>
            Destination
            <select
              value={trip.destination}
              onChange={(event) => setTrip((current) => ({ ...current, destination: event.target.value }))}
            >
              <option value="Tokyo">Tokyo</option>
              <option value="Paris">Paris</option>
              <option value="New York City">New York City</option>
            </select>
          </label>

          <label>
            Days
            <input
              type="number"
              min={1}
              max={14}
              value={trip.days}
              onChange={(event) => setTrip((current) => ({ ...current, days: Number(event.target.value) }))}
            />
          </label>
        </div>

        <label>
          Interests
          <input
            value={interestInput}
            onChange={(event) => setInterestInput(event.target.value)}
            placeholder="food, coffee shops, bookstores, neighborhoods"
          />
        </label>

        <label>
          Trip-specific preferences
          <textarea
            rows={4}
            value={trip.constraints}
            onChange={(event) => setTrip((current) => ({ ...current, constraints: event.target.value }))}
            placeholder="Low walking, vegetarian-friendly, no early mornings, near transit"
          />
        </label>

        <div className="memory-summary">
          <span>Budget from memory</span>
          <span>Pace from memory</span>
          <span>Food notes from memory</span>
          <span>Saved places weighted</span>
        </div>

        <button className="primary-button" disabled={isLoading} type="submit">
          {isLoading ? "Generating plan..." : "Generate itinerary"}
        </button>

        {error ? <p className="error-text">{error}</p> : null}
      </form>

      <div className="results-column">
        <section className="results-panel">
          <div className="panel-heading results-heading">
            <div>
              <p className="eyebrow">Generated plan</p>
              <h2>Itinerary</h2>
              <p>Each activity is grounded in retrieved destination and personal context.</p>
            </div>
            {result ? (
              <span className="mode-pill">
                {result.generation_mode === "llm" ? "LLM-backed" : "Demo fallback"}
              </span>
            ) : null}
          </div>

          {result ? (
            <>
              <div className="summary-card">
                <span>Trip summary</span>
                <p className="summary-text">{result.summary}</p>
              </div>
              <div className="map-shell">
                <div className="map-shell-header">
                  <div>
                    <p className="eyebrow">Day map</p>
                    <h3>{CITY_MAPS[trip.destination as MapCity]?.label ?? trip.destination}</h3>
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

                {activeDayPlan ? (
                  <ItineraryMap destination={trip.destination as MapCity} day={activeDayPlan} />
                ) : null}
              </div>
              <div className="days-stack">
                {result.itinerary.map((day) => (
                  <DayCard
                    day={day}
                    feedbackStatus={feedbackStatus}
                    key={day.day}
                    onFeedback={handleFeedback}
                  />
                ))}
              </div>
            </>
          ) : (
            <div className="empty-state">
              <span>No itinerary yet</span>
              <p>Generate a trip to see city guides and personal notes become a day-by-day plan.</p>
            </div>
          )}
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
            onChange={(event) => setRefinement(event.target.value)}
            placeholder="Make day 2 more food-focused"
          />
          <button className="secondary-button" disabled={!result || isRefining} onClick={handleRefine} type="button">
            {isRefining ? "Updating..." : "Refine itinerary"}
          </button>
        </section>

        <section className="results-panel">
          <div className="panel-heading">
            <p className="eyebrow">Retrieved Sources</p>
            <h2>Why this was suggested</h2>
            <p>These are the city guide and personal memory documents retrieved for the plan.</p>
          </div>

          {result?.sources?.length ? (
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
    </section>
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

function ItineraryMap({ destination, day }: { destination: MapCity; day: DayPlan }) {
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

function activitySearchText(activity: Activity): string {
  return normalizeText(`${activity.title} ${activity.reason} ${activity.source_titles.join(" ")}`);
}

function getStopsForDay(destination: MapCity, day: DayPlan): MapPoint[] {
  const catalog = CITY_MAPS[destination].points;
  const matched = day.activities.flatMap((activity) => {
    const text = activitySearchText(activity);
    return catalog.filter((point) => point.aliases.some((alias) => text.includes(alias)));
  });
  return dedupeStops(matched);
}

function getFallbackStops(destination: MapCity, day: DayPlan): MapPoint[] {
  const catalog = CITY_MAPS[destination].points;
  const fallback = [catalog[0], catalog[1] ?? catalog[0], catalog[2] ?? catalog[0]].filter(
    Boolean,
  ) as MapPoint[];
  return fallback.slice(0, Math.max(day.activities.length, 1));
}

function findActivityForStop(day: DayPlan, stopLabel: string): Activity | null {
  const normalizedStop = normalizeText(stopLabel);
  return (
    day.activities.find((activity) => activitySearchText(activity).includes(normalizedStop)) ?? null
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

function splitInterests(value: string): string[] {
  return value
    .split(",")
    .map((interest) => interest.trim())
    .filter(Boolean);
}


