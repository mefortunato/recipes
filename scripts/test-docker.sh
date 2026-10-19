#!/usr/bin/env bash
# ==============================================================
# RECIPE BOOK - LOCAL DOCKER PRODUCTION TEST HARNESS
# ==============================================================
# Builds the production Cloud Run multi-stage Docker image and runs
# automated health & SPA routing checks against it locally.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

PORT="${TEST_PORT:-8085}"
IMAGE_TAG="recipe-book:local-test"
CONTAINER_NAME="recipe-book-docker-test"
NO_BUILD=false
KEEP_RUNNING=false

# Parse flags
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      PORT="$2"
      shift 2
      ;;
    --no-build)
      NO_BUILD=true
      shift
      ;;
    --keep)
      KEEP_RUNNING=true
      shift
      ;;
    -h|--help)
      echo "Usage: ./scripts/test-docker.sh [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --port <PORT>   Port to bind test container to (default: 8085)"
      echo "  --no-build      Skip Docker build and test existing image"
      echo "  --keep          Keep container running after test completes"
      echo "  -h, --help      Show this help message"
      exit 0
      ;;
    *)
      echo "Unknown flag: $1"
      exit 1
      ;;
  esac
done

cd "${ROOT_DIR}"

cleanup() {
  if [ "${KEEP_RUNNING}" = false ]; then
    echo "🧹 Cleaning up test container '${CONTAINER_NAME}'..."
    docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
  else
    echo "ℹ️ Container '${CONTAINER_NAME}' is still running on http://localhost:${PORT}"
  fi
}
trap cleanup EXIT INT TERM

# 1. Build image if requested
if [ "${NO_BUILD}" = false ]; then
  echo "🔨 Building multi-stage production Docker image '${IMAGE_TAG}'..."
  docker build -t "${IMAGE_TAG}" .
  echo "✓ Docker image built successfully."
fi

# 2. Stop any existing test container
docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true

# 3. Start container
echo "🚀 Starting test container on http://127.0.0.1:${PORT}..."
docker run -d \
  --name "${CONTAINER_NAME}" \
  -p "${PORT}:8080" \
  -e PORT=8080 \
  -e ENVIRONMENT=development \
  "${IMAGE_TAG}" >/dev/null

# 4. Wait for container to be ready
echo "⏳ Waiting for container to become healthy..."
READY=false
for i in {1..20}; do
  if curl -s -f "http://127.0.0.1:${PORT}/health" >/dev/null 2>&1; then
    READY=true
    break
  fi
  sleep 0.5
done

if [ "${READY}" = false ]; then
  echo "❌ Container failed to respond on /health within 10 seconds. Logs:"
  docker logs "${CONTAINER_NAME}"
  exit 1
fi

echo "✓ Health check passed!"

# 5. Run automated validation checks
echo "🧪 Running endpoint checks..."

# Check 1: Healthcheck endpoint returns valid JSON with healthy status
HEALTH_RESP=$(curl -s "http://127.0.0.1:${PORT}/health")
if [[ "${HEALTH_RESP}" != *"healthy"* ]]; then
  echo "❌ /health check failed: ${HEALTH_RESP}"
  exit 1
fi
echo "  [PASS] GET /health -> ${HEALTH_RESP}"

# Check 2: Root endpoint serves Svelte SPA HTML
ROOT_RESP=$(curl -s -H "Accept: text/html" "http://127.0.0.1:${PORT}/")
if [[ "${ROOT_RESP}" != *"<!doctype html>"* ]]; then
  echo "❌ Root endpoint failed to serve frontend HTML"
  exit 1
fi
echo "  [PASS] GET / -> Successfully served SPA HTML index"

# Check 3: Auth config endpoint works
AUTH_CFG=$(curl -s "http://127.0.0.1:${PORT}/api/v1/auth/config")
if [[ "${AUTH_CFG}" != *"google_client_id"* ]]; then
  echo "❌ /api/v1/auth/config failed: ${AUTH_CFG}"
  exit 1
fi
echo "  [PASS] GET /api/v1/auth/config -> Returned authentication configuration"

# Check 4: Unknown API route returns 404 JSON, not HTML
API_404_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${PORT}/api/nonexistent-route")
if [ "${API_404_STATUS}" != "404" ]; then
  echo "❌ Unknown API route should return 404, got ${API_404_STATUS}"
  exit 1
fi
echo "  [PASS] GET /api/nonexistent-route -> HTTP 404 JSON"

echo ""
echo "=========================================================="
echo "🎉 ALL LOCAL DOCKER PRODUCTION CHECKS PASSED!"
echo "The multi-stage container is 100% ready for Google Cloud Run."
echo "=========================================================="
