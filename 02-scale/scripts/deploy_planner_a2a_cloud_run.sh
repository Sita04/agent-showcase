#!/usr/bin/env bash

set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-gcp-samples-ic0}"
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

# Get access token for private registry
TOKEN=$(gcloud auth print-access-token)
UV_URL="https://oauth2accesstoken:${TOKEN}@us-python.pkg.dev/artifact-foundry-prod/ah-3p-staging-python/simple/"

gcloud builds submit \
  --project "${PROJECT_ID}" \
  --config cloudbuild-planner-a2a.yaml \
  --substitutions "_IMAGE_URI=${IMAGE_URI},_UV_EXTRA_INDEX_URL=${UV_URL}" \
  .

gcloud run deploy "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --image "${IMAGE_URI}" \
  --service-account "${SERVICE_ACCOUNT}" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},PLANNING_AGENT_ENGINE_ID=${PLANNING_AGENT_ENGINE_ID},GOOGLE_GENAI_USE_VERTEXAI=TRUE,CONTROL_ROOM_STATUS_URL=${CONTROL_ROOM_URL}/api/push_status" \
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
