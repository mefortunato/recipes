# ==============================================================
# Stage 1: Build Svelte static frontend
# ==============================================================
FROM node:20-alpine AS frontend-builder
WORKDIR /build

# Copy frontend package manifests
COPY frontend/package*.json ./frontend/
WORKDIR /build/frontend
RUN npm ci || npm install

# Copy frontend source code
COPY frontend/ ./
RUN mkdir -p /build/backend/app/static
RUN npm run build

# ==============================================================
# Stage 2: Python environment with uv & FastAPI
# ==============================================================
FROM python:3.11-slim AS runner

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:0.6.5 /uv /uvx /bin/

# Working directory
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV PYTHONUNBUFFERED=1

# Install backend dependencies first for layer caching
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy backend application code
COPY backend/app ./app

# Copy built static HTML & assets from Stage 1 into backend/app/static
COPY --from=frontend-builder /build/backend/app/static ./app/static

# Install project into virtualenv
RUN uv sync --frozen --no-dev

# Run as an unprivileged user
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup --no-create-home appuser
USER appuser

# Activate virtualenv
ENV PATH="/app/.venv/bin:$PATH"
ENV PORT=8000

EXPOSE 8000 8080

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD python -c "import os, urllib.request; port = os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/health/live')" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
