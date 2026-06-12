"use client";

import { FormEvent, useState } from "react";

import { Activity, DayPlan, FeedbackRating, TripRequest, TripResponse } from "../lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

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
  x: number;
  y: number;
  aliases: string[];
};

const CITY_MAPS: Record<MapCity, { label: string; points: MapPoint[] }> = {
  Tokyo: {
    label: "Tokyo",
    points: [
      { label: "Tsukiji Outer Market", x: 694, y: 386, aliases: ["tsukiji outer market", "tsukiji"] },
      { label: "Shinjuku", x: 262, y: 262, aliases: ["shinjuku"] },
      { label: "Omoide Yokocho", x: 242, y: 284, aliases: ["omoide yokocho"] },
      { label: "Daikanyama T-Site", x: 302, y: 330, aliases: ["daikanyama t-site", "daikanyama"] },
      { label: "Yanaka Ginza", x: 674, y: 190, aliases: ["yanaka ginza", "yanaka"] },
      { label: "Kichijoji", x: 166, y: 196, aliases: ["kichijoji"] },
      { label: "Ueno", x: 632, y: 152, aliases: ["ueno"] },
      { label: "Asakusa", x: 716, y: 170, aliases: ["asakusa"] },
      { label: "Senso-ji", x: 730, y: 180, aliases: ["senso-ji", "sensoji"] },
      { label: "Akihabara", x: 640, y: 150, aliases: ["akihabara"] },
      { label: "Shibuya", x: 262, y: 348, aliases: ["shibuya"] },
      { label: "Ameya-Yokocho", x: 612, y: 176, aliases: ["ameya-yokocho", "ameya yokocho"] },
    ],
  },
  Paris: {
    label: "Paris",
    points: [
      { label: "Rue Cler", x: 392, y: 400, aliases: ["rue cler"] },
      { label: "Le Marais", x: 570, y: 298, aliases: ["marais"] },
      { label: "Louvre", x: 522, y: 282, aliases: ["louvre"] },
      { label: "Tuileries", x: 490, y: 270, aliases: ["tuileries"] },
      { label: "Saint-Germain-des-Prés", x: 430, y: 336, aliases: ["saint-germain-des-pres", "saint germain des pres"] },
      { label: "Montmartre", x: 530, y: 148, aliases: ["montmartre"] },
      { label: "Latin Quarter", x: 488, y: 398, aliases: ["latin quarter"] },
      { label: "Île de la Cité", x: 520, y: 306, aliases: ["ile de la cite", "île de la cité", "cite"] },
      { label: "Seine", x: 516, y: 300, aliases: ["seine"] },
    ],
  },
  "New York City": {
    label: "New York City",
    points: [
      { label: "Central Park", x: 548, y: 150, aliases: ["central park"] },
      { label: "Museum Mile", x: 572, y: 170, aliases: ["museum mile"] },
      { label: "Upper West Side", x: 468, y: 190, aliases: ["upper west side"] },
      { label: "Chelsea Market", x: 492, y: 348, aliases: ["chelsea market"] },
      { label: "SoHo", x: 566, y: 392, aliases: ["soho"] },
      { label: "Greenwich Village", x: 530, y: 430, aliases: ["greenwich village"] },
      { label: "Times Square", x: 528, y: 268, aliases: ["times square"] },
      { label: "Grand Central", x: 600, y: 246, aliases: ["grand central"] },
      { label: "DUMBO", x: 670, y: 560, aliases: ["dumbo"] },
      { label: "Brooklyn Heights", x: 634, y: 520, aliases: ["brooklyn heights"] },
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
      const response = await fetch(`${API_BASE_URL}/api/itinerary`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response, "Failed to generate itinerary."));
      }

      const data: TripResponse = await response.json();
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
      const response = await fetch(`${API_BASE_URL}/api/itinerary/refine`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          trip: { ...trip, interests: splitInterests(interestInput) },
          current_summary: result.summary,
          current_itinerary: result.itinerary,
          instruction: refinement,
        }),
      });

      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response, "Failed to refine itinerary."));
      }

      const data: TripResponse = await response.json();
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
      const response = await fetch(`${API_BASE_URL}/api/feedback`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          destination: trip.destination,
          day,
          period: activity.period,
          title: activity.title,
          rating,
          note: "",
          source_titles: activity.source_titles,
        }),
      });

      if (!response.ok) {
        throw new Error(await getApiErrorMessage(response, "Failed to save feedback."));
      }

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
  const city = CITY_MAPS[destination];
  const stops = getStopsForDay(destination, day);
  const orderedStops = stops.length ? stops : getFallbackStops(destination, day);
  const points = orderedStops.map((stop, index) => ({ ...stop, index: index + 1 }));
  const path = points.map((point) => `${point.x},${point.y}`).join(" ");

  return (
    <div className="itinerary-map">
      <svg viewBox="0 0 1000 640" role="img" aria-label={`${city.label} itinerary map for day ${day.day}`}>
        <defs>
          <pattern id="grid" width="80" height="80" patternUnits="userSpaceOnUse">
            <path d="M 80 0 L 0 0 0 80" fill="none" stroke="rgba(23,35,38,0.06)" strokeWidth="1" />
          </pattern>
          <linearGradient id="mapFill" x1="0" x2="1" y1="0" y2="1">
            <stop offset="0%" stopColor="#f8f5ef" />
            <stop offset="100%" stopColor="#eef4f0" />
          </linearGradient>
        </defs>
        <rect x="0" y="0" width="1000" height="640" rx="24" fill="url(#mapFill)" />
        <rect x="0" y="0" width="1000" height="640" rx="24" fill="url(#grid)" />
        <path
          d={
            destination === "Tokyo"
              ? "M140 220 C240 110, 470 110, 640 180 C790 240, 850 340, 806 480 C756 590, 568 594, 392 548 C252 510, 120 370, 140 220 Z"
              : destination === "Paris"
                ? "M220 160 C360 90, 588 92, 746 192 C850 254, 872 390, 772 484 C646 600, 396 598, 228 500 C112 430, 100 236, 220 160 Z"
                : "M150 164 C260 80, 458 72, 638 148 C808 216, 870 354, 806 492 C742 620, 548 602, 372 554 C216 512, 100 330, 150 164 Z"
          }
          fill="rgba(255,255,255,0.35)"
          stroke="rgba(23,35,38,0.12)"
          strokeWidth="2"
        />
        {points.length > 1 ? (
          <polyline
            fill="none"
            points={path}
            stroke="var(--accent)"
            strokeDasharray="10 8"
            strokeWidth="5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        ) : null}
        {points.map((point) => (
          <g key={`${point.label}-${point.index}`} transform={`translate(${point.x} ${point.y})`}>
            <circle r="18" fill="rgba(15,118,110,0.15)" />
            <circle r="11" fill="var(--accent)" />
            <text x="0" y="4" textAnchor="middle" fontSize="12" fontWeight="900" fill="#ffffff">
              {point.index}
            </text>
            <text x="18" y="-16" fontSize="12" fontWeight="800" fill="var(--ink)">
              {point.label}
            </text>
          </g>
        ))}
      </svg>

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

function getStopsForDay(destination: MapCity, day: DayPlan): MapPoint[] {
  const catalog = CITY_MAPS[destination].points;
  const matched = day.activities.flatMap((activity) => {
    const text = normalizeText(`${activity.title} ${activity.reason} ${activity.source_titles.join(" ")}`);
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

function splitInterests(value: string): string[] {
  return value
    .split(",")
    .map((interest) => interest.trim())
    .filter(Boolean);
}

async function getApiErrorMessage(response: Response, fallback: string): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string | { msg?: string }[] };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail)) {
      return body.detail.map((item) => item.msg).filter(Boolean).join(" ") || fallback;
    }
  } catch {
    return fallback;
  }
  return fallback;
}
