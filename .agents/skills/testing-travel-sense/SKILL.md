---
name: testing-travel-sense
description: Test the TravelSense app end-to-end. Use when verifying backend API changes, security fixes, or frontend integration.
---

# Testing TravelSense

## Local Setup

### Backend
```bash
cd backend
source .venv/bin/activate
# Default (production-like): docs disabled
DEBUG=false uvicorn app.main:app --port 8000
# Debug mode: docs enabled at /docs and /redoc
DEBUG=true uvicorn app.main:app --port 8000
```

The backend uses demo fallback mode when `OPENAI_API_KEY` is not set — itineraries are generated from local Chroma vector store data without calling OpenAI. This is sufficient for most testing.

### Frontend
```bash
cd frontend
cp .env.local.example .env.local  # if .env.local doesn't exist
npm run dev  # serves at http://localhost:3000
```

## Devin Secrets Needed
- `OPENAI_API_KEY` (optional) — only needed to test live LLM-generated itineraries. Without it, the app falls back to demo/template responses.

## Key API Endpoints

| Endpoint | Method | Rate Limit | Purpose |
|----------|--------|------------|----------|
| `/api/health` | GET | 30/min | Health check |
| `/api/itinerary` | POST | 10/min | Generate itinerary |
| `/api/itinerary/refine` | POST | 10/min | Refine existing itinerary |
| `/api/feedback` | POST | 20/min | Submit activity feedback |

## Testing Patterns

### Input Validation
Send payloads exceeding field limits to verify 422 responses:
- `destination`: max 100 chars
- `interests` / `source_titles`: max 20 items
- `constraints` / `instruction` / `note`: max 1000 chars
- `current_summary`: max 2000 chars
- `days`: 1-14

```bash
# Example: oversized destination
curl -s -w "\nHTTP %{http_code}" -X POST http://localhost:8000/api/itinerary \
  -H "Content-Type: application/json" \
  -d '{"destination":"'$(python3 -c "print('A'*200)")'","days":2,"budget":"mid-range","interests":["food"],"travel_style":"solo","pace":"balanced","constraints":""}'
# Expected: HTTP 422
```

### Rate Limiting
Send requests in a tight loop. The rate limiter uses `slowapi` keyed by remote address:
```bash
for i in $(seq 1 12); do
  CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/itinerary \
    -H "Content-Type: application/json" \
    -d '{"destination":"Tokyo","days":2,"budget":"mid-range","interests":["food"],"travel_style":"solo","pace":"balanced","constraints":""}')
  echo "Request $i: HTTP $CODE"
done
# Expected: first 10 return 200, then 429
```

### CORS
```bash
# Allowed origin
curl -s -I -H "Origin: http://localhost:3000" http://localhost:8000/api/health | grep -i access-control
# Expected: access-control-allow-origin: http://localhost:3000

# Disallowed origin
curl -s -I -H "Origin: http://evil.com" http://localhost:8000/api/health | grep -i access-control
# Expected: no access-control-allow-origin header
```

### Docs Gating
```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/docs
# Expected: 404 when DEBUG=false, 200 when DEBUG=true
```

### Feedback Sanitization
Post feedback with dangerous characters (`< > [ ] \``), then check `backend/data/personal/activity_feedback.md` to confirm they were stripped.

### E2E UI Flow
1. Open `http://localhost:3000`
2. Default form has Tokyo, 4 days, food/museums interests
3. Click "Generate Itinerary"
4. Verify: trip summary, day map with tabs, activity cards with feedback buttons, retrieved sources panel
5. Note: shows "Demo fallback" badge when no OpenAI key is set — this is expected

## Tips
- Kill backend: `fuser -k 8000/tcp` (`lsof` may not be available)
- The backend writes feedback to `backend/data/personal/activity_feedback.md` — check this file after feedback sanitization tests
- `CORS_ORIGINS` env var controls allowed origins (comma-separated), defaults to `http://localhost:3000`
- Langchain ecosystem versions must be pinned carefully — see requirements.txt comments if you hit import errors
