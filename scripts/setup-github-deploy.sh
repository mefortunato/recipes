#!/usr/bin/env bash
# ==============================================================
# RECIPE BOOK - ONE-TIME SETUP FOR GITHUB ACTIONS DEPLOYS
# ==============================================================
# Prepares a GCP project so .github/workflows/deploy.yml can deploy to
# Cloud Run on every push to main, using Workload Identity Federation
# (short-lived OIDC tokens, no service account JSON keys).
#
# Creates (idempotently):
#   - Required APIs (Cloud Run, Artifact Registry, IAM, STS, IAM Credentials)
#   - Artifact Registry Docker repository for the images
#   - A "github-deployer" service account with only the roles it needs
#   - A Workload Identity pool + GitHub OIDC provider that only accepts
#     tokens from <owner>/<repo> on refs/heads/main
#
# Then prints the GitHub variables and secrets to configure.
#
# Usage:
#   ./scripts/setup-github-deploy.sh --project my-recipes-app [--repo owner/name]
# ==============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${ROOT_DIR}"

CALLER_PROJECT_ID="${GCP_PROJECT_ID:-}"
if [ -f "${ROOT_DIR}/.env" ]; then
  set -a
  # shellcheck disable=SC1090
  source <(grep -v '^#' "${ROOT_DIR}/.env" | grep -v '^$')
  set +a
fi
[ -n "$CALLER_PROJECT_ID" ] && GCP_PROJECT_ID="$CALLER_PROJECT_ID"

PROJECT_ID="${GCP_PROJECT_ID:-$(gcloud config get-value project 2>/dev/null || echo "")}"
REGION="${GCP_REGION:-${REGION:-us-central1}}"
SERVICE_NAME="${GCP_SERVICE_NAME:-${SERVICE_NAME:-recipe-book}}"
AR_REPO="${GCP_ARTIFACT_REPO:-cloud-run-source-deploy}"
POOL_ID="github"
PROVIDER_ID="github-oidc"
DEPLOYER_NAME="github-deployer"
RUNTIME_SA=""
GITHUB_REPO=""
BRANCH="main"

print_help() {
  cat <<EOF
Usage: ./scripts/setup-github-deploy.sh [OPTIONS]

Options:
  -p, --project <ID>        GCP project ID (default: GCP_PROJECT_ID from .env or active gcloud project)
  -r, --region <REGION>     Region (default: ${REGION})
  -s, --service <NAME>      Cloud Run service name (default: ${SERVICE_NAME})
      --repo <OWNER/NAME>   GitHub repository allowed to deploy (default: from git remote 'origin')
      --branch <NAME>       Branch allowed to deploy (default: main)
      --runtime-sa <EMAIL>  Service account Cloud Run runs as (default: Compute Engine default SA)
  -h, --help                Show this help message
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project) PROJECT_ID="$2"; shift 2 ;;
    -r|--region) REGION="$2"; shift 2 ;;
    -s|--service) SERVICE_NAME="$2"; shift 2 ;;
    --repo) GITHUB_REPO="$2"; shift 2 ;;
    --branch) BRANCH="$2"; shift 2 ;;
    --runtime-sa) RUNTIME_SA="$2"; shift 2 ;;
    -h|--help) print_help; exit 0 ;;
    *) echo "Unknown option: $1"; print_help; exit 1 ;;
  esac
done

if ! command -v gcloud &> /dev/null; then
  echo "❌ Error: Google Cloud SDK (gcloud) is not installed. See https://cloud.google.com/sdk/docs/install"
  exit 1
fi
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
  echo "❌ Error: No GCP project ID. Set GCP_PROJECT_ID in .env or pass --project <ID>."
  exit 1
fi
if [ -z "$GITHUB_REPO" ]; then
  REMOTE_URL=$(git remote get-url origin 2>/dev/null || true)
  GITHUB_REPO=$(echo "$REMOTE_URL" | sed -E 's#^(https://|git@)github\.com[:/]##; s#\.git$##')
fi
if [[ ! "$GITHUB_REPO" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "❌ Error: Could not determine the GitHub repository. Pass --repo <owner>/<name>."
  exit 1
fi

PROJECT_NUMBER=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')
DEPLOYER_SA="${DEPLOYER_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
RUNTIME_SA="${RUNTIME_SA:-${PROJECT_NUMBER}-compute@developer.gserviceaccount.com}"
POOL_NAME="projects/${PROJECT_NUMBER}/locations/global/workloadIdentityPools/${POOL_ID}"
PROVIDER_NAME="${POOL_NAME}/providers/${PROVIDER_ID}"

echo "======================================================"
echo "🔐 Setting up GitHub Actions → Cloud Run deploys"
echo "Project:     ${PROJECT_ID} (${PROJECT_NUMBER})"
echo "Region:      ${REGION}"
echo "Service:     ${SERVICE_NAME}"
echo "GitHub repo: ${GITHUB_REPO} (branch: ${BRANCH})"
echo "======================================================"

echo ""
echo "1/5 Enabling APIs..."
gcloud services enable \
  run.googleapis.com artifactregistry.googleapis.com compute.googleapis.com \
  iam.googleapis.com iamcredentials.googleapis.com sts.googleapis.com \
  --project "$PROJECT_ID"

echo ""
echo "2/5 Artifact Registry repository '${AR_REPO}'..."
if ! gcloud artifacts repositories describe "$AR_REPO" --location "$REGION" --project "$PROJECT_ID" &>/dev/null; then
  gcloud artifacts repositories create "$AR_REPO" --repository-format=docker \
    --location "$REGION" --project "$PROJECT_ID" --description "Recipe Book images"
fi
# Keep image storage inside the free tier (cleanup policies run automatically from now on)
bash "${SCRIPT_DIR}/cleanup-gcp-artifacts.sh" --project "$PROJECT_ID" --region "$REGION" \
  --service "$SERVICE_NAME" --repo "$AR_REPO" >/dev/null || \
  echo "⚠️  Could not apply Artifact Registry cleanup policies; run ./scripts/cleanup-gcp-artifacts.sh manually."

echo ""
echo "3/5 Deployer service account ${DEPLOYER_SA}..."
if ! gcloud iam service-accounts describe "$DEPLOYER_SA" --project "$PROJECT_ID" &>/dev/null; then
  gcloud iam service-accounts create "$DEPLOYER_NAME" --project "$PROJECT_ID" \
    --display-name "GitHub Actions deployer (${GITHUB_REPO})"
fi
# Deploy revisions and keep the service public (--allow-unauthenticated needs run.admin)
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member "serviceAccount:${DEPLOYER_SA}" --role roles/run.admin --condition=None >/dev/null
# Push images to this one repository only
gcloud artifacts repositories add-iam-policy-binding "$AR_REPO" --location "$REGION" --project "$PROJECT_ID" \
  --member "serviceAccount:${DEPLOYER_SA}" --role roles/artifactregistry.writer >/dev/null
# Deploy revisions that run as the runtime service account
gcloud iam service-accounts add-iam-policy-binding "$RUNTIME_SA" --project "$PROJECT_ID" \
  --member "serviceAccount:${DEPLOYER_SA}" --role roles/iam.serviceAccountUser >/dev/null

echo ""
echo "4/5 Workload Identity pool and GitHub OIDC provider..."
if ! gcloud iam workload-identity-pools describe "$POOL_ID" --location global --project "$PROJECT_ID" &>/dev/null; then
  gcloud iam workload-identity-pools create "$POOL_ID" --location global --project "$PROJECT_ID" \
    --display-name "GitHub Actions"
fi
ATTRIBUTE_CONDITION="assertion.repository=='${GITHUB_REPO}' && assertion.ref=='refs/heads/${BRANCH}'"
if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_ID" --workload-identity-pool "$POOL_ID" \
    --location global --project "$PROJECT_ID" &>/dev/null; then
  gcloud iam workload-identity-pools providers create-oidc "$PROVIDER_ID" \
    --workload-identity-pool "$POOL_ID" --location global --project "$PROJECT_ID" \
    --display-name "GitHub OIDC" \
    --issuer-uri "https://token.actions.githubusercontent.com" \
    --attribute-mapping "google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" \
    --attribute-condition "$ATTRIBUTE_CONDITION"
else
  gcloud iam workload-identity-pools providers update-oidc "$PROVIDER_ID" \
    --workload-identity-pool "$POOL_ID" --location global --project "$PROJECT_ID" \
    --attribute-condition "$ATTRIBUTE_CONDITION" >/dev/null
fi

echo ""
echo "5/5 Letting ${GITHUB_REPO} impersonate the deployer..."
gcloud iam service-accounts add-iam-policy-binding "$DEPLOYER_SA" --project "$PROJECT_ID" \
  --role roles/iam.workloadIdentityUser \
  --member "principalSet://iam.googleapis.com/${POOL_NAME}/attribute.repository/${GITHUB_REPO}" >/dev/null

cat <<EOF

======================================================
✅ GCP setup complete.
======================================================
Configure the "production" environment in GitHub
(Settings → Environments → production), or run these with the gh CLI:

Variables (not secret):
  gh variable set GCP_PROJECT_ID --env production --repo ${GITHUB_REPO} --body "${PROJECT_ID}"
  gh variable set GCP_REGION --env production --repo ${GITHUB_REPO} --body "${REGION}"
  gh variable set GCP_SERVICE_NAME --env production --repo ${GITHUB_REPO} --body "${SERVICE_NAME}"
  gh variable set GCP_ARTIFACT_REPO --env production --repo ${GITHUB_REPO} --body "${AR_REPO}"
  gh variable set GCP_WORKLOAD_IDENTITY_PROVIDER --env production --repo ${GITHUB_REPO} --body "${PROVIDER_NAME}"
  gh variable set GCP_DEPLOY_SERVICE_ACCOUNT --env production --repo ${GITHUB_REPO} --body "${DEPLOYER_SA}"
  gh variable set ALLOWED_EDITOR_EMAILS --env production --repo ${GITHUB_REPO} --body "admin@yourdomain.com"
  gh variable set GOOGLE_CLIENT_ID --env production --repo ${GITHUB_REPO} --body "<oauth-client-id>"
  # Optional: CUSTOM_DOMAIN or FRONTEND_URL, MONGODB_DB_NAME, AUTO_SEED, LOG_LEVEL

Secrets (each command prompts for the value, so it stays out of shell history):
  gh secret set MONGODB_URI --env production --repo ${GITHUB_REPO}
  gh secret set JWT_SECRET --env production --repo ${GITHUB_REPO}       # openssl rand -hex 32
  gh secret set GOOGLE_CLIENT_SECRET --env production --repo ${GITHUB_REPO}   # optional

The next push to ${BRANCH} deploys automatically, or run the "Deploy" workflow manually.
======================================================
EOF
