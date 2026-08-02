"use client";

import { KeyboardEvent, useEffect, useState } from "react";

import { useAuth } from "../lib/AuthContext";
import { requestJson } from "../lib/api";
import type { IngestedSource, SourceIngestResponse, SourceListResponse } from "../lib/types";

export function SourceIngestForm({ destination }: { destination: string }) {
  const { user } = useAuth();
  const [url, setUrl] = useState("");
  const [sources, setSources] = useState<IngestedSource[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!destination.trim()) {
      setSources([]);
      return;
    }
    let cancelled = false;
    requestJson<SourceListResponse>(`/api/sources?destination=${encodeURIComponent(destination)}`, user)
      .then((data) => {
        if (!cancelled) {
          setSources(data.sources);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setSources([]);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [destination, user, status]);

  async function handleSubmit() {
    if (!url.trim() || !destination.trim()) {
      return;
    }
    setError(null);
    setStatus(null);
    setIsSubmitting(true);
    try {
      const result = await requestJson<SourceIngestResponse>("/api/sources", user, {
        payload: { destination, url },
      });
      setStatus(`Added "${result.title}" (${result.chunks_indexed} chunks).`);
      setUrl("");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Failed to add source.");
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      // This widget lives inside the outer trip-planning <form>, so it can't
      // be its own nested <form> (invalid HTML). Handle Enter manually here
      // so it adds a source instead of submitting the outer form.
      event.preventDefault();
      void handleSubmit();
    }
  }

  async function handleDelete(sourceUrl: string) {
    setError(null);
    try {
      await requestJson(`/api/sources`, user, { method: "DELETE", payload: { url: sourceUrl } });
      setStatus(`Removed source.`);
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : "Failed to remove source.");
    }
  }

  return (
    <section className="results-panel">
      <div className="panel-heading">
        <p className="eyebrow">Sources</p>
        <h2>Add blog or YouTube links</h2>
        <p>Submit links about {destination.trim() || "your destination"} to ground the itinerary in.</p>
      </div>

      <div className="source-ingest-form">
        <input
          disabled={!destination.trim()}
          onChange={(event) => setUrl(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="https://example.com/tokyo-food-guide"
          type="url"
          value={url}
        />
        <button
          className="primary-button"
          disabled={isSubmitting || !destination.trim() || !url.trim()}
          onClick={() => void handleSubmit()}
          type="button"
        >
          {isSubmitting ? "Adding..." : "Add source"}
        </button>
      </div>

      {status ? <p className="status-text">{status}</p> : null}
      {error ? <p className="error-text">{error}</p> : null}

      {sources.length ? (
        <ul className="source-list">
          {sources.map((source) => (
            <li key={source.url}>
              <div>
                <strong>{source.title}</strong>
                <span>
                  {source.source_type} · {source.chunk_count} chunks
                </span>
              </div>
              <button className="secondary-button" onClick={() => void handleDelete(source.url)} type="button">
                Remove
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <div className="empty-state">
          <span>No sources yet</span>
          <p>Add a link above to start building context for {destination.trim() || "this destination"}.</p>
        </div>
      )}
    </section>
  );
}
