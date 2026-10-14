#!/usr/bin/env bash
# ==============================================================
# RECIPE BOOK - GOOGLE CLOUD RUN DEPLOYMENT SCRIPT
# ==============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

echo "======================================================"
echo "⚡ Recipe Book - Deploying to Google Cloud Run"
echo "======================================================"

# 1. Check if gcloud CLI is installed
if ! command -v gcloud &> /dev/null; then
  echo "❌ Error: Google Cloud SDK (gcloud) is not installed."
  echo ""
  echo "To install gcloud CLI on Linux:"
  echo "  curl https://sdk.cloud.google.com | bash"
  echo "  exec -l \$SHELL"
  echo "  gcloud init"
  echo ""
  echo "Or see: https://cloud.google.com/sdk/docs/install"
  exit 1
fi

# 2. Check GCP Project
PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
  echo "⚠️  No GCP project currently active."
  echo "Please select or set your project:"
  echo "  gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

echo "✓ Active GCP Project: ${PROJECT_ID}"

# 3. Read environment variables from .env if present
# Save any explicit caller overrides passed in the environment
CALLER_FRONTEND_URL="${FRONTEND_URL:-}"
CALLER_CUSTOM_DOMAIN="${CUSTOM_DOMAIN:-}"

if [ -f .env ]; then
  echo "✓ Loading configuration from .env..."
  # Export non-comment lines
  set -a
  source <(grep -v '^#' .env | grep -v '^$')
  set +a
fi

# Restore explicit caller overrides if provided
[ -n "$CALLER_FRONTEND_URL" ] && FRONTEND_URL="$CALLER_FRONTEND_URL"
[ -n "$CALLER_CUSTOM_DOMAIN" ] && CUSTOM_DOMAIN="$CALLER_CUSTOM_DOMAIN"

# Ensure variables exist with sensible defaults
MONGODB_URI="${MONGODB_URI:-}"
MONGODB_DB_NAME="${MONGODB_DB_NAME:-recipe_book}"
ENVIRONMENT="${ENVIRONMENT:-production}"
AUTO_SEED="${AUTO_SEED:-true}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
LOG_FORMAT="${LOG_FORMAT:-json}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-recipe-book}"

# Production Custom Domain and FRONTEND_URL resolution
CUSTOM_DOMAIN="${CUSTOM_DOMAIN:-}"

# If CUSTOM_DOMAIN is set, use it for FRONTEND_URL
if [ -n "$CUSTOM_DOMAIN" ]; then
  FRONTEND_URL="https://${CUSTOM_DOMAIN}"
fi

# Ensure protocol is present if FRONTEND_URL is provided without scheme
if [ -n "$FRONTEND_URL" ] && [[ "$FRONTEND_URL" != http* ]]; then
  FRONTEND_URL="https://${FRONTEND_URL}"
fi

# Strip trailing slash
FRONTEND_URL="${FRONTEND_URL%/}"

# If FRONTEND_URL is not set or points to localhost/127.0.0.1, check if Cloud Run service has an existing URL
if [ -z "$FRONTEND_URL" ] || [[ "$FRONTEND_URL" == *"localhost"* ]] || [[ "$FRONTEND_URL" == *"127.0.0.1"* ]]; then
  EXISTING_URL=$(gcloud run services describe "${SERVICE_NAME}" --platform managed --region "${REGION}" --format 'value(status.url)' --project "${PROJECT_ID}" 2>/dev/null || true)
  if [ -n "$EXISTING_URL" ]; then
    echo "ℹ️  No custom FRONTEND_URL or CUSTOM_DOMAIN set; using Cloud Run service URL: ${EXISTING_URL}"
    FRONTEND_URL="${EXISTING_URL}"
  else
    FRONTEND_URL=""
  fi
fi

if [ -z "$MONGODB_URI" ]; then
  echo "❌ Error: MONGODB_URI is not set in .env."
  echo "Please set your MongoDB Atlas connection string in .env before deploying."
  echo "Example: MONGODB_URI=\"mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority\""
  exit 1
fi

echo "✓ Target Region:  ${REGION}"
echo "✓ Service Name:   ${SERVICE_NAME}"
if [ -n "$FRONTEND_URL" ]; then
  echo "✓ Frontend URL:   ${FRONTEND_URL}"
fi

# 4. Enable Google Cloud APIs
echo ""
echo "🚀 Step 1/3: Enabling required Google Cloud APIs (Cloud Run, Cloud Build, Artifact Registry)..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project "${PROJECT_ID}"

# Ensure auth variables exist
JWT_SECRET="${JWT_SECRET:-super-secret-recipes-jwt-token-key-2026}"
GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}"
GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-}"
ALLOWED_EDITOR_EMAILS="${ALLOWED_EDITOR_EMAILS:-chef@gourmetvault.com}"

# 5. Build and deploy container directly using Google Cloud Build & Cloud Run
echo ""
echo "🚀 Step 2/3: Building and deploying container to Cloud Run..."
ENV_VARS="MONGODB_URI=${MONGODB_URI},MONGODB_DB_NAME=${MONGODB_DB_NAME},ENVIRONMENT=${ENVIRONMENT},AUTO_SEED=${AUTO_SEED},LOG_LEVEL=${LOG_LEVEL},LOG_FORMAT=${LOG_FORMAT},JWT_SECRET=${JWT_SECRET},ALLOWED_EDITOR_EMAILS=${ALLOWED_EDITOR_EMAILS}"
if [ -n "$GOOGLE_CLIENT_ID" ]; then
  ENV_VARS="${ENV_VARS},GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}"
fi
if [ -n "$GOOGLE_CLIENT_SECRET" ]; then
  ENV_VARS="${ENV_VARS},GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}"
fi
if [ -n "$FRONTEND_URL" ]; then
  ENV_VARS="${ENV_VARS},FRONTEND_URL=${FRONTEND_URL}"
fi

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "${ENV_VARS}" \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 10 \
  --project "${PROJECT_ID}"

# 6. Retrieve Service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --platform managed --region "${REGION}" --format 'value(status.url)' --project "${PROJECT_ID}")

# If FRONTEND_URL was not known prior to first deploy, set it to the provisioned SERVICE_URL
if [ -z "$FRONTEND_URL" ]; then
  FRONTEND_URL="${SERVICE_URL}"
  echo "Updating Cloud Run FRONTEND_URL to ${SERVICE_URL}..."
  gcloud run services update "${SERVICE_NAME}" \
    --region "${REGION}" \
    --platform managed \
    --update-env-vars "FRONTEND_URL=${SERVICE_URL}" \
    --project "${PROJECT_ID}"
fi

# 7. Auto-cleanup old builds & enforce free-tier storage limits
if [ -f "${SCRIPT_DIR}/cleanup-gcp-artifacts.sh" ]; then
  bash "${SCRIPT_DIR}/cleanup-gcp-artifacts.sh" --prune-now || true
fi

echo ""
echo "======================================================"
echo "🎉 DEPLOYMENT SUCCESSFUL!"
echo "======================================================"
echo "App URL:               ${FRONTEND_URL}"
echo "Cloud Run Service URL: ${SERVICE_URL}"
echo ""
echo "🚀 Production Google OAuth Settings"
echo "1. In Google Cloud Console (https://console.cloud.google.com/apis/credentials):"
echo "   Ensure your OAuth 2.0 Web Client includes:"
echo "   - Authorized JavaScript Origins:"
echo "       ${FRONTEND_URL}"
echo "       ${SERVICE_URL}"
echo "   - Authorized Redirect URIs:"
echo "       ${FRONTEND_URL}/api/v1/auth/google/callback"
echo "       ${SERVICE_URL}/api/v1/auth/google/callback"
echo ""
echo "2. In MongoDB Atlas (https://cloud.mongodb.com/):"
echo "   Under 'Network Access' -> 'IP Access List', ensure '0.0.0.0/0' is whitelisted"
echo "   so Cloud Run instances can reach your database."
echo ""
echo "3. Custom Domain Mapping:"
if [ -n "$CUSTOM_DOMAIN" ]; then
  echo "   If not mapped yet, map ${CUSTOM_DOMAIN} to this Cloud Run service via Cloud Console:"
  echo "   https://console.cloud.google.com/run/domains"
else
  echo "   To map a custom domain, visit Google Cloud Console:"
  echo "   https://console.cloud.google.com/run/domains"
fi
echo "======================================================"
