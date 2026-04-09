#!/usr/bin/env bash

set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-gcp-samples-ic0}"
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

gcloud builds submit \
  --project "${PROJECT_ID}" \
  --config cloudbuild-control-room.yaml \
  --substitutions "_IMAGE_URI=${IMAGE_URI}" \
  .

gcloud run deploy "${SERVICE_NAME}" \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --image "${IMAGE_URI}" \
  --service-account "${CONTROL_ROOM_SA}" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},GOOGLE_GENAI_USE_VERTEXAI=TRUE,PLANNER_AGENT_URL=${PLANNER_AGENT_URL}" \
  --concurrency 1 \
  --min-instances 1 \
  --timeout 300 \
  --memory 2Gi \
  --allow-unauthenticated

echo ""
echo "Control Room deployed to Cloud Run."
