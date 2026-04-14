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

# CUJ 2: Teardown — Remove Agent Engine instances, service accounts, and IAM policies.
#
# Usage:
#   bash scripts/teardown.sh

set -euo pipefail

PROJECT_ID="${GOOGLE_CLOUD_PROJECT:-gcp-samples-ic0}"
PLANNING_SA_EMAIL="planning-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com"
EXECUTION_SA_EMAIL="execution-agent-sa@${PROJECT_ID}.iam.gserviceaccount.com"
DENY_POLICY_ID="deny-planning-agent-index-delete"

echo "=== CUJ 2: Teardown ==="
echo "Project: ${PROJECT_ID}"
echo ""

# Step 1: Delete Agent Engine instances
echo "--- Step 1: Deleting Agent Engine instances"
cd "$(dirname "$0")/.."
uv run scripts/deploy_to_agent_engine.py --teardown || echo "  (deploy teardown skipped or failed)"

# Step 2: Remove IAM deny policy
echo ""
echo "--- Step 2: Removing IAM deny policy"
if gcloud iam policies get "${DENY_POLICY_ID}" \
    --attachment-point="cloudresourcemanager.googleapis.com/projects/${PROJECT_ID}" \
    --kind=denypolicies 2>/dev/null; then
    gcloud iam policies delete "${DENY_POLICY_ID}" \
        --attachment-point="cloudresourcemanager.googleapis.com/projects/${PROJECT_ID}" \
        --kind=denypolicies \
        --quiet
    echo "  Deny policy deleted."
else
    echo "  Deny policy not found, skipping."
fi

# Step 3: Remove IAM role bindings
echo ""
echo "--- Step 3: Removing IAM role bindings"

for SA_EMAIL in "${PLANNING_SA_EMAIL}" "${EXECUTION_SA_EMAIL}"; do
    for ROLE in "roles/aiplatform.user" "roles/aiplatform.editor"; do
        echo "  Removing ${ROLE} from ${SA_EMAIL}..."
        gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
            --member="serviceAccount:${SA_EMAIL}" \
            --role="${ROLE}" \
            --quiet 2>/dev/null || echo "    (not bound, skipping)"
    done
done

# Step 4: Delete service accounts
echo ""
echo "--- Step 4: Deleting service accounts"

for SA_EMAIL in "${PLANNING_SA_EMAIL}" "${EXECUTION_SA_EMAIL}"; do
    if gcloud iam service-accounts describe "${SA_EMAIL}" --project="${PROJECT_ID}" &>/dev/null; then
        gcloud iam service-accounts delete "${SA_EMAIL}" --project="${PROJECT_ID}" --quiet
        echo "  Deleted ${SA_EMAIL}."
    else
        echo "  ${SA_EMAIL} not found, skipping."
    fi
done

echo ""
echo "=== Teardown Complete ==="
