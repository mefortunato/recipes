#!/usr/bin/env bash
# ==============================================================
# RECIPE BOOK - GOOGLE CLOUD RUN DEPLOYMENT SCRIPT
# ==============================================================
# Builds and deploys the unified Recipe Book container to Google Cloud Run.
#
# Usage:
#   ./scripts/deploy-gcp.sh [OPTIONS]
#
# Examples:
#   ./scripts/deploy-gcp.sh
#   ./scripts/deploy-gcp.sh --project my-recipes-app --region us-central1
# ==============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

# --- 1. Load configuration from .env if present ---
CALLER_PROJECT_ID="${GCP_PROJECT_ID:-}"
CALLER_FRONTEND_URL="${FRONTEND_URL:-}"
CALLER_CUSTOM_DOMAIN="${CUSTOM_DOMAIN:-}"

if [ -f "${ROOT_DIR}/.env" ]; then
  echo "✓ Loading configuration from .env..."
  set -a
  source <(grep -v '^#' "${ROOT_DIR}/.env" | grep -v '^$')
  set +a
fi

# Restore explicit caller overrides if provided
[ -n "$CALLER_PROJECT_ID" ] && GCP_PROJECT_ID="$CALLER_PROJECT_ID"
[ -n "$CALLER_FRONTEND_URL" ] && FRONTEND_URL="$CALLER_FRONTEND_URL"
[ -n "$CALLER_CUSTOM_DOMAIN" ] && CUSTOM_DOMAIN="$CALLER_CUSTOM_DOMAIN"

# --- 2. Default Parameters ---
PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo "")}"
REGION="${GCP_REGION:-${REGION:-us-central1}}"
SERVICE_NAME="${GCP_SERVICE_NAME:-${SERVICE_NAME:-recipe-book}}"
DRY_RUN=false

print_help() {
  echo "Recipe Book - Google Cloud Run Deployment Tool"
  echo ""
  echo "Usage: ./scripts/deploy-gcp.sh [OPTIONS]"
  echo ""
  echo "Options:"
  echo "  -p, --project <ID>       GCP Project ID (default: GCP_PROJECT_ID from .env or active gcloud project)"
  echo "  -r, --region <REGION>    GCP Region (default: us-central1)"
  echo "  -s, --service <NAME>     Cloud Run service name (default: recipe-book)"
  echo "      --dry-run            Display commands without executing them"
  echo "  -h, --help               Show this help message"
  echo ""
}

# --- 3. Parse CLI Arguments ---
while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project)
      PROJECT_ID="$2"
      shift 2
      ;;
    -r|--region)
      REGION="$2"
      shift 2
      ;;
    -s|--service)
      SERVICE_NAME="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    -h|--help)
      print_help
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      print_help
      exit 1
      ;;
  esac
done

echo "======================================================"
echo "⚡ Recipe Book - Deploying to Google Cloud Run"
echo "======================================================"

# --- 4. Verify Prerequisites ---
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

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
  echo "❌ Error: No GCP Project ID specified."
  echo "Please set GCP_PROJECT_ID in .env or provide --project <PROJECT_ID>."
  echo "Example: GCP_PROJECT_ID=my-recipes-app"
  exit 1
fi

echo "✓ Target GCP Project: ${PROJECT_ID}"

# --- 5. Resolve URLs and Environment Defaults ---
MONGODB_URI="${MONGODB_URI:-}"
MONGODB_DB_NAME="${MONGODB_DB_NAME:-recipe_book}"
ENVIRONMENT="${ENVIRONMENT:-production}"
AUTO_SEED="${AUTO_SEED:-true}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"
LOG_FORMAT="${LOG_FORMAT:-json}"
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

echo "✓ Target Region:     ${REGION}"
echo "✓ Service Name:      ${SERVICE_NAME}"
if [ -n "$FRONTEND_URL" ]; then
  echo "✓ Frontend URL:      ${FRONTEND_URL}"
fi

# --- 6. Enable Google Cloud APIs ---
echo ""
echo "🚀 Step 1/3: Enabling required Google Cloud APIs (Cloud Run, Cloud Build, Artifact Registry)..."
if [ "${DRY_RUN}" = false ]; then
  gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project "${PROJECT_ID}"
else
  echo "[DRY-RUN] gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com --project ${PROJECT_ID}"
fi

# Auth variables
JWT_SECRET="${JWT_SECRET:-super-secret-recipes-jwt-token-key-2026}"
GOOGLE_CLIENT_ID="${GOOGLE_CLIENT_ID:-}"
GOOGLE_CLIENT_SECRET="${GOOGLE_CLIENT_SECRET:-}"
ALLOWED_EDITOR_EMAILS="${ALLOWED_EDITOR_EMAILS:-}"

# --- 7. Build and deploy container directly using Google Cloud Build & Cloud Run ---
echo ""
echo "🚀 Step 2/3: Building and deploying container to Cloud Run..."
ENV_VARS="GCP_PROJECT_ID=${PROJECT_ID},MONGODB_URI=${MONGODB_URI},MONGODB_DB_NAME=${MONGODB_DB_NAME},ENVIRONMENT=${ENVIRONMENT},AUTO_SEED=${AUTO_SEED},LOG_LEVEL=${LOG_LEVEL},LOG_FORMAT=${LOG_FORMAT},JWT_SECRET=${JWT_SECRET},ALLOWED_EDITOR_EMAILS=${ALLOWED_EDITOR_EMAILS}"
if [ -n "$GOOGLE_CLIENT_ID" ]; then
  ENV_VARS="${ENV_VARS},GOOGLE_CLIENT_ID=${GOOGLE_CLIENT_ID}"
fi
if [ -n "$GOOGLE_CLIENT_SECRET" ]; then
  ENV_VARS="${ENV_VARS},GOOGLE_CLIENT_SECRET=${GOOGLE_CLIENT_SECRET}"
fi
if [ -n "$FRONTEND_URL" ]; then
  ENV_VARS="${ENV_VARS},FRONTEND_URL=${FRONTEND_URL}"
fi

DEPLOY_CMD=(
  gcloud run deploy "${SERVICE_NAME}"
  --source .
  --region "${REGION}"
  --platform managed
  --allow-unauthenticated
  --set-env-vars "${ENV_VARS}"
  --memory 512Mi
  --cpu 1
  --min-instances 0
  --max-instances 10
  --project "${PROJECT_ID}"
)

if [ "${DRY_RUN}" = true ]; then
  echo "[DRY-RUN] ${DEPLOY_CMD[*]}"
  SERVICE_URL="https://${SERVICE_NAME}-${PROJECT_ID}.${REGION}.run.app"
else
  "${DEPLOY_CMD[@]}"
  SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" --platform managed --region "${REGION}" --format 'value(status.url)' --project "${PROJECT_ID}")
fi

# If FRONTEND_URL was not known prior to first deploy, set it to the provisioned SERVICE_URL
if [ -z "$FRONTEND_URL" ]; then
  FRONTEND_URL="${SERVICE_URL}"
  echo "Updating Cloud Run FRONTEND_URL to ${SERVICE_URL}..."
  if [ "${DRY_RUN}" = false ]; then
    gcloud run services update "${SERVICE_NAME}" \
      --region "${REGION}" \
      --platform managed \
      --update-env-vars "FRONTEND_URL=${SERVICE_URL}" \
      --project "${PROJECT_ID}"
  else
    echo "[DRY-RUN] gcloud run services update ${SERVICE_NAME} --project ${PROJECT_ID} --update-env-vars FRONTEND_URL=${SERVICE_URL}"
  fi
fi

# --- 8. Auto-cleanup old builds & enforce free-tier storage limits ---
if [ -f "${SCRIPT_DIR}/cleanup-gcp-artifacts.sh" ]; then
  echo ""
  echo "🚀 Step 3/3: Cleaning up old build storage artifacts..."
  if [ "${DRY_RUN}" = false ]; then
    bash "${SCRIPT_DIR}/cleanup-gcp-artifacts.sh" --project "${PROJECT_ID}" --region "${REGION}" --prune-now || true
  else
    echo "[DRY-RUN] bash ${SCRIPT_DIR}/cleanup-gcp-artifacts.sh --project ${PROJECT_ID} --region ${REGION} --prune-now"
  fi
fi

echo ""
echo "======================================================"
echo "🎉 DEPLOYMENT SUCCESSFUL!"
echo "======================================================"
echo "App URL:               ${FRONTEND_URL}"
echo "Cloud Run Service URL: ${SERVICE_URL}"
echo "Target GCP Project:    ${PROJECT_ID}"
echo ""
echo "🚀 Production Google OAuth Settings"
echo "1. In Google Cloud Console (https://console.cloud.google.com/apis/credentials?project=${PROJECT_ID}):"
echo "   Ensure your OAuth 2.0 Web Client includes:"
echo "   - Authorized JavaScript Origins:"
echo "       ${FRONTEND_URL}"
echo "       ${SERVICE_URL}"
echo "   - Authorized Redirect URIs:"
echo "       ${FRONTEND_URL}/api/v1/auth/google/callback"
echo "       ${SERVICE_URL}/api/v1/auth/google/callback"
echo "   (Note: With Google Identity Services 1-click button, only Authorized Origins are required!)"
echo ""
echo "2. In MongoDB Atlas (https://cloud.mongodb.com/):"
echo "   Under 'Network Access' -> 'IP Access List', ensure '0.0.0.0/0' is whitelisted"
echo "   so Cloud Run instances can reach your database."
echo ""
echo "3. Custom Domain Mapping:"
if [ -n "$CUSTOM_DOMAIN" ]; then
  echo "   If not mapped yet, map ${CUSTOM_DOMAIN} to this Cloud Run service via Cloud Console:"
  echo "   https://console.cloud.google.com/run/domains?project=${PROJECT_ID}"
else
  echo "   To map a custom domain, visit Google Cloud Console:"
  echo "   https://console.cloud.google.com/run/domains?project=${PROJECT_ID}"
fi
echo "======================================================"
