#Brilliance — Multi‑source Research Assistant with AI Synthesis

##Brilliance is a full‑stack app that gathers recent papers from multiple scholarly sources, then produces an AI‑generated synthesis tailored to your query. It’s designed for quick local testing and simple cloud deployment.

##To use our existing react frontend, set FRONTEND_URL=brilliance-frontend.vercel.app

### Highlights
- **Multi‑source search**: arXiv, PubMed, OpenAlex
- **Smart query optimization** before fetching
- **AI synthesis** of combined results
- **Simple API**: single POST `/research`
- **Built‑in free tier**: default 2 requests per IP per 24h in production, with user‑provided API key override
- **Quick start**: React frontend + Flask backend, runs with one command locally

---

### Architecture
- **Backend**: Flask (`backend/brilliance/api/v1.py`) serves `/research` and `/health` and orchestrates tools in `brilliance/agents/*` and `brilliance/tools/*`.
- **Frontend**: React (CRA) in `frontend/` calls the backend, handles API key prompts, and renders the synthesis.

Directory layout (key parts only):
- `backend/brilliance/api/v1.py`: Flask app (CORS, rate‑limit, endpoints)
- `backend/brilliance/agents/`: query optimization + orchestration
- `backend/brilliance/tools/`: source-specific fetchers (arXiv, PubMed, OpenAlex)
- `backend/brilliance/synthesis/synthesis_tool.py`: AI synthesis
- `frontend/`: React UI (Search and Results)

---

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

Recommended: create a Python virtual environment in `backend/`.

---

### Quick Start (Local)
1) Backend deps
```
cd backend
python -m venv venv
source venv/bin/activate
pip install -r ../requirements.txt
```

2) Frontend deps
```
cd ../frontend
npm install
```

3) Run both (two terminals or a single concurrently command)
- Terminal A (backend):
```
cd backend && source venv/bin/activate
flask --app backend.brilliance.api.v1:app run --port 5000
```
- Terminal B (frontend):
```
cd frontend
npm start
```

Or one command from the repo root (requires Node):
```
npx -y concurrently -k -r -n FRONTEND,BACKEND -c blue,green \
  "npm --prefix ./frontend run start" \
  "./backend/venv/bin/flask --app backend.brilliance.api.v1:app run --port 5000"
```

Default local URL: `http://localhost:3000` (frontend) proxied to `http://localhost:5000` (backend).

---

### Configuration
Backend environment variables (set on your machine or in your platform):
- `FRONTEND_URL`: Comma‑separated list of allowed origins for CORS. Example: `https://your-frontend.app,http://localhost:3000`
  - Fallback: `CORS_ORIGINS` (same format). `*` allows any origin.
- `FREE_MESSAGES_PER_IP`: Free requests per IP per window. Default: `2` in production; set `0` for unlimited.
- `FREE_QUOTA_WINDOW_SECONDS`: Window length for the free tier. Default: `86400` (24h).
- `BYPASS_IPS`: Comma‑separated list of IPs that skip the quota (useful for local testing).
- `REQUIRE_API_KEY`: If set to `1`, all requests must include `X-User-Api-Key`.

Provider API keys:
- Users can provide their own key via request header `X-User-Api-Key` (stored in the browser locally by the frontend). The backend maps it to common env names (`OPENAI_API_KEY`, `XAI_API_KEY`, `GROK_API_KEY`, `ANTHROPIC_API_KEY`, `TOGETHER_API_KEY`, `GEMINI_API_KEY`) for downstream tools.
- For server‑side keys (optional), set the corresponding env var(s) directly.

Frontend:
- During development, CRA proxies API calls to `http://localhost:5000` via `frontend/package.json`.
- When deploying the frontend separately, set `REACT_APP_API_URL` to your backend URL at build time.

---

### API
Base URL: your backend (e.g., `http://localhost:5000` locally)

- `GET /health`
  - 200: `{ "status": "ok" }`

- `POST /research`
  - Headers: optional `X-User-Api-Key: <string>`
  - JSON body: `{ "query": "string", "max_results": number }`
    - `max_results` caps results per source; defaults to 3
  - Responses:
    - 200 OK: JSON with `summary`, `raw_results` (strings per source), and `synthesis` (AI text)
    - 400 Bad Request: `{ "error": "..." }` when `query` is missing
    - 402 Payment Required: `{ "message": "Free limit reached...", "remaining": 0, "reset_in": <seconds> }` — triggers the frontend’s API key prompt
    - 500 Internal Server Error: `{ "error": "..." }`

Example request:
```
curl -X POST http://localhost:5000/research \
  -H 'Content-Type: application/json' \
  -d '{"query":"protein folding breakthroughs","max_results":3}'
```

Add a user key to bypass the free tier:
```
curl -X POST http://localhost:5000/research \
  -H 'Content-Type: application/json' \
  -H 'X-User-Api-Key: sk-...your-key...' \
  -d '{"query":"protein folding breakthroughs"}'
```

---

### Rate Limits and Free Tier
- Defaults (recommended for production):
  - `FREE_MESSAGES_PER_IP=2`, `FREE_QUOTA_WINDOW_SECONDS=86400`
  - After the free quota, requests return HTTP 402; the frontend asks the user for an API key and retries
- Local unlimited options:
  - Set `FREE_MESSAGES_PER_IP=0`, or
  - Add your IP to `BYPASS_IPS`, or
  - Use the frontend’s key entry (sends `X-User-Api-Key`)
- IP detection honors `X-Forwarded-For` (left‑most value) for platforms like Heroku

Note: Quota is in‑memory per process; it resets on server restart and isn’t shared across workers.

---

### Deployment
Backend (Heroku example):
1) Create and push
```
heroku create brilliance-ws-demo
git push heroku HEAD:main
```
2) Config vars
```
heroku config:set FRONTEND_URL=https://<your-frontend-domain>,http://localhost:3000
heroku config:set FREE_MESSAGES_PER_IP=2
heroku config:set FREE_QUOTA_WINDOW_SECONDS=86400
heroku config:set BYPASS_IPS=1.2.3.4   # optional
```
3) Scale web dyno
```
heroku ps:scale web=1
```

Frontend (Vercel/Netlify or similar):
- Build with `REACT_APP_API_URL` pointing to your backend URL.
- If serving locally while backend is remote, set `REACT_APP_API_URL` in your local `.env` before `npm start`.

Procfile (already included) runs Gunicorn:
```
web: gunicorn backend.brilliance.api.v1:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60
```

---

### Local CLI (no HTTP)
Quickly exercise the backend pipeline without starting the server:
```
cd backend && source venv/bin/activate
python brilliance/cli.py "crispr gene editing 2025"
```

---

### Troubleshooting
- “Could not import `backend.brilliance.api.v1`”
  - Ensure the file exists and you’re running from the repo root, or provide the correct module path to Flask.
- CORS errors
  - Set `FRONTEND_URL` (or `CORS_ORIGINS`) to include your frontend origin.
- HTTP 402 after a few requests
  - Expected in production; provide `X-User-Api-Key` or adjust `FREE_MESSAGES_PER_IP`/`BYPASS_IPS`.

---

### Contributing
Issues and pull requests are welcome. Please:
- Keep code readable and well‑structured
- Add minimal reproduction steps for issues
- Avoid committing real API keys or secrets

---

### License
See `LICENSE` in this repository.

Heroku Deployment Guide

Overview
- Backend: Flask app at `backend/brilliance/api/v1.py` (served by Gunicorn)
- Frontend: CRA app under `frontend` (optional; can be hosted elsewhere)
- Quota: 2 free requests per IP per 24h, then user-supplied API key required

Prerequisites
- Heroku account and Heroku CLI installed
- Python 3.11+ locally for building if needed

Deploy Backend to Heroku
1) Create app
   heroku create brilliance-ws-demo

2) Push code
   git push heroku HEAD:main

3) Set config vars
   # Comma-separated list of allowed frontend origins
   heroku config:set FRONTEND_URL=https://<your-frontend-domain>,http://localhost:3000
   heroku config:set FREE_MESSAGES_PER_IP=2
   heroku config:set FREE_QUOTA_WINDOW_SECONDS=86400
   # Optional: bypass your IP (comma-separated list)
   heroku config:set BYPASS_IPS=1.2.3.4

4) Scale web dyno
   heroku ps:scale web=1

5) Open app
   heroku open

Notes
- Procfile binds Gunicorn to `$PORT` automatically.
- Quota counting is in-memory per dyno and per worker. It resets on dyno restart and is not shared across multiple workers.
- Heroku router forwards `X-Forwarded-For`. The app trusts the left-most value to identify the client IP.
- After hitting the free limit, requests return HTTP 402 with a message prompting for a user API key.
- The frontend stores the key locally and adds it to requests via `X-User-Api-Key`.

Frontend Options
Option A: Serve frontend elsewhere (e.g., Vercel/Netlify). Set `REACT_APP_API_URL` to your Heroku backend URL when building.
Option B: Deploy as a separate Heroku app. The CRA build can be served by static hosts. This repo keeps backend and frontend separated for simplicity.

Local Development
- Backend: export `FLASK_ENV=development` and run via `gunicorn backend.brilliance.api.v1:app --bind 0.0.0.0:5000` or `python -m backend.brilliance.api.v1`.
- Frontend: `cd frontend && npm install && npm start` (proxied to `http://localhost:5000`).

Security
- Never commit real API keys. The app accepts user keys at runtime and does not persist them server-side.
- If using a specific provider, set the corresponding env var name as needed. The backend attempts to map the provided key to common providers (`OPENAI_API_KEY`, `XAI_API_KEY`, `GROK_API_KEY`, `ANTHROPIC_API_KEY`, `TOGETHER_API_KEY`, `GEMINI_API_KEY`).
