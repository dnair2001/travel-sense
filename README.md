# TravelSense

TravelSense is a RAG-powered travel planner that generates personalized multi-day itineraries from curated destination guides. Users can enter a destination, trip length, budget, interests, pace, and travel constraints, then refine the itinerary with follow-up requests such as "make day 2 less walking-heavy."

## What This Builds

- A `Next.js` frontend for trip input and itinerary display
- A `FastAPI` backend for itinerary generation and refinement
- A small curated travel corpus for `Tokyo`, `Paris`, and `New York City`
- A `LangChain` ingestion pipeline with chunking and retrieval
- A `Chroma` vector store with metadata-aware search
- Source-backed itinerary recommendations

## Project Structure

```text
travel-sense/
  frontend/
  backend/
```

Backend highlights:

- `backend/data/`: Curated city guides in Markdown
- `backend/app/services/rag.py`: Ingestion, retrieval, itinerary generation
- `backend/app/ingest.py`: Rebuilds the vector store from source docs

Frontend highlights:

- `frontend/app/page.tsx`: Main page shell
- `frontend/components/TripPlanner.tsx`: Form, itinerary display, refinement flow

## Backend Setup

1. Create a virtual environment.
2. Install dependencies:

```bash
cd backend
pip install -r requirements.txt
```

3. Copy `.env.example` to `.env` and add your keys if you want LLM generation.

```bash
cp .env.example .env
```

4. Rebuild the vector store:

```bash
python -m app.ingest
```

5. Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

If `OPENAI_API_KEY` is missing, the app still works in demo mode:

- retrieval still uses LangChain chunking plus Chroma
- embeddings fall back to a local hash-based embedding class
- itinerary generation falls back to a deterministic template planner

That fallback keeps the project runnable while still letting you switch to a real LLM later.

## Frontend Setup

1. Install dependencies:

```bash
cd frontend
npm install
```

2. Copy `.env.local.example` to `.env.local`:

```bash
cp .env.local.example .env.local
```

3. Start the frontend:

```bash
npm run dev
```

The frontend expects the backend at `http://localhost:8000`.

## Environment Variables

Backend:

- `OPENAI_API_KEY`: Optional. Enables real itinerary generation and OpenAI embeddings.
- `OPENAI_MODEL`: Optional. Defaults to `gpt-4o-mini`.
- `CHROMA_DIR`: Optional. Defaults to `./chroma_db`.
- `COLLECTION_NAME`: Optional. Defaults to `travel-sense-docs`.

Frontend:

- `NEXT_PUBLIC_API_BASE_URL`: Optional. Defaults to `http://localhost:8000`.

## Core Learning Goals

This project is intentionally structured to make the main RAG concepts visible:

- `document loading`: load travel guides with metadata
- `chunking`: split guides into retrieval-friendly sections
- `embeddings`: encode chunks for similarity search
- `vector search`: retrieve relevant city-specific chunks
- `prompt grounding`: generate itineraries from retrieved context
- `citations`: show which source docs informed the plan

## Suggested Next Steps

- Add more cities by dropping Markdown files into `backend/data/<city>/`
- Improve metadata filtering with tags like `family`, `nightlife`, `rainy-day`
- Add saved trips in SQLite or Postgres
- Add itinerary export to PDF
- Replace demo mode with a fully LLM-backed refinement flow if needed
