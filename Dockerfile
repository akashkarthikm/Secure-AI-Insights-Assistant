# syntax=docker/dockerfile:1.7
#
# Multi-stage build:
#   1. node-build  — compiles the React frontend into static files
#   2. py-build    — installs Python deps and pre-downloads the embedding model
#   3. runtime     — minimal runtime image with the API + baked-in static frontend

# -------- 1. Frontend build --------

FROM node:22-alpine AS node-build
WORKDIR /frontend

# Cache npm install across rebuilds: only re-runs when package files change.
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci

# Now copy the rest and build the static bundle.
COPY frontend/ .
RUN npm run build
# Output ends up in /frontend/dist


# -------- 2. Python build --------

FROM python:3.12-slim AS py-build

# System deps: build essentials for any wheels that need compiling, plus
# libpq for psycopg. Cleaned up in the same RUN to keep the layer slim.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install into a dedicated prefix so we can copy it cleanly into the runtime stage.
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Pre-download the embedding model into a known cache so the runtime image
# doesn't need internet on first start. ~80 MB; happens once at build time.
ENV HF_HOME=/install/hf-cache
RUN PYTHONPATH=/install/lib/python3.12/site-packages \
    python -c "from sentence_transformers import SentenceTransformer; \
SentenceTransformer('all-MiniLM-L6-v2')"


# -------- 3. Runtime --------

FROM python:3.12-slim AS runtime

# Runtime libpq for psycopg, then clean up.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for safety.
RUN useradd --system --create-home --uid 1001 app
WORKDIR /app

# Bring in installed Python packages and the cached HF model.
COPY --from=py-build /install /usr/local
ENV HF_HOME=/usr/local/hf-cache
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Application code.
COPY --chown=app:app backend/ ./backend/
COPY --chown=app:app data/ ./data/

# Static frontend bundle from the node stage.
COPY --from=node-build --chown=app:app /frontend/dist ./frontend/dist

USER app

EXPOSE 8000

# Default command. compose can override (e.g., for the one-shot ingest container).
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]