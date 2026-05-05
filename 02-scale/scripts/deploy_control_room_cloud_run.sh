#!/usr/bin/env bash

set -euo pipefail

# Load demo config from 02-scale/.env so GOOGLE_CLOUD_PROJECT,
# GEMINI_API_KEY, etc. live in one place. .env wins over the shell — corp
# shells often have a stale GOOGLE_CLOUD_PROJECT export that would otherwise
# silently route the Cloud Build source upload to the wrong _cloudbuild
# bucket.
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

# Get access token for the internal Python registry. Requires the active
# gcloud account to be the Googler corp account.
TOKEN="$(gcloud auth print-access-token)"
UV_URL="https://oauth2accesstoken:${TOKEN}@us-python.pkg.dev/artifact-foundry-prod/ah-3p-staging-python/simple/"

# Read Control Room Agent ID from metadata if present
CONTROL_ROOM_AGENT_ENGINE_ID=$(python3 -c "import json; print(json.load(open('deployment_metadata.json')).get('control_room_agent_engine_id', ''))" 2>/dev/null || echo "")
echo "Control Room Agent ID from metadata: ${CONTROL_ROOM_AGENT_ENGINE_ID}"

# GEMINI_API_KEY is sourced from .env above. The Explainer Live API needs
# it; without it, the SDK falls back to Vertex where
# gemini-3.1-flash-live-preview is not served. `--env-vars-file` below
# REPLACES env vars on each deploy, so we must forward it explicitly every time.
if [[ -z "${GEMINI_API_KEY:-}" ]]; then
  echo "WARNING: GEMINI_API_KEY not set in 02-scale/.env. Explainer Live API will fail."
fi

gcloud builds submit \
  --project "${PROJECT_ID}" \
  --config scripts/cloudbuild-control-room.yaml \
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
CONTROL_ROOM_A2A_URL: "${CONTROL_ROOM_A2A_URL:-}"
GEMINI_API_KEY: "${GEMINI_API_KEY:-}"
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

# Post-deploy smoke check.
#
# Why this exists: /api/health returns a static {"status":"ok"} that
# never touches control_room_engine, the bridge, or the Explainer Live
# API. So a Cloud Run revision can deploy green and silently fail every
# /api/chat call (e.g. April 2026 incident: a passive uv.lock bump
# baked the broken google-cloud-aiplatform 1.146 SDK call surface into
# the image; revision 00034-x5j served traffic for two weeks before
# anyone noticed). This check actually drives a CUJ end-to-end and
# exits non-zero if the SSE stream lacks a WorkflowComplete frame or
# carries an error frame, so the deploy fails loud instead of going
# green-on-broken.
#
# Skip with SKIP_SMOKE_CHECK=1 (e.g. first-time deploy before the AE
# engine or A2A bridge exists, or air-gapped environments).
if [[ "${SKIP_SMOKE_CHECK:-0}" == "1" ]]; then
  echo ""
  echo "SKIP_SMOKE_CHECK=1 set — skipping post-deploy smoke check."
else
  SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" \
    --project "${PROJECT_ID}" --region "${REGION}" --format='value(status.url)')"

  echo ""
  echo "=== Post-deploy smoke check ==="
  echo "Driving CUJ 1 against ${SERVICE_URL}/api/chat (timeout 540s for AE cold start)..."

  SMOKE_OUTPUT="$(mktemp -t scale-smoke.XXXXXX.txt)"
  trap 'rm -f "${ENV_FILE}" "${SMOKE_OUTPUT}"' EXIT

  if ! curl -sS -X POST "${SERVICE_URL}/api/chat" \
        -F "prompt=Restock 2 Google Droid figures for the Tokyo office" \
        -F "session_id=smoke-$(date +%s)" \
        --max-time 540 > "${SMOKE_OUTPUT}" 2>&1; then
    echo "❌ Smoke check FAILED — curl returned non-zero."
    echo "----- output -----"
    cat "${SMOKE_OUTPUT}"
    exit 1
  fi

  ERROR_COUNT="$(grep -c '"name": "error"' "${SMOKE_OUTPUT}" || true)"
  COMPLETE_COUNT="$(grep -c '"event_type": "WorkflowComplete"' "${SMOKE_OUTPUT}" || true)"

  if [[ "${ERROR_COUNT}" != "0" ]] || [[ "${COMPLETE_COUNT}" == "0" ]]; then
    echo "❌ Smoke check FAILED — error_frames=${ERROR_COUNT} workflow_complete_frames=${COMPLETE_COUNT}"
    echo "----- last 10 frames -----"
    tail -10 "${SMOKE_OUTPUT}"
    exit 1
  fi

  echo "✅ Smoke check passed (WorkflowComplete=${COMPLETE_COUNT}, errors=${ERROR_COUNT})."
fi
