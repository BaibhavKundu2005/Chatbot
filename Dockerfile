# Dockerfile for Chatbot (FastAPI backend + bundled frontend)
FROM python:3.12-slim

# Set working dir
WORKDIR /app

# Install system deps (if you need build tools for packages)
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY api/requirements.txt ./api/requirements.txt
RUN python -m pip install --upgrade pip
RUN pip install -r api/requirements.txt

# Copy source
COPY api ./api
COPY frontend ./frontend

# Don't copy local .env into image; set secrets via host/env provider
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Expose the port (can be overridden by Render with $PORT at runtime)
EXPOSE ${PORT}

# Run with Uvicorn directly and expand $PORT at container start.
# Use a shell form so environment variables are substituted.
CMD ["sh", "-c", "python -m uvicorn api.chat:app --host 0.0.0.0 --port ${PORT:-8000}"]
