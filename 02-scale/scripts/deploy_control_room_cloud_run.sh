#!/usr/bin/env bash

set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-n26-learn-build-ai-apps-6}"
REGION="${CLOUD_RUN_REGION:-us-central1}"
SERVICE_NAME="${CONTROL_ROOM_SERVICE_NAME:-scale-control-room}"
REPOSITORY="${ARTIFACT_REPOSITORY:-agent-showcase}"
CONTROL_ROOM_SA="${CONTROL_ROOM_SERVICE_ACCOUNT:-control-room-sa@${PROJECT_ID}.iam.gserviceaccount.com}"
IMAGE_URI="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/${SERVICE_NAME}:latest"
PLANNER_AGENT_URL="${PLANNER_AGENT_URL:-}"

if [[ -z "${PLANNER_AGENT_URL}" ]]; then
  echo "PLANNER_AGENT_URL is required."
  echo "Example:"
  echo "  PLANNER_AGENT_URL=https://planner-a2a-xxxxx-uc.a.run.app bash scripts/deploy_control_room_cloud_run.sh"
  exit 1
fi

echo "=== Deploying Control Room (ADK 2.0 Workflow) to Cloud Run ==="
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo "Image: ${IMAGE_URI}"
echo "Planner URL: ${PLANNER_AGENT_URL}"
echo "Service Account: ${CONTROL_ROOM_SA}"
echo ""

# Copy uv.lock from root to context directory
cp ../uv.lock .

# Get access token for private registry
TOKEN=$(gcloud auth print-access-token)
UV_URL="https://oauth2accesstoken:${TOKEN}@us-python.pkg.dev/artifact-foundry-prod/ah-3p-staging-python/simple/"

# Read Control Room Agent ID from metadata if present
CONTROL_ROOM_AGENT_ENGINE_ID=$(python3 -c "import json; print(json.load(open('deployment_metadata.json')).get('control_room_agent_engine_id', ''))" 2>/dev/null || echo "")
echo "Control Room Agent ID from metadata: ${CONTROL_ROOM_AGENT_ENGINE_ID}"

gcloud builds submit \
  --project "${PROJECT_ID}" \
  --config cloudbuild-control-room.yaml \
  --substitutions "_IMAGE_URI=${IMAGE_URI},_UV_EXTRA_INDEX_URL=${UV_URL}" \
  .

# Write env vars to a temp YAML file so values with special characters (URLs,
# resource names) can't unbalance shell quoting on --set-env-vars.
ENV_FILE="$(mktemp -t scale-control-room-env.XXXXXX.yaml)"
trap 'rm -f "${ENV_FILE}"' EXIT
cat > "${ENV_FILE}" <<YAML
GOOGLE_CLOUD_PROJECT: "${PROJECT_ID}"
GOOGLE_CLOUD_LOCATION: "${REGION}"
GOOGLE_GENAI_USE_VERTEXAI: "TRUE"
PLANNER_AGENT_URL: "${PLANNER_AGENT_URL}"
CONTROL_ROOM_AGENT_ENGINE_ID: "${CONTROL_ROOM_AGENT_ENGINE_ID}"
YAML

gcloud run deploy "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --image "${IMAGE_URI}" \
  --service-account "${CONTROL_ROOM_SA}" \
  --env-vars-file "${ENV_FILE}" \
  --concurrency 10 \
  --min-instances 1 \
  --timeout 600 \
  --memory 2Gi \
  --allow-unauthenticated

echo ""
echo "Control Room deployed to Cloud Run."
