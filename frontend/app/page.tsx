import { TripPlanner } from "../components/TripPlanner";

export default function HomePage() {
  return (
    <main className="page-shell">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Personal RAG travel planning</p>
          <h1>
            Travel<span className="title-accent">Sense</span>
          </h1>
          <p className="lede">
            Build an itinerary from curated city guides, saved places, trip ratings, food preferences,
            budget style, and pace constraints.
          </p>
          <div className="hero-actions">
            <span>City guides</span>
            <span>Personal notes</span>
            <span>Source-backed plans</span>
          </div>
        </div>
        <div className="hero-card">
          <p className="hero-card-label">Active memory</p>
          <div className="memory-list">
            <span>Travel preferences</span>
            <span>Budget style</span>
            <span>Food restrictions</span>
            <span>Past trip notes</span>
            <span>Saved places</span>
            <span>Trip ratings</span>
          </div>
        </div>
      </section>
      <TripPlanner />
    </main>
  );
}
