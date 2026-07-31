"use client";

import { FormEvent } from "react";

import { TripRequest } from "../lib/types";
import { SourceIngestForm } from "./SourceIngestForm";

export function TripForm({
  trip,
  interestInput,
  onChangeTrip,
  onChangeInterestInput,
  onSubmit,
  isLoading,
  error,
}: {
  trip: TripRequest;
  interestInput: string;
  onChangeTrip: (updater: (current: TripRequest) => TripRequest) => void;
  onChangeInterestInput: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  isLoading: boolean;
  error: string | null;
}) {
  return (
    <div className="step-shell">
      <form className="planner-panel" onSubmit={onSubmit}>
        <div className="panel-heading">
          <p className="eyebrow">Trip brief</p>
          <h2>Plan a trip</h2>
          <p>Tell TravelSense where you're headed. Your added sources ground the itinerary.</p>
        </div>

        <div className="field-row">
          <label>
            Destination
            <input
              value={trip.destination}
              onChange={(event) => onChangeTrip((current) => ({ ...current, destination: event.target.value }))}
              placeholder="Any city, e.g. Lisbon"
            />
          </label>

          <label>
            Days
            <input
              type="number"
              min={1}
              max={14}
              value={trip.days}
              onChange={(event) => onChangeTrip((current) => ({ ...current, days: Number(event.target.value) }))}
            />
          </label>
        </div>

        <label>
          Interests
          <input
            value={interestInput}
            onChange={(event) => onChangeInterestInput(event.target.value)}
            placeholder="food, coffee shops, bookstores, neighborhoods"
          />
        </label>

        <label>
          Trip-specific preferences
          <textarea
            rows={4}
            value={trip.constraints}
            onChange={(event) => onChangeTrip((current) => ({ ...current, constraints: event.target.value }))}
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

      <SourceIngestForm destination={trip.destination} />
    </div>
  );
}
