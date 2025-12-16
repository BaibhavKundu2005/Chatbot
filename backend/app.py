import os
import time
import logging
from typing import List, Optional, Dict, Any

import httpx
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

# Load local .env for development (safe to use locally; ensure .env is in .gitignore)
load_dotenv()

# ---------- Configuration ----------
FRONTEND_DIR = os.getenv("FRONTEND_DIR", "../frontend")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
MODEL = os.getenv("MODEL", "gemini-2.5-flash")  # change to a model you have access to
MAX_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "1024"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.4"))

# Rate limiting (in-memory, non-persistent)
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_MAX_PER_WINDOW = int(os.getenv("RATE_LIMIT_MAX_PER_WINDOW", "30"))
_ip_timestamps: Dict[str, List[float]] = {}

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend")

if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable not set. /api/chat will error until provided.")

app = FastAPI(title="Mini AI Chat Backend (Gemini)")

# CORS - loose for local dev; tighten in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # change to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")



class ChatRequest(BaseModel):
    message: str
    # Optional short history: list of {"role": "user"|"assistant"|"system", "content": "..."}
    history: Optional[List[Dict[str, str]]] = None


def check_rate_limit(ip: str) -> None:
    """Simple sliding-window rate limiter per IP."""
    now = time.time()
    arr = _ip_timestamps.setdefault(ip, [])
    # remove old timestamps
    while arr and arr[0] < now - RATE_LIMIT_WINDOW_SECONDS:
        arr.pop(0)
    if len(arr) >= RATE_LIMIT_MAX_PER_WINDOW:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests — slow down.")
    arr.append(now)


def build_prompt_from_history(history: Optional[List[Dict[str, str]]], user_message: str) -> str:
    """
    Convert an optional history into a single prompt string, then append the user's message.
    This keeps compatibility without assuming a chat-specific Gemini payload format.
    """
    parts: List[str] = []
    if history:
        for item in history:
            role = item.get("role", "user")
            content = item.get("content", "")
            parts.append(f"{role}: {content}")
    parts.append(f"user: {user_message}")
    # Join with double newline to keep boundaries clear
    return "\n\n".join(parts)


async def call_gemini_generate(prompt_text: str) -> Dict[str, Any]:
    """
    Call the Gemini REST GenerateContent endpoint.
    Minimal assumptions: use x-goog-api-key header (server-to-server API key).
    """
    if not GEMINI_API_KEY:
        raise HTTPException(status_code=500, detail="Server missing GEMINI_API_KEY environment variable.")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

    payload = {
        "contents": [
            {
                # Use 'parts' containing the single prompt text piece
                "parts": [
                    {"text": prompt_text}
                ]
            }
        ],
        "generationConfig": {
            "temperature": TEMPERATURE,
            "maxOutputTokens": MAX_TOKENS,
        }
    }

    headers = {
        "x-goog-api-key": GEMINI_API_KEY,
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, json=payload, headers=headers)
        # If upstream returns HTTP error, raise with details for easier debugging
        if resp.status_code >= 400:
            logger.error("Gemini API error %s: %s", resp.status_code, resp.text)
            raise HTTPException(status_code=502, detail=f"Upstream error: {resp.status_code} — {resp.text}")
        return resp.json()


def extract_reply_from_gemini_response(j: Dict[str, Any]) -> str:
    """
    Robust extraction of text from various Gemini response shapes.
    Typical response includes 'candidates' -> first candidate -> 'content' -> 'parts' (list of dicts with 'text').
    This function checks multiple possible locations and returns the best text found.
    """
    if not isinstance(j, dict):
        return ""

    # 1) candidates -> content -> parts
    candidates = j.get("candidates") or []
    if candidates and isinstance(candidates, list):
        first = candidates[0]
        # try content.parts
        content = first.get("content") if isinstance(first, dict) else {}
        if content and isinstance(content, dict):
            parts = content.get("parts") or []
            if parts and isinstance(parts, list):
                # parts might be strings or dicts with 'text'
                out = []
                for p in parts:
                    if isinstance(p, dict):
                        text = p.get("text")
                        if text:
                            out.append(str(text))
                    elif isinstance(p, str):
                        out.append(p)
                if out:
                    return "".join(out)

            # sometimes content has a direct 'text' field
            text_field = content.get("text")
            if text_field:
                return str(text_field)

        # fallback: candidate may have 'text' at top-level
        if isinstance(first, dict):
            top_text = first.get("text")
            if top_text:
                return str(top_text)

    # 2) check top-level fields
    if "response" in j:
        return str(j.get("response") or "")

    # 3) as a last resort, try to stringify any message-like field
    for key in ("output", "generated_text", "content", "message"):
        if key in j:
            val = j.get(key)
            if isinstance(val, str):
                return val
            if isinstance(val, dict):
                # try to find text inside
                for subk in ("text", "parts"):
                    if subk in val:
                        if isinstance(val[subk], str):
                            return val[subk]
                        if isinstance(val[subk], list):
                            return "".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in val[subk]])
    # nothing found
    return ""


@app.post("/api/chat")
async def chat_endpoint(req: Request, body: ChatRequest):
    # rate limit
    client_ip = req.client.host if req.client else "unknown"
    check_rate_limit(client_ip)

    user_message = (body.message or "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Message is empty.")

    # Build single prompt text from optional history + user's message
    prompt_text = build_prompt_from_history(body.history, user_message)

    try:
        gemini_json = await call_gemini_generate(prompt_text)
        reply = extract_reply_from_gemini_response(gemini_json)
        if reply is None:
            reply = ""
        return {"reply": reply}
    except HTTPException:
        # re-raise HTTPExceptions (rate-limit / upstream errors)
        raise
    except Exception as exc:
        logger.exception("Unexpected error calling Gemini")
        raise HTTPException(status_code=500, detail="Internal server error while contacting Gemini.") from exc


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# Serve the static frontend directory (index.html served at root)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


if __name__ == "__main__":
    # convenience dev runner
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="127.0.0.1", port=8000)

