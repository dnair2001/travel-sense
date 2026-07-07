"use client";

import { FormEvent, useState } from "react";

import type { SearchResponse, SearchResult } from "../lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const CITY_OPTIONS = [
  { value: "", label: "All" },
  { value: "Tokyo", label: "Tokyo" },
  { value: "Paris", label: "Paris" },
  { value: "New York City", label: "New York City" },
  { value: "personal", label: "Personal memory" },
];

export function SearchPanel() {
  const [query, setQuery] = useState("");
  const [city, setCity] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [searched, setSearched] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) return;

    setError(null);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/api/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: query.trim(), city, limit: 8 }),
      });

      if (!response.ok) {
        const body = await response.json().catch(() => null);
        const detail = typeof body?.detail === "string" ? body.detail : "Search failed.";
        throw new Error(detail);
      }

      const data: SearchResponse = await response.json();
      setResults(data.results);
      setSearched(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="results-panel search-panel">
      <div className="panel-heading">
        <p className="eyebrow">Knowledge search</p>
        <h2>Search guides &amp; notes</h2>
        <p>Find relevant city guides, saved places, and personal travel notes.</p>
      </div>

      <form className="search-form" onSubmit={handleSearch}>
        <div className="search-input-row">
          <input
            className="search-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. best ramen spots, museum tips, budget advice..."
          />
          <select
            className="search-city-filter"
            value={city}
            onChange={(e) => setCity(e.target.value)}
          >
            {CITY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
          <button className="primary-button search-button" type="submit" disabled={isLoading || !query.trim()}>
            {isLoading ? "Searching..." : "Search"}
          </button>
        </div>
      </form>

      {error ? <p className="error-text">{error}</p> : null}

      {searched && results.length === 0 ? (
        <div className="empty-state">
          <span>No results found</span>
          <p>Try a different query or broaden the city filter.</p>
        </div>
      ) : null}

      {results.length > 0 ? (
        <div className="search-results">
          {results.map((result, index) => (
            <article className="search-result-card" key={`${result.title}-${result.city}-${index}`}>
              <div className="source-meta">
                <span className={result.scope === "personal" ? "source-badge personal" : "source-badge"}>
                  {result.scope === "personal" ? "Personal memory" : result.city}
                </span>
                <span>{result.category}</span>
              </div>
              <h3>{result.title}</h3>
              <p>{result.excerpt}</p>
            </article>
          ))}
        </div>
      ) : null}
    </section>
  );
}
