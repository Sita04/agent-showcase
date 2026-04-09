#!/usr/bin/env bash
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# CUJ 2: Identity Shield — IAM Setup
#
# Creates service accounts and binds IAM roles for the Identity Shield demo.
# The planning agent uses a custom least-privilege role that preserves only the
# model + Agent Engine permissions needed for the demo, without vector index
# mutation permissions. A deny policy remains an optional extra guardrail when
# the caller has iam.denypolicies.create.
# The execution agent SA gets full access including vector store write.
#
# Prerequisites:
#   - gcloud authenticated with IAM Admin permissions on the project
#   - Vertex AI API enabled
#
# Usage:
#   bash scripts/setup_iam.sh

set -uo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-gcp-samples-ic0}"
REGION="us-central1"
PLANNING_SA="planning-agent-sa"
EXECUTION_SA="execution-agent-sa"
PLANNING_ROLE_ID="planningAgentRuntime"
PLANNING_ROLE="projects/${PROJECT_ID}/roles/${PLANNING_ROLE_ID}"
PLANNING_SA_EMAIL="${PLANNING_SA}@${PROJECT_ID}.iam.gserviceaccount.com"
EXECUTION_SA_EMAIL="${EXECUTION_SA}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=== CUJ 2: Identity Shield — IAM Setup ==="
echo "Project: ${PROJECT_ID}"
echo "Planning Agent SA: ${PLANNING_SA_EMAIL}"
echo "Execution Agent SA: ${EXECUTION_SA_EMAIL}"
echo ""

# --- Step 1: Create Service Accounts (idempotent) ---
echo "--- Step 1: Creating service accounts ---"

if gcloud iam service-accounts describe "${PLANNING_SA_EMAIL}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "  ${PLANNING_SA} already exists, skipping."
else
    gcloud iam service-accounts create "${PLANNING_SA}" \
        --display-name="Planning Agent (Identity Shield - Read Only)" \
        --description="CUJ 2: Planning Agent SA with restricted permissions - no vector store write access" \
        --project="${PROJECT_ID}"
    echo "  Created ${PLANNING_SA}."
fi

if gcloud iam service-accounts describe "${EXECUTION_SA_EMAIL}" --project="${PROJECT_ID}" &>/dev/null; then
    echo "  ${EXECUTION_SA} already exists, skipping."
else
    gcloud iam service-accounts create "${EXECUTION_SA}" \
        --display-name="Execution Agent (Full MCP Access)" \
        --description="CUJ 2: Execution Agent SA with full MCP tool access including vector store write" \
        --project="${PROJECT_ID}"
    echo "  Created ${EXECUTION_SA}."
fi

# --- Step 1.5: Create or Update Least-Privilege Planner Role ---
echo ""
echo "--- Step 1.5: Ensuring custom planning runtime role ---"

PLANNING_ROLE_PERMISSIONS="aiplatform.endpoints.predict,aiplatform.locations.get,aiplatform.locations.list,aiplatform.reasoningEngines.get,aiplatform.reasoningEngines.query,resourcemanager.projects.get"

if gcloud iam roles describe "${PLANNING_ROLE_ID}" \
    --project="${PROJECT_ID}" \
    --format="value(name)" &>/dev/null; then
    echo "  ${PLANNING_ROLE_ID} already exists, updating permissions."
    gcloud iam roles update "${PLANNING_ROLE_ID}" \
        --project="${PROJECT_ID}" \
        --title="Planning Agent Runtime" \
        --description="Least-privilege runtime role for CUJ 2 planning agent" \
        --permissions="${PLANNING_ROLE_PERMISSIONS}" \
        --stage=GA > /dev/null
else
    echo "  Creating ${PLANNING_ROLE_ID} custom role."
    gcloud iam roles create "${PLANNING_ROLE_ID}" \
        --project="${PROJECT_ID}" \
        --title="Planning Agent Runtime" \
        --description="Least-privilege runtime role for CUJ 2 planning agent" \
        --permissions="${PLANNING_ROLE_PERMISSIONS}" \
        --stage=GA > /dev/null
fi

# --- Step 2: Grant IAM Roles ---
echo ""
echo "--- Step 2: Granting IAM roles ---"

# Planning Agent: use the custom least-privilege runtime role.
echo "  Granting ${PLANNING_ROLE} to ${PLANNING_SA}..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${PLANNING_SA_EMAIL}" \
    --role="${PLANNING_ROLE}" \
    --condition=None \
    --quiet > /dev/null

echo "  Removing legacy roles/aiplatform.user from ${PLANNING_SA} if present..."
gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${PLANNING_SA_EMAIL}" \
    --role="roles/aiplatform.user" \
    --condition=None \
    --quiet > /dev/null 2>&1 || true

# Execution Agent: Vertex AI User + Editor (full access)
echo "  Granting roles/aiplatform.user to ${EXECUTION_SA}..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${EXECUTION_SA_EMAIL}" \
    --role="roles/aiplatform.user" \
    --condition=None \
    --quiet > /dev/null

echo "  Granting roles/aiplatform.editor to ${EXECUTION_SA}..."
gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${EXECUTION_SA_EMAIL}" \
    --role="roles/aiplatform.editor" \
    --condition=None \
    --quiet > /dev/null

# --- Step 3: Create IAM Deny Policy for Planning Agent ---
# This explicitly denies the planning agent from deleting vector indexes.
echo ""
echo "--- Step 3: Creating IAM deny policy for Planning Agent ---"

DENY_POLICY_ID="deny-planning-agent-index-delete"

# Check if deny policy already exists
if gcloud iam policies get "${DENY_POLICY_ID}" \
    --attachment-point="cloudresourcemanager.googleapis.com/projects/${PROJECT_ID}" \
    --kind=denypolicies \
    --format="value(name)" 2>/dev/null; then
    echo "  Deny policy ${DENY_POLICY_ID} already exists, skipping."
else
    echo "  Creating deny policy to block ${PLANNING_SA} from deleting indexes..."
    echo "  (Requires iam.denypolicies.create — skipped if permission denied)"
    gcloud iam policies create "${DENY_POLICY_ID}" \
        --attachment-point="cloudresourcemanager.googleapis.com/projects/${PROJECT_ID}" \
        --kind=denypolicies \
        --policy-file=<(cat <<POLICY
{
  "displayName": "Deny Planning Agent Index Delete (CUJ 2)",
  "rules": [
    {
      "denyRule": {
        "deniedPrincipals": [
          "principal://iam.googleapis.com/projects/-/serviceAccounts/${PLANNING_SA_EMAIL}"
        ],
        "deniedPermissions": [
          "aiplatform.googleapis.com/indexes.delete",
          "aiplatform.googleapis.com/indexes.update",
          "aiplatform.googleapis.com/indexEndpoints.delete",
          "aiplatform.googleapis.com/indexEndpoints.update"
        ]
      }
    }
  ]
}
POLICY
    ) && echo "  Deny policy created." || echo "  WARNING: Deny policy creation failed (needs iam.denypolicies.create). The custom planningAgentRuntime role still enforces CUJ 2 least privilege, but the deny policy remains a useful extra guardrail."
fi

echo ""
echo "=== IAM Setup Complete ==="
echo ""
echo "Planning Agent (${PLANNING_SA_EMAIL}):"
echo "  - ${PLANNING_ROLE} (model + Agent Engine access only)"
echo "  - Does NOT include indexes.delete, indexes.update, indexEndpoints.delete, indexEndpoints.update"
echo ""
echo "Execution Agent (${EXECUTION_SA_EMAIL}):"
echo "  - roles/aiplatform.user (can call Gemini models)"
echo "  - roles/aiplatform.editor (full vector store access)"
echo ""
echo "Next step: Run 'python scripts/deploy_to_agent_engine.py' to deploy agents."
