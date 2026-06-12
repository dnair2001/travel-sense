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

export type FeedbackRating = "love" | "not_for_me" | "too_expensive" | "too_much_walking" | "too_touristy";

export type ActivityFeedbackRequest = {
  destination: string;
  day: number;
  period: Activity["period"];
  title: string;
  rating: FeedbackRating;
  note: string;
  source_titles: string[];
};

export type ActivityFeedbackResponse = {
  saved: boolean;
  message: string;
};
