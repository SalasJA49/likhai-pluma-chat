# Likhai / Pluma Chat — Developer Quickstart

This repository is a small example web app with a React + Vite frontend and a Django backend. It was built around a style-writing UX and may connect to Azure services (OpenAI/Foundry, Cosmos DB, Blob storage). This README explains the pieces in plain English, how they connect, and step-by-step instructions for running locally (dev) and with Docker Compose.

If you're new to Django, JavaScript or Vite — no worries. Read the "High-level overview" first, then use the step-by-step commands under "Run locally" or "Run with Docker".

## Quick summary (in one line)
- Frontend: React + Vite (served by the `frontend` service or nginx in Docker). The frontend calls `/api/*` to talk to the backend.
- Backend: Django REST endpoints under `backend/api/` which provide /styles/, /rewrite/, chat endpoints and more.
- nginx (in docker-compose) proxies `/api/` to the backend and serves the built frontend — use `http://localhost:8080` when running via Docker Compose.

---

## High-level architecture (how things connect)

- Browser → Frontend (React/Vite)
	- The app is served from the frontend service (or via nginx when using Docker Compose).
	- The frontend makes API calls to the same origin path `/api/...`. When using nginx (port 8080), that path gets forwarded to the Django backend.

- nginx (Docker Compose) — when present, listens on host port 8080 and:
	- serves the frontend static files (the built Vite app)
	- proxies `/api/` to the Django backend (internal container:8000)

- Backend: Django (server code under `backend/`)
	- Implements API endpoints under `backend/api/` (views, repositories, models).
	- Persists styles/outputs either to Django models (Postgres/SQLite) or to Cosmos (Azure) depending on environment variables.

- Optional Azure services (if configured via env variables):
	- Azure OpenAI / Foundry for LLM inference
	- Azure Cosmos DB for storing styles / outputs (when AZURE_COSMOS_* env vars are set)
	- Azure Blob Storage (APP_AZURE_STORAGE_*) for file artifacts

Diagram (simplified):

Browser <---> nginx (host:8080) <---> frontend static files
													|---> /api/ --> backend (Django running at :8000)
																									|--> Cosmos (if configured)
																									|--> Azure OpenAI for LLM calls

---

## Where key code lives (quick map)

- Frontend (React + Vite)
	- `frontend/` — the React app (TypeScript + Vite). Entry: `frontend/src/main.tsx`, pages in `frontend/src/pages/`.
	- `frontend/src/lib/api.ts` — central API wrapper using axios (baseURL = `/api`). Important: the frontend expects the API at the same origin under `/api/`.
	- `frontend/src/pages/Writer.tsx` — the Style Writer UI that shows the styles drop-down by calling `fetchStyles()`.

- Backend (Django)
	- `backend/` — Django project. Main API: `backend/api/`.
	- `backend/api/views.py` — Django REST views that implement `/api/styles/`, `/api/rewrite/`, chat endpoints, etc.
	- `backend/api/repositories/` — repository layer. Contains two implementations:
		- `repo_django.py` — uses Django models in the project DB
		- `repo_cosmos.py` — uses Azure Cosmos DB when AZURE_COSMOS_* env vars are present or when `DATA_STORE=cosmos`
		- `factory.py` — logic that chooses between Django vs Cosmos repo depending on environment variables
	- `backend/api/models.py` — Django models (Style, Output) when using the Django repo

---

## Before you run: environment (.env) notes — Azure-focused

- This project uses a `.env` file for docker-compose and for local runs. Keep these points in mind:
	- Format exactly: KEY=value (no extra spaces around `=`) and avoid wrapping values in quotes unless you *intend* the quotes to be literal characters. Example:

```env
AZURE_COSMOS_ENDPOINT=https://example.documents.azure.com:443/
AZURE_COSMOS_KEY=abcd-very-long-key
AZURE_COSMOS_DATABASE=stylewriter

AZURE_OPENAI_ENDPOINT=https://your-openai-resource.cognitiveservices.azure.com/
AZURE_OPENAI_KEY=your_key_here
```

	- If you see lines like `AZURE_OPENAI_ENDPOINT = "https://..."` (note spaces and quotes), docker-compose may treat that differently — remove the spaces around `=` and the surrounding quotes.
	- Important env variables (Azure-related):
		- `AZURE_OPENAI_ENDPOINT` — endpoint for Azure OpenAI/Foundry
		- `AZURE_OPENAI_KEY` — API key
		- `AZURE_COSMOS_ENDPOINT` — Cosmos endpoint
		- `AZURE_COSMOS_KEY` — Cosmos key
		- `AZURE_COSMOS_DATABASE` — Cosmos DB database name
		- `APP_AZURE_STORAGE_ACCOUNT` / `APP_AZURE_STORAGE_ACCESS_KEY` — Azure Blob storage credentials (optional)
		- `DATABASE_URL` — if you use a hosted Postgres (or Citus/Cosmos Postgres)

How the backend picks data storage:
- If `DATA_STORE=cosmos` OR `AZURE_COSMOS_ENDPOINT` + `AZURE_COSMOS_KEY` + `AZURE_COSMOS_DATABASE` are present, the backend will instantiate the Cosmos repository and read/write styles from Cosmos.
- Otherwise it will use the Django models (local DB).

---

## Run locally (development mode — fast feedback, recommended for development)

1) Backend (Django dev server)

Open a terminal, make sure Python 3.12+ is available and the `backend/requirements.txt` (or the top-level `requirements.txt`) packages are installed in a virtualenv. Then:

```bash
# from repo root
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# set DJANGO_SETTINGS_MODULE if needed: export DJANGO_SETTINGS_MODULE=server.settings
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

This runs the Django dev server on port 8000. The API is available at `http://localhost:8000/api/`.

2) Frontend (Vite development server)

Open another terminal:

```bash
cd frontend
npm install   # or yarn
npm run dev
```

By default `npm run dev` serves the frontend on port 5173 or the configured dev port. When developing locally you will often run the frontend directly (hosted by Vite). Note: the frontend's axios instance calls `/api/...` on the same origin; if running Vite on a different port you may need to configure a proxy (see `vite.config.ts`) or run the backend on a port that the Vite dev server proxies to.

Quick dev-tip: when you run the frontend directly on a different port (for example port 3000 or 5173), the browser will try to call `/api/styles/` on that same origin. To reach the Django API you can either:
- open the app through nginx (see Docker section) OR
- set Vite proxy so `/api` requests are forwarded to `http://localhost:8000` in development.

---

## Run with Docker Compose (recommended for reproducing the production-ish setup)

This repository includes a `docker-compose.yml` with three main services: `backend`, `frontend`, and `nginx`.

Start everything with build:

```bash
docker compose up --build
```

What to expect:
- nginx listens on host port **8080** and proxies `/api/` to the backend and serves the frontend.
- frontend container may also expose port 3000 (the dev server) — avoid opening that in the browser for the full integrated behavior.

When running compose, open the app at:

- http://localhost:8080 — this is the nginx front which will serve the frontend and proxy `/api/` to Django. Using this URL avoids CORS and proxy issues.

Important note: If you open the frontend directly on port 3000 (or Vite's dev port), the calls to `/api` will go to that origin and typically return 404 because that container is not proxying API paths to the backend. This is a common source of confusion — if the UI looks broken or lists are empty, try `http://localhost:8080`.

---

## Troubleshooting checklist (common gotchas explained simply)

1) Styles dropdown is empty in the UI
	 - Likely cause: you're loading the frontend on a different origin (for example `:3000`) and `/api/styles/` is requested on that origin and returns 404. Solution: open `http://localhost:8080` (nginx) so `/api/` is proxied to the backend.
	 - Another cause: backend didn't detect Cosmos env or DB is empty. Check the backend logs and `curl http://localhost:8080/api/styles/` from the host to confirm a JSON response.

2) .env formatting problems
	 - Ensure `KEY=value` (no spaces around `=`) and avoid wrapping values in quotes. Docker Compose uses `env_file` which expects this format.

3) Backend seems to pick wrong repository (Django vs Cosmos)
	 - The backend automatically picks Cosmos repo when AZURE_COSMOS_ENDPOINT + AZURE_COSMOS_KEY + AZURE_COSMOS_DATABASE are present. If those are present but invalid, connections may fail. If you want to force Django models, set `DATA_STORE=django`.

4) CSRF / withCredentials
	 - The frontend axios instance sets `withCredentials=true` and configures CSRF cookie names (csrftoken). When using nginx to proxy and same-origin requests, CSRF should work as expected for browser requests. If you see 403 errors on POST, check that cookies are being set and sent and that axios is using `credentials: 'include'`.

5) How to quickly inspect API responses
	 - From your host machine (not inside the browser), run:

```bash
curl -i http://localhost:8080/api/styles/
```

If that returns `200` and JSON list items with `id`, `name`, `style`, `example`, then the backend is serving styles correctly.

---

## Useful debug commands (copy-paste)

Check containers:
```bash
docker compose ps
```

Tail nginx logs:
```bash
docker compose logs -f nginx
```

Tail backend logs:
```bash
docker compose logs -f backend
```

Get backend env vars (quick check to see what the backend sees):
```bash
docker compose exec backend env | grep -E "AZURE_COSMOS|AZURE_OPENAI|DATA_STORE|DATABASE_URL" || true
```

Check the proxied styles endpoint from the host:
```bash
curl -sS http://localhost:8080/api/styles/ | jq '.[0] | {id,name}'
```

---

## Key files to open next (if you want to learn the code)

- `frontend/src/lib/api.ts` — where frontend calls are defined (fetchStyles, rewrite, chat endpoints)
- `frontend/src/pages/Writer.tsx` — UI that shows styles and calls `rewrite()`
- `backend/api/views.py` — API entrypoints for styles/chat/rewrite
- `backend/api/repositories/factory.py` — how the backend chooses Django vs Cosmos repo
- `backend/api/repositories/repo_cosmos.py` — how the Cosmos implementation queries containers
- `backend/api/repositories/repo_django.py` — how the Django model implementation works

---

## FAQ

- Q: "When I use Docker Compose the UI is empty but local dev works — why?"
	- A: Likely because you opened the frontend directly at the dev server port (ex: 3000). The docker-compose setup expects you to use nginx (8080) so `/api/` requests are correctly proxied to the backend. Open `http://localhost:8080`.

- Q: "I changed my `.env` but the container doesn't pick it up"
	- A: Rebuild and restart: `docker compose up --build` — also ensure `.env` lines have no spaces around `=`.

---

## Next steps I can do for you (offer)

- Add an `env.sample` with example Azure keys (placeholder values) to make onboarding easier
- Add a short shell script `start-dev.sh` that runs backend and frontend in two terminals for local dev
- Remove publishing of `frontend:3000` from `docker-compose.yml` to avoid confusion and force use of nginx

If you'd like one of these, tell me which and I'll add it.

---

Happy hacking — if anything is unclear, tell me which part you want simpler and I will rewrite it.

