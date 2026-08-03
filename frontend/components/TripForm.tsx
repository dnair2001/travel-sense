"use client";

import { FormEvent } from "react";

import { TripRequest } from "../lib/types";
import { SourceIngestForm } from "./SourceIngestForm";

export function TripForm({
  trip,
  interestInput,
  daysInput,
  onChangeTrip,
  onChangeInterestInput,
  onChangeDaysInput,
  onSubmit,
  isLoading,
  error,
}: {
  trip: TripRequest;
  interestInput: string;
  daysInput: string;
  onChangeTrip: (updater: (current: TripRequest) => TripRequest) => void;
  onChangeInterestInput: (value: string) => void;
  onChangeDaysInput: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  isLoading: boolean;
  error: string | null;
}) {
  return (
    <form className="step-shell" onSubmit={onSubmit}>
      <div className="planner-panel">
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
              value={daysInput}
              onChange={(event) => onChangeDaysInput(event.target.value)}
              placeholder="e.g. 4"
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
      </div>

      <SourceIngestForm destination={trip.destination} />

      <button className="primary-button" disabled={isLoading} type="submit">
        {isLoading ? (
          <span className="button-loading">
            <span className="spinner" aria-hidden="true" />
            Generating plan...
          </span>
        ) : (
          "Generate itinerary"
        )}
      </button>

      {isLoading ? (
        <p className="status-text">
          Grounding your plan in the sources you added — this usually takes 10–20 seconds.
        </p>
      ) : null}

      {error ? <p className="error-text">{error}</p> : null}
    </form>
  );
}
