# Mini AI Chat — Project Overview

This repository contains a minimal local/chat demo that integrates a small frontend UI with a Python backend which forwards requests to a Generative Language model (Gemini) via a REST API. The project is suitable for local development, containerized deployment, and hosting on platforms like Render or Vercel (with adjustments).

**Repository layout**

- `api/`
	- `chat.py` — FastAPI application that exposes the chat API. Accepts POST requests and forwards prompts to the Gemini REST endpoint, extracts text from the model response, and returns JSON `{ "reply": "..." }`.
	- `requirements.txt` — Python dependencies used by the `api` app.
	- `.env` — (optional, local) environment variables for local runs (not committed in production).

- `frontend/`
	- `index.html` — Minimal chat UI shell and links to `styles.css` and `app.js`.
	- `styles.css` — Lightweight styling for the chat UI.
	- `app.js` — Frontend logic: sends POST requests to `/api/chat`, renders messages, and handles UI state.

- `Dockerfile` — Containerizes the application (copies `api/` and `frontend/`, installs dependencies, runs Uvicorn).
- `.dockerignore` — Files and folders excluded from the Docker build context.
- `vercel.json` — (optional) configuration for deploying the project to Vercel as static + serverless functions.

**What each part does and how they connect**

- Frontend (`frontend/`) runs in the browser and posts user messages to the backend at `/api/chat`.
- The backend (`api/chat.py`) is a FastAPI application that:
	- loads configuration from environment variables (or `api/.env` in development),
	- rate-limits requests per IP (simple in-memory sliding window),
	- constructs a prompt from optional history + user message,
	- calls the Gemini REST `generateContent` endpoint with a server-side API key,
	- extracts the reply text from the Gemini response shape and returns it to the frontend.
- The `Dockerfile` bundles `api/` and `frontend/` into a single container for hosting; the container exposes the configured port and runs Uvicorn.

**Tech stack**

- Frontend: plain HTML, CSS, and JavaScript (vanilla) — no build step.
- Backend: Python 3.12, FastAPI, httpx (async HTTP client), python-dotenv for local env loading.
- Server: Uvicorn (ASGI), optionally run behind Gunicorn for production processes.
- Containerization: Docker.
- Deployment: Render (Docker or native Python service) recommended for the full FastAPI app; Vercel can host the frontend and serverless functions (requires refactor of backend into per-file handlers or using `@vercel/python`).

**Important environment variables**

- `GEMINI_API_KEY` or `GOOGLE_API_KEY` — required to call the Gemini REST API.
- `MODEL` — model name to call, e.g. `gemini-2.5-flash` (defaults present in code).
- `MAX_OUTPUT_TOKENS` — max tokens returned from the model.
- `TEMPERATURE` — sampling temperature.

Example local `.env` (api/.env):

GEMINI_API_KEY=your_key_here
MODEL=gemini-2.5-flash
MAX_OUTPUT_TOKENS=1024
TEMPERATURE=0.4

**Running locally (recommended)**

1. Create and activate a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Install dependencies:

```powershell
pip install -r api/requirements.txt
```

3. Ensure environment variables are set (either in `api/.env` or export them in your shell).

4. Run the app with Uvicorn:

```powershell
python -m uvicorn api.chat:app --reload --host 127.0.0.1 --port 8000
```

5. Open `frontend/index.html` in a browser (or serve it from the same FastAPI app if configured) and test the chat.

**Building and running with Docker**

Build image (from repo root):

```bash
docker build -t chatbot:latest .
```

Run container (set the API key as an environment variable):

```bash
docker run -e GEMINI_API_KEY="your_key" -p 8000:8000 chatbot:latest
```

The app will listen on the port you mapped (default 8000).

**Deployment notes**

- Render: recommended for the full FastAPI container. Provide env vars in the Render Dashboard. Use Docker service or native Python Web Service with the start command that binds to `$PORT`.
- Vercel: good for static frontend hosting. To run backend on Vercel you'll need to refactor `api/chat.py` into a serverless handler compatible with `@vercel/python` (or deploy the backend elsewhere and point the frontend to that URL). `vercel.json` in this repo includes a `builds` configuration but Vercel serverless may need further changes.

**Endpoints**

- POST `/api/chat` — request body: `{ "message": "...", "history": [...] }` returns `{ "reply": "..." }`.
- GET `/api/health` — simple health/status response.
