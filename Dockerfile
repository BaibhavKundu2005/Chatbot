# Dockerfile for Chatbot (FastAPI backend + bundled frontend)
FROM python:3.12-slim

# Set working dir
WORKDIR /app

# Install system deps (if you need build tools for packages)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY backend/requirements.txt ./backend/requirements.txt
RUN python -m pip install --upgrade pip
RUN pip install -r backend/requirements.txt

# Copy source
COPY backend ./backend
COPY frontend ./frontend

# Don't copy local .env into image; set secrets via host/env provider
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

EXPOSE ${PORT}

# Use gunicorn with uvicorn worker for production
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "backend.app:app", "--bind", "0.0.0.0:8000", "--workers", "1"]
