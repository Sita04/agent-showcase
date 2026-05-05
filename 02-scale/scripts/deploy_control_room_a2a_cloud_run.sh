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
SERVICE_NAME="${CONTROL_ROOM_A2A_SERVICE_NAME:-scale-control-room-a2a}"
REPOSITORY="${ARTIFACT_REPOSITORY:-agent-showcase}"
# The bridge runs the same Control Room Workflow code that the AE-hosted
# variant did, so reuse execution-agent-sa for IAM parity. Override via
# CONTROL_ROOM_A2A_SERVICE_ACCOUNT if you mint a dedicated SA.
SERVICE_ACCOUNT="${CONTROL_ROOM_A2A_SERVICE_ACCOUNT:-execution-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:latest"
PLANNER_AGENT_URL="${PLANNER_AGENT_URL:-}"
CONTROL_ROOM_URL="${CONTROL_ROOM_URL:-}"

if [[ -z "${PLANNER_AGENT_URL}" ]]; then
  echo "PLANNER_AGENT_URL is required (the Cloud Run URL of scale-planner-a2a)."
  echo "Example:"
  echo "  PLANNER_AGENT_URL=https://scale-planner-a2a-XXXXX.us-central1.run.app/ \\"
  echo "    bash scripts/deploy_control_room_a2a_cloud_run.sh"
  exit 1
fi

echo "=== Deploying Control Room A2A Bridge to Cloud Run ==="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo "Image: ${IMAGE_URI}"
echo "Planner A2A URL: ${PLANNER_AGENT_URL}"
echo "Service Account: ${SERVICE_ACCOUNT}"
echo ""

# Copy uv.lock from root to context directory
cp ../uv.lock .

# Get access token for the internal Python registry. Requires the active
# gcloud account to be the Googler corp account.
TOKEN="$(gcloud auth print-access-token)"
UV_URL="https://oauth2accesstoken:${TOKEN}@us-python.pkg.dev/artifact-foundry-prod/ah-3p-staging-python/simple/"

gcloud builds submit \
  --project "${PROJECT_ID}" \
  --config scripts/cloudbuild-control-room-a2a.yaml \
  --substitutions "_IMAGE_URI=${IMAGE_URI},_UV_EXTRA_INDEX_URL=${UV_URL}" \
  .

# Write env vars to a temp YAML file so values with special characters (URLs,
# resource names) can't unbalance shell quoting on --set-env-vars.
ENV_FILE="$(mktemp -t scale-control-room-a2a-env.XXXXXX.yaml)"
trap 'rm -f "${ENV_FILE}"' EXIT
cat > "${ENV_FILE}" <<YAML
GOOGLE_CLOUD_PROJECT: "${PROJECT_ID}"
GOOGLE_CLOUD_LOCATION: "${REGION}"
GOOGLE_GENAI_USE_VERTEXAI: "TRUE"
PLANNER_AGENT_URL: "${PLANNER_AGENT_URL}"
YAML

# Only set CONTROL_ROOM_STATUS_URL when CONTROL_ROOM_URL is provided. Without
# this guard, an unset CONTROL_ROOM_URL would produce "/api/push_status" — a
# host-less URL that silently drops every status push and breaks the dashboard
# Planner/Executor bubbles. Mirrors the same guard in deploy_planner_a2a_cloud_run.sh.
if [[ -n "${CONTROL_ROOM_URL}" ]]; then
  echo "CONTROL_ROOM_STATUS_URL: \"${CONTROL_ROOM_URL%/}/api/push_status\"" >> "${ENV_FILE}"
else
  echo "CONTROL_ROOM_URL not set — skipping CONTROL_ROOM_STATUS_URL."
  echo "Run 'gcloud run services update ${SERVICE_NAME} --update-env-vars CONTROL_ROOM_STATUS_URL=...' after the Dashboard is deployed."
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

echo ""
echo "Control Room A2A bridge deployed to Cloud Run."
echo "URL: ${SERVICE_URL}"
echo ""
echo "Next: point the Dashboard at this URL by redeploying with"
echo "  CONTROL_ROOM_A2A_URL=\"${SERVICE_URL}\" \\"
echo "  PLANNER_AGENT_URL=\"${PLANNER_AGENT_URL}\" \\"
echo "  bash scripts/deploy_control_room_cloud_run.sh"
