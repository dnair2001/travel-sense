"use client";

import { FormEvent, useState } from "react";

import { useAuth } from "../lib/AuthContext";
import { requestJson } from "../lib/api";
import { TripRequest, TripResponse } from "../lib/types";
import { ItineraryResult } from "./ItineraryResult";
import { TripForm } from "./TripForm";

const defaultTrip: TripRequest = {
  destination: "Tokyo",
  days: 4,
  budget: "mid-range",
  interests: ["food", "museums"],
  travel_style: "personalized traveler",
  pace: "balanced",
  constraints: "Avoid overly packed transit-heavy afternoons.",
};

export function TripPlanner() {
  const { user } = useAuth();
  const [view, setView] = useState<"plan" | "result">("plan");
  const [trip, setTrip] = useState<TripRequest>(defaultTrip);
  const [interestInput, setInterestInput] = useState(defaultTrip.interests.join(", "));
  const [refinement, setRefinement] = useState("Make day 2 less walking-heavy and add more local food.");
  const [result, setResult] = useState<TripResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefining, setIsRefining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setIsLoading(true);

    const payload = { ...trip, interests: splitInterests(interestInput) };
    setTrip(payload);

    try {
      const data = await requestJson<TripResponse>("/api/itinerary", user, { payload });
      setResult(data);
      setView("result");
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
      const data = await requestJson<TripResponse>("/api/itinerary/refine", user, {
        payload: {
          trip: { ...trip, interests: splitInterests(interestInput) },
          current_summary: result.summary,
          current_itinerary: result.itinerary,
          instruction: refinement,
        },
      });
      setResult(data);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Something went wrong.");
    } finally {
      setIsRefining(false);
    }
  }

  if (view === "result" && result) {
    return (
      <ItineraryResult
        destination={trip.destination}
        error={error}
        isRefining={isRefining}
        onBack={() => setView("plan")}
        onChangeRefinement={setRefinement}
        onRefine={handleRefine}
        refinement={refinement}
        result={result}
      />
    );
  }

  return (
    <TripForm
      error={error}
      interestInput={interestInput}
      isLoading={isLoading}
      onChangeInterestInput={setInterestInput}
      onChangeTrip={setTrip}
      onSubmit={handleSubmit}
      trip={trip}
    />
  );
}

function splitInterests(value: string): string[] {
  return value
    .split(",")
    .map((interest) => interest.trim())
    .filter(Boolean);
}
