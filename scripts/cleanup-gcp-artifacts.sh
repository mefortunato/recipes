#!/usr/bin/env bash
# ==============================================================
# RECIPE BOOK - GCP BUILD ARTIFACTS & STORAGE CLEANUP SCRIPT
# ==============================================================
# Automatically manages and cleans up Google Cloud Build storage
# to stay comfortably below Google Cloud Free Tier limits:
#   - Artifact Registry: 0.5 GB (500 MB) / month free
#   - Cloud Storage:     5.0 GB / month free
# ==============================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${ROOT_DIR}"

# 1. Check gcloud CLI
if ! command -v gcloud &> /dev/null; then
  echo "❌ Error: Google Cloud SDK (gcloud) is not installed."
  exit 1
fi

PROJECT_ID=$(gcloud config get-value project 2>/dev/null || true)
if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "(unset)" ]; then
  echo "❌ Error: No GCP project active. Run: gcloud config set project YOUR_PROJECT_ID"
  exit 1
fi

REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-recipe-book}"
AR_REPO="${AR_REPO:-cloud-run-source-deploy}"
KEEP_COUNT="${KEEP_COUNT:-1}"

echo "======================================================"
echo "🧹 GCP Storage & Build Artifacts Manager"
echo "Project:  ${PROJECT_ID}"
echo "Region:   ${REGION}"
echo "======================================================"

# --------------------------------------------------------------
# 1. Configure Cloud Storage Lifecycle Rule for Source Archives
# --------------------------------------------------------------
SOURCE_BUCKET=$(gcloud storage buckets list --format="value(name)" --filter="name ~ run-sources-${PROJECT_ID}" 2>/dev/null | head -n 1 || true)

if [ -n "$SOURCE_BUCKET" ]; then
  echo ""
  echo "📦 1. Cloud Storage (Source Zip Archives)"
  echo "   Bucket: gs://${SOURCE_BUCKET}"
  
  LIFECYCLE_TMP=$(mktemp)
  cat << 'EOF' > "${LIFECYCLE_TMP}"
{
  "rule": [
    {
      "action": {
        "type": "Delete"
      },
      "condition": {
        "age": 1
      }
    }
  ]
}
EOF
  gcloud storage buckets update "gs://${SOURCE_BUCKET}" --lifecycle-file="${LIFECYCLE_TMP}" >/dev/null 2>&1
  gcloud storage buckets update "gs://${SOURCE_BUCKET}" --clear-soft-delete >/dev/null 2>&1
  rm -f "${LIFECYCLE_TMP}"
  echo "   ✓ Lifecycle policy active: deletes source zips older than 1 day."
  echo "   ✓ Soft-delete retention set to 0 to prevent lingering storage."
  
  # Display current bucket usage
  OBJECTS_COUNT=$(gcloud storage ls --recursive "gs://${SOURCE_BUCKET}/**" 2>/dev/null | wc -l || echo "0")
  echo "   Current objects stored: ${OBJECTS_COUNT} (Free tier limit: 5 GB)"
else
  echo "ℹ️  No run-sources bucket found yet."
fi

# --------------------------------------------------------------
# 2. Configure Artifact Registry Automated Cleanup Policies
# --------------------------------------------------------------
echo ""
echo "🐳 2. Artifact Registry (Container Images)"
echo "   Repository: ${AR_REPO} (${REGION})"

REPO_EXISTS=$(gcloud artifacts repositories describe "${AR_REPO}" --location="${REGION}" --format="value(name)" 2>/dev/null || true)

if [ -n "$REPO_EXISTS" ]; then
  POLICY_TMP=$(mktemp)
  cat << EOF > "${POLICY_TMP}"
[
  {
    "name": "keep-recent-versions",
    "action": {
      "type": "Keep"
    },
    "mostRecentVersions": {
      "keepCount": ${KEEP_COUNT}
    }
  },
  {
    "name": "delete-old-images",
    "action": {
      "type": "Delete"
    },
    "condition": {
      "tagState": "any",
      "olderThan": "86400s"
    }
  }
]
EOF

  gcloud artifacts repositories set-cleanup-policies "${AR_REPO}" \
    --location="${REGION}" \
    --policy="${POLICY_TMP}" \
    --no-dry-run >/dev/null 2>&1
  rm -f "${POLICY_TMP}"
  echo "   ✓ Automated cleanup policy active:"
  echo "     - Retains the ${KEEP_COUNT} most recent versions (active & rollback images)."
  echo "     - Automatically purges older images exceeding the keep count after 1 day."
else
  echo "ℹ️  Artifact Registry repository ${AR_REPO} does not exist yet."
fi

# --------------------------------------------------------------
# 3. Optional Immediate Cleanup: Prune Untagged / Stale Images
# --------------------------------------------------------------
if [ "$1" = "--prune-now" ] && [ -n "$REPO_EXISTS" ]; then
  echo ""
  echo "⚡ Running immediate manual prune (keeping latest ${KEEP_COUNT} images)..."

  # Find active Cloud Run image digest
  ACTIVE_IMAGE=$(gcloud run services describe "${SERVICE_NAME}" --region="${REGION}" --format="value(spec.template.spec.containers[0].image)" 2>/dev/null || true)
  ACTIVE_DIGEST=""
  if [[ "$ACTIVE_IMAGE" == *"@"* ]]; then
    ACTIVE_DIGEST="${ACTIVE_IMAGE#*@}"
  fi

  PACKAGE_PATH="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${SERVICE_NAME}"

  # Get all image digests sorted by creation date (newest first)
  ALL_DIGESTS=$(gcloud artifacts docker images list "${PACKAGE_PATH}" --format="value(version)" --sort-by="~create_time" 2>/dev/null || true)

  INDEX=0
  for DIGEST in ${ALL_DIGESTS}; do
    INDEX=$((INDEX + 1))
    if [ "${INDEX}" -gt "${KEEP_COUNT}" ] && [ "${DIGEST}" != "${ACTIVE_DIGEST}" ]; then
      echo "   🗑️ Deleting older image version: ${DIGEST:0:19}..."
      gcloud artifacts docker images delete "${PACKAGE_PATH}@${DIGEST}" --delete-tags --quiet 2>/dev/null || true
    fi
  done
  echo "   ✓ Immediate prune complete."
fi

# --------------------------------------------------------------
# 4. Summary & Free Tier Health Check
# --------------------------------------------------------------
echo ""
echo "======================================================"
echo "📊 Storage & Free Tier Status"
echo "======================================================"
if [ -n "$REPO_EXISTS" ]; then
  REPO_SIZE_STR=$(gcloud artifacts repositories describe "${AR_REPO}" --location="${REGION}" 2>&1 | grep -i "Repository Size" | head -n 1 | awk '{print $3}' || echo "N/A")
  echo "Artifact Registry Storage: ${REPO_SIZE_STR} (Free tier limit: 500 MB)"
fi
echo ""
echo "Tip: Run './scripts/cleanup-gcp-artifacts.sh --prune-now' to immediately"
echo "     delete old images beyond the ${KEEP_COUNT} newest versions."
echo "======================================================"
