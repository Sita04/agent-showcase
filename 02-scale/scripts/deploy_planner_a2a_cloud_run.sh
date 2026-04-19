#!/usr/bin/env bash

set -euo pipefail

# Load demo config from 02-scale/.env. See deploy_control_room_cloud_run.sh
# for the full rationale — short version: corp shells often have a stale
# GOOGLE_CLOUD_PROJECT export that misroutes the Cloud Build source upload.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

if [[ -z "${GOOGLE_CLOUD_PROJECT:-}" ]]; then
  echo "ERROR: GOOGLE_CLOUD_PROJECT is not set. Define it in 02-scale/.env."
  exit 1
fi
PROJECT_ID="${GOOGLE_CLOUD_PROJECT}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE_NAME="${PLANNER_A2A_SERVICE_NAME:-scale-planner-a2a}"
REPOSITORY="${ARTIFACT_REPOSITORY:-agent-showcase}"
SERVICE_ACCOUNT="${PLANNER_A2A_SERVICE_ACCOUNT:-planning-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:latest"
PLANNING_AGENT_ENGINE_ID="${PLANNING_AGENT_ENGINE_ID:-}"
CONTROL_ROOM_URL="${CONTROL_ROOM_URL:-}"

if [[ -z "${PLANNING_AGENT_ENGINE_ID}" ]]; then
  echo "PLANNING_AGENT_ENGINE_ID is required."
  echo "Example:"
  echo "  PLANNING_AGENT_ENGINE_ID=projects/.../reasoningEngines/... bash scripts/deploy_planner_a2a_cloud_run.sh"
  exit 1
fi

echo "=== Deploying Planner A2A Bridge to Cloud Run ==="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo "Image: ${IMAGE_URI}"
echo "Planning Agent Engine: ${PLANNING_AGENT_ENGINE_ID}"
echo "Service Account: ${SERVICE_ACCOUNT}"
echo ""

# Copy uv.lock from root to context directory
cp ../uv.lock .

# Get access token for private registry.
# If CORP_ACCESS_TOKEN is set (e.g. fetched from a corp machine), use it
# instead of minting one locally — handy when the corp account isn't logged
# in on this machine.
TOKEN="${CORP_ACCESS_TOKEN:-$(gcloud auth print-access-token)}"
UV_URL="https://oauth2accesstoken:${TOKEN}@us-python.pkg.dev/artifact-foundry-prod/ah-3p-staging-python/simple/"

gcloud builds submit \
  --project "${PROJECT_ID}" \
  --config cloudbuild-planner-a2a.yaml \
  --substitutions "_IMAGE_URI=${IMAGE_URI},_UV_EXTRA_INDEX_URL=${UV_URL}" \
  .

# Write env vars to a temp YAML file so values with special characters (URLs,
# resource names) can't unbalance shell quoting on --set-env-vars.
ENV_FILE="$(mktemp -t scale-planner-a2a-env.XXXXXX.yaml)"
trap 'rm -f "${ENV_FILE}"' EXIT
cat > "${ENV_FILE}" <<YAML
GOOGLE_CLOUD_PROJECT: "${PROJECT_ID}"
GOOGLE_CLOUD_LOCATION: "${REGION}"
PLANNING_AGENT_ENGINE_ID: "${PLANNING_AGENT_ENGINE_ID}"
GOOGLE_GENAI_USE_VERTEXAI: "TRUE"
YAML

# Only set CONTROL_ROOM_STATUS_URL when CONTROL_ROOM_URL is provided. Without
# this guard, an unset CONTROL_ROOM_URL would produce "/api/push_status" — a
# host-less URL that silently drops every status push and breaks the dashboard
# Planner/Executor bubbles.
if [[ -n "${CONTROL_ROOM_URL}" ]]; then
  echo "CONTROL_ROOM_STATUS_URL: \"${CONTROL_ROOM_URL%/}/api/push_status\"" >> "${ENV_FILE}"
else
  echo "CONTROL_ROOM_URL not set — skipping CONTROL_ROOM_STATUS_URL."
  echo "Run 'gcloud run services update scale-planner-a2a --update-env-vars CONTROL_ROOM_STATUS_URL=...' after the Control Room is deployed."
fi

gcloud run deploy "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --image "${IMAGE_URI}" \
  --service-account "${SERVICE_ACCOUNT}" \
  --env-vars-file "${ENV_FILE}" \
  --concurrency 10 \
  --min-instances 1 \
  --timeout 300 \
  --memory 2Gi \
  --allow-unauthenticated

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.url)')"

gcloud run services update "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --update-env-vars "PLANNER_AGENT_URL=${SERVICE_URL}"

echo ""
echo "Planner A2A bridge deployed to Cloud Run."
echo "URL: ${SERVICE_URL}"
