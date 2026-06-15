---
name: testing-travel-sense
description: Test TravelSense end-to-end locally. Use when verifying UI or API changes to the itinerary planner.
---

# Testing TravelSense

## Prerequisites

- Python backend dependencies installed (`cd backend && pip install -r requirements.txt`)
- Node frontend dependencies installed (`cd frontend && npm install`)
- No external API keys needed — the app runs in **demo mode** without `OPENAI_API_KEY`

## Setup

1. **Copy env files** (if not already present):
   ```bash
   cp backend/.env.example backend/.env
   cp frontend/.env.local.example frontend/.env.local
   ```

2. **Ingest documents** (creates the Chroma vector store):
   ```bash
   cd backend && python -m app.ingest
   ```
   Expected output: `Indexed 15 documents into 18 chunks across 3 cities.`

3. **Start backend**:
   ```bash
   cd backend && uvicorn app.main:app --reload --port 8000
   ```
   Verify: `curl http://localhost:8000/api/health` should return `{"status":"ok"}`

4. **Start frontend**:
   ```bash
   cd frontend && npm run dev
   ```
   Runs on `http://localhost:3000`

## Core Test Flows

### 1. Generate Itinerary
- Open `http://localhost:3000`
- Default form: Tokyo, 4 days, interests "food, museums"
- Click "Generate itinerary"
- **Expect**: Trip summary card, 4 day tabs, map with numbered stops, source cards, "Demo fallback" pill

### 2. Activity Feedback
- After generating, scroll to activity cards
- Click "Love" on any activity
- **Expect**: Button text changes to "Saved" (not "Try again")

### 3. Refine Itinerary
- After generating, scroll to "Edit the plan" section
- Enter refinement text (e.g., "Make day 2 more food-focused")
- Click "Refine itinerary"
- **Expect**: Summary includes "Updated to reflect: [your text]", activities show "Refinement applied: [your text]"

### 4. Error Handling
- Test via API: `curl -s -X POST http://localhost:8000/api/itinerary -H 'Content-Type: application/json' -d '{"destination":"Atlantis","days":1,"budget":"mid-range","interests":[],"travel_style":"solo","pace":"balanced","constraints":""}'`
- **Expect**: HTTP 400 with `{"detail":"Unsupported destination 'Atlantis'. Available destinations: Paris, Tokyo, NYC."}`

## Running Automated Tests

```bash
# Backend unit tests (22 tests)
cd backend && python -m pytest tests/ -v

# Frontend type check
cd frontend && npx tsc --noEmit
```

## Supported Destinations

Tokyo, Paris, New York City (dropdown in the UI, API accepts "Tokyo", "Paris", "NYC")

## Notes

- Demo mode generates itineraries from pre-indexed city guide documents without calling OpenAI
- The `_build_llm()` method in `rag.py` is only exercised when `OPENAI_API_KEY` is set; demo mode bypasses it
- Map pins are matched via `activitySearchText()` which normalizes activity titles+reasons against known point aliases
- The frontend might show stale `.env.local.example` — if `NEXT_PUBLIC_API_BASE_URL` isn't set, it defaults to `http://localhost:8000`
