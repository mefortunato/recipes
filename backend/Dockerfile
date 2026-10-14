# Multi-stage cloud-native Dockerfile using Astral uv for ultra-fast, reproducible builds
FROM ghcr.io/astral-sh/uv:0.6.5 AS uv_bin

FROM python:3.11-slim AS builder

WORKDIR /app

# Install uv from official image
COPY --from=uv_bin /uv /uvx /bin/

# Environment settings for uv and python
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Install dependencies first for optimal Docker layer caching
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

# Copy application source code
COPY app/ ./app/

# Build and install the application wheel
RUN uv sync --frozen --no-dev

# -------------------------------------------------------------
# Final minimal production image
# -------------------------------------------------------------
FROM python:3.11-slim AS runner

WORKDIR /app

# Create a non-privileged user for security compliance (Cloud Run)
RUN addgroup --system --gid 1001 appgroup && \
    adduser --system --uid 1001 --ingroup appgroup --no-create-home appuser

# Copy virtual environment from builder stage
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app

# Set PATH so executables in .venv are directly accessible
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Switch to non-root user
USER appuser

EXPOSE 8000

# Container healthcheck for orchestrators
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/live', timeout=2).read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
