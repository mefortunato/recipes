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
export PATH="${HOME}/.local/bin:${PATH}"

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

# 3. Ensure local MongoDB Docker container is running (if Docker is available)
is_mongodb_running() {
  # 1. Check if local port is already open and accepting connections
  if (exec 3<>/dev/tcp/127.0.0.1/"${LOCAL_MONGO_PORT}") 2>/dev/null; then
    exec 3<&- 2>/dev/null || true
    exec 3>&- 2>/dev/null || true
    return 0
  fi

  # Fallback to nc if available
  if command -v nc >/dev/null 2>&1 && nc -z -w 1 127.0.0.1 "${LOCAL_MONGO_PORT}" >/dev/null 2>&1; then
    return 0
  fi

  # Fallback to ss socket inspection if available
  if command -v ss >/dev/null 2>&1 && ss -tln "( sport = :${LOCAL_MONGO_PORT} )" 2>/dev/null | grep -q LISTEN; then
    return 0
  fi

  # 2. Check if MongoDB container is already running in Docker
  if command -v docker >/dev/null 2>&1; then
    if [ "$(docker inspect -f '{{.State.Running}}' recipe-book-mongodb 2>/dev/null)" = "true" ]; then
      return 0
    fi
  fi

  return 1
}

if is_mongodb_running; then
  echo "✓ MongoDB is already running on port ${LOCAL_MONGO_PORT}."
  echo "⚡ Dev Database: ${MONGODB_URI} (${MONGODB_DB_NAME})"
elif command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "📦 Ensuring local MongoDB container is running on port ${LOCAL_MONGO_PORT}..."
  if ! docker compose up -d mongodb; then
    echo "⚠️ Failed to start MongoDB container."
  fi
  echo "⚡ Dev Database: ${MONGODB_URI} (${MONGODB_DB_NAME})"
else
  echo "⚠️ Docker is not running or unavailable. Ensure MongoDB is running locally on port ${LOCAL_MONGO_PORT}."
fi

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

  # Ensure ports 8000 and 5173 are freed if fuser is installed
  if command -v fuser >/dev/null 2>&1; then
    fuser -k -TERM 8000/tcp 2>/dev/null || true
    fuser -k -TERM 5173/tcp 2>/dev/null || true
    sleep 0.5
    fuser -k -KILL 8000/tcp 2>/dev/null || true
    fuser -k -KILL 5173/tcp 2>/dev/null || true
  fi

  wait "${BACKEND_PID}" 2>/dev/null || true
  wait "${FRONTEND_PID}" 2>/dev/null || true

  echo "✓ Dev servers stopped."
  exit 0
}

trap cleanup EXIT INT TERM

# 4. Clean up any stale processes before starting
if command -v fuser >/dev/null 2>&1; then
  fuser -k 8000/tcp 2>/dev/null || true
  fuser -k 5173/tcp 2>/dev/null || true
fi

# 5. Ensure dependencies are installed
if [ ! -d "${ROOT_DIR}/backend/.venv" ]; then
  echo "📦 Initializing backend Python environment with uv..."
  (cd "${ROOT_DIR}/backend" && uv sync)
fi

if [ ! -d "${ROOT_DIR}/frontend/node_modules" ]; then
  echo "📦 Installing frontend npm dependencies..."
  (cd "${ROOT_DIR}/frontend" && npm install)
fi

# 6. Start FastAPI backend with hot reloading
echo "🚀 Starting FastAPI backend on http://127.0.0.1:8000..."
(cd "${ROOT_DIR}/backend" && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!

# 7. Start Vite frontend
echo "✨ Starting Vite frontend on http://localhost:5173..."
(cd "${ROOT_DIR}/frontend" && npm run dev) &
FRONTEND_PID=$!

# 8. Wait for background jobs
wait
