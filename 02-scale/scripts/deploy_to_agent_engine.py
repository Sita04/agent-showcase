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

"""CUJ 2: Deploy Planning and Control Room agents to Agent Engine with scoped SAs.

Deploys two Agent Engine instances:
  1. Planning Agent — bound to planning-agent-sa (read-only, no vector store write)
  2. Control Room Agent — bound to execution-agent-sa (full access)

Usage:
    uv run scripts/deploy_to_agent_engine.py
    uv run scripts/deploy_to_agent_engine.py --planning-only
    uv run scripts/deploy_to_agent_engine.py --list
    uv run scripts/deploy_to_agent_engine.py --teardown
"""

import argparse
import json
import os
import subprocess
import sys

import vertexai

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "gcp-samples-ic0")
REGION = "us-central1"
PLANNING_SA = f"planning-agent-sa@{PROJECT_ID}.iam.gserviceaccount.com"
EXECUTION_SA = f"execution-agent-sa@{PROJECT_ID}.iam.gserviceaccount.com"

SCALE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
METADATA_FILE = os.path.join(SCALE_DIR, "deployment_metadata.json")


def load_metadata() -> dict:
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE) as f:
            return json.load(f)
    return {}


def save_metadata(data: dict) -> None:
    with open(METADATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved metadata to {METADATA_FILE}")


def deploy_agent_via_adk(
    agent_dir: str,
    display_name: str,
    project: str,
    region: str,
    agent_engine_id: str | None = None,
) -> str:
    """Deploy an agent using `adk deploy agent_engine` CLI."""
    cmd = [
        sys.executable, "-m", "google.adk.cli",
        "deploy", "agent_engine",
        "--project", project,
        "--region", region,
        "--display_name", display_name,
        "--no-validate-agent-import",
    ]

    if agent_engine_id:
        cmd.extend(["--agent_engine_id", agent_engine_id])

    cmd.append(agent_dir)

    print(f"  Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=SCALE_DIR)

    if result.returncode != 0:
        print(f"  STDOUT: {result.stdout}")
        print(f"  STDERR: {result.stderr}")
        raise RuntimeError(f"adk deploy failed with exit code {result.returncode}")

    print(result.stdout)

    # Parse the engine ID from output
    for line in result.stdout.splitlines():
        if "reasoningEngines/" in line:
            # Extract the resource name
            import re
            match = re.search(r"projects/[^/]+/locations/[^/]+/reasoningEngines/\d+", line)
            if match:
                return match.group(0)

    # Fallback: return empty string if we can't parse the ID
    print("  WARNING: Could not parse engine ID from output")
    return ""


def deploy_planning_agent(args: argparse.Namespace) -> str:
    """Deploy the Planning Agent with restricted SA via adk CLI."""
    print("\n=== Deploying Planning Agent ===")
    print(f"  Service Account: {PLANNING_SA}")
    print(f"  Agent dir: agents/planner")

    metadata = load_metadata()
    existing_id = metadata.get("planning_agent_engine_id") if not args.force else None

    # Extract just the numeric ID if we have a full resource name
    engine_id_param = None
    if existing_id:
        engine_id_param = existing_id.split("/")[-1] if "/" in existing_id else existing_id

    resource_name = deploy_agent_via_adk(
        agent_dir="agents/planner",
        display_name="Planning Agent (Identity Shield - CUJ 2)",
        project=args.project,
        region=args.region,
        agent_engine_id=engine_id_param,
    )

    if resource_name:
        metadata["planning_agent_engine_id"] = resource_name
        metadata["planning_agent_sa"] = PLANNING_SA
        save_metadata(metadata)

    return resource_name


def deploy_control_room_agent(args: argparse.Namespace) -> str:
    """Deploy the Control Room Agent with full SA via adk CLI."""
    print("\n=== Deploying Control Room Agent ===")
    print(f"  Service Account: {EXECUTION_SA}")
    print(f"  Agent dir: agents/control_room")

    metadata = load_metadata()
    existing_id = metadata.get("control_room_agent_engine_id") if not args.force else None

    engine_id_param = None
    if existing_id:
        engine_id_param = existing_id.split("/")[-1] if "/" in existing_id else existing_id

    resource_name = deploy_agent_via_adk(
        agent_dir="agents/control_room",
        display_name="Control Room Agent (CUJ 2)",
        project=args.project,
        region=args.region,
        agent_engine_id=engine_id_param,
    )

    if resource_name:
        metadata["control_room_agent_engine_id"] = resource_name
        metadata["control_room_agent_sa"] = EXECUTION_SA
        save_metadata(metadata)

    return resource_name


def teardown(client: vertexai.Client) -> None:
    """Delete deployed Agent Engine instances."""
    print("\n=== Tearing Down Agent Engine Instances ===")
    metadata = load_metadata()

    for key in ["planning_agent_engine_id", "control_room_agent_engine_id"]:
        engine_id = metadata.get(key)
        if engine_id:
            print(f"  Deleting {key}: {engine_id}...")
            try:
                client.agent_engines.delete(name=engine_id, force=True)
                print(f"  Deleted.")
                del metadata[key]
            except Exception as e:
                print(f"  Failed to delete: {e}")
        else:
            print(f"  {key} not found in metadata, skipping.")

    save_metadata(metadata)
    print("\nTeardown complete.")


def list_engines(client: vertexai.Client) -> None:
    """List existing Agent Engine instances."""
    print("\n=== Existing Agent Engine Instances ===")
    for engine in client.agent_engines.list():
        r = engine.api_resource
        print(f"  {r.name} — {r.display_name or '(no name)'}")


def main():
    parser = argparse.ArgumentParser(
        description="Deploy CUJ 2 agents to Agent Engine"
    )
    parser.add_argument("--project", default=PROJECT_ID, help="GCP project ID")
    parser.add_argument("--region", default=REGION, help="GCP region")
    parser.add_argument("--teardown", action="store_true", help="Delete deployed engines")
    parser.add_argument("--list", action="store_true", dest="list_engines", help="List engines")
    parser.add_argument("--force", action="store_true", help="Force create new engines")
    parser.add_argument("--planning-only", action="store_true", help="Deploy only Planning Agent")
    parser.add_argument("--control-room-only", action="store_true", help="Deploy only Control Room")
    args = parser.parse_args()

    print(f"Project: {args.project}")
    print(f"Region: {args.region}")

    if args.list_engines or args.teardown:
        client = vertexai.Client(project=args.project, location=args.region)
        if args.list_engines:
            list_engines(client)
        if args.teardown:
            teardown(client)
        return

    deploy_planning = not args.control_room_only
    deploy_control_room = not args.planning_only

    if deploy_planning:
        deploy_planning_agent(args)

    if deploy_control_room:
        deploy_control_room_agent(args)

    print("\n=== Deployment Complete ===")
    print(f"Metadata saved to: {METADATA_FILE}")
    print("\nNext steps:")
    print("  1. Bind service accounts to deployed engines (manual step)")
    print("  2. Run 'uv run pytest tests/e2e/test_cuj2_identity_shield.py -v' to verify")


if __name__ == "__main__":
    main()
