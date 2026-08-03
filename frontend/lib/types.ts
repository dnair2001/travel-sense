export type BudgetLevel = "budget" | "mid-range" | "luxury";
export type PaceLevel = "slow" | "balanced" | "fast";

export type TripRequest = {
  destination: string;
  days: number;
  budget: BudgetLevel;
  interests: string[];
  travel_style: string;
  pace: PaceLevel;
  constraints: string;
};

export type Activity = {
  period: "Morning" | "Afternoon" | "Evening";
  title: string;
  reason: string;
  source_titles: string[];
};

export type DayPlan = {
  day: number;
  theme: string;
  activities: Activity[];
};

export type SourceSnippet = {
  title: string;
  city: string;
  category: string;
  excerpt: string;
};

export type TripResponse = {
  summary: string;
  itinerary: DayPlan[];
  sources: SourceSnippet[];
  generation_mode: "llm" | "demo";
};

export type SourceType = "blog" | "youtube";

export type SourceIngestResponse = {
  url: string;
  source_type: SourceType;
  title: string;
  chunks_indexed: number;
  city: string;
};

export type IngestedSource = {
  url: string;
  title: string;
  source_type: SourceType;
  city: string;
  ingested_at: string;
  chunk_count: number;
};

export type SourceListResponse = {
  sources: IngestedSource[];
};

export type GeocodeResult = {
  lat: number;
  lng: number;
  label: string;
  is_approximate: boolean;
};

export type RouteLeg = {
  distance_m: number;
  walking_duration_s: number;
  driving_duration_s: number;
};

export type RouteResponse = {
  geometry: GeoJSON.LineString;
  distance_m: number;
  walking_duration_s: number;
  driving_duration_s: number;
  legs: RouteLeg[];
};
