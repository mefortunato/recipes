#!/usr/bin/env bash
# ==============================================================
# RECIPE BOOK - LOCAL DEVELOPMENT ENVIRONMENT SCRIPT
# ==============================================================
# Runs local MongoDB container, FastAPI backend, and Vite frontend.
# Forces local MongoDB connection regardless of production MONGODB_URI in .env.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

# 1. Load variables from root .env if present
if [ -f "${ROOT_DIR}/.env" ]; then
  echo "✓ Loading configuration from .env..."
  set -a
  source <(grep -v '^#' "${ROOT_DIR}/.env" | grep -v '^$')
  set +a
fi

# 2. Local overrides for development
LOCAL_MONGO_PORT="${MONGO_PORT:-27017}"
export MONGODB_URI="mongodb://127.0.0.1:${LOCAL_MONGO_PORT}"
export MONGODB_DB_NAME="${MONGODB_DB_NAME:-recipe_book}"
export FRONTEND_URL="http://localhost:5173"

# 3. Ensure local MongoDB Docker container is running
echo "📦 Ensuring local MongoDB container is running on port ${LOCAL_MONGO_PORT}..."
docker compose up -d mongodb

echo "⚡ Dev Database: ${MONGODB_URI} (${MONGODB_DB_NAME})"

# Track child process IDs for graceful shutdown
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  set +e
  # Remove traps to prevent recursive trap execution and segfaults
  trap - EXIT INT TERM

  echo ""
  echo "🛑 Stopping dev servers..."

  # Terminate frontend process & its child tree
  if [ -n "${FRONTEND_PID}" ] && kill -0 "${FRONTEND_PID}" 2>/dev/null; then
    pkill -TERM -P "${FRONTEND_PID}" 2>/dev/null || true
    kill -TERM "${FRONTEND_PID}" 2>/dev/null || true
  fi

  # Terminate backend process & uvicorn worker tree
  if [ -n "${BACKEND_PID}" ] && kill -0 "${BACKEND_PID}" 2>/dev/null; then
    pkill -TERM -P "${BACKEND_PID}" 2>/dev/null || true
    kill -TERM "${BACKEND_PID}" 2>/dev/null || true
  fi

  # Give processes a moment to terminate gracefully
  sleep 0.5

  # Ensure ports 8000 and 5173 are freed
  fuser -k -TERM 8000/tcp 2>/dev/null || true
  fuser -k -TERM 5173/tcp 2>/dev/null || true
  sleep 0.5
  fuser -k -KILL 8000/tcp 2>/dev/null || true
  fuser -k -KILL 5173/tcp 2>/dev/null || true

  wait "${BACKEND_PID}" 2>/dev/null || true
  wait "${FRONTEND_PID}" 2>/dev/null || true

  echo "✓ Dev servers stopped."
  exit 0
}

trap cleanup EXIT INT TERM

# 4. Clean up any stale processes before starting
fuser -k 8000/tcp 2>/dev/null || true
fuser -k 5173/tcp 2>/dev/null || true

# 5. Start FastAPI backend with hot reloading
echo "🚀 Starting FastAPI backend on http://127.0.0.1:8000..."
(cd "${ROOT_DIR}/backend" && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!

# 6. Start Vite frontend
echo "✨ Starting Vite frontend on http://localhost:5173..."
(cd "${ROOT_DIR}/frontend" && npm run dev) &
FRONTEND_PID=$!

# 7. Wait for background jobs
wait
