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

"""CUJ 2: Deploy agents to Agent Engine with scoped service accounts.

Deploys three Agent Engine instances using native framework support:
  1. Execution Crew (CrewAI) — bound to execution-agent-sa (full access)
  2. Planning Agent (LangGraph) — bound to planning-agent-sa (read-only)
  3. Control Room (ADK Workflow) — bound to execution-agent-sa (full access)

Deployment order matters: crew first (planner depends on crew engine ID).

Usage:
    uv run scripts/deploy_to_agent_engine.py --crew-only
    uv run scripts/deploy_to_agent_engine.py --planning-only
    uv run scripts/deploy_to_agent_engine.py --control-room-only
    uv run scripts/deploy_to_agent_engine.py --list
    uv run scripts/deploy_to_agent_engine.py --teardown
"""

import argparse
import json
import os
import re
import subprocess
import sys

import vertexai

from build_patched_crewai_wheel import build_patched_wheel

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "gcp-samples-ic0")
REGION = "us-central1"
PLANNING_SA = f"planning-agent-sa@{PROJECT_ID}.iam.gserviceaccount.com"
EXECUTION_SA = f"execution-agent-sa@{PROJECT_ID}.iam.gserviceaccount.com"

STAGING_BUCKET = f"gs://staging.{PROJECT_ID}.appspot.com"

SCALE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
METADATA_FILE = os.path.join(SCALE_DIR, "deployment_metadata.json")
VENDOR_DIR = os.path.join(SCALE_DIR, "vendor")


def load_metadata() -> dict:
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE) as f:
            return json.load(f)
    return {}


def save_metadata(data: dict) -> None:
    with open(METADATA_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  Saved metadata to {METADATA_FILE}")


def _bind_service_account(
    client: vertexai.Client, engine_id: str, sa_email: str
) -> None:
    """Bind a service account to a deployed Agent Engine instance."""
    print(f"  Binding SA {sa_email} to {engine_id}...")
    client.agent_engines.update(name=engine_id, config={"serviceAccount": sa_email})
    print(f"  SA bound.")


# ---------------------------------------------------------------------------
# Execution Crew (CrewAI) — deployed via Python SDK
# ---------------------------------------------------------------------------

def _relative_to_scale(path: str) -> str:
    """Convert an absolute repo path into the relative path Agent Engine expects."""
    return os.path.relpath(path, SCALE_DIR)


def _ensure_patched_crewai_wheel(custom_path: str = "") -> str:
    """Build or reuse the patched CrewAI wheel bundled with the deployment."""
    if custom_path:
        wheel_path = os.path.abspath(custom_path)
        if not os.path.exists(wheel_path):
            raise FileNotFoundError(f"Patched CrewAI wheel not found: {wheel_path}")
    else:
        wheel_path = str(build_patched_wheel(VENDOR_DIR))

    return _relative_to_scale(wheel_path)


def deploy_execution_crew(args: argparse.Namespace) -> str:
    """Deploy the CrewAI Execution Crew via source deployment.

    Agent Engine source builds run ``compileall`` across installed packages.
    CrewAI ships Jinja2-backed CLI template Python files that break that step.
    This path bundles a patched CrewAI wheel that strips those templates first.
    """
    print("\n=== Deploying Execution Crew (CrewAI via patched wheel) ===")
    print(f"  Service Account: {EXECUTION_SA}")

    client = vertexai.Client(project=args.project, location=args.region)
    metadata = load_metadata()
    existing_id = metadata.get("crew_agent_engine_id") if not args.force else None
    patched_wheel = _ensure_patched_crewai_wheel(args.crewai_wheel)

    config = {
        "display_name": "Execution Crew (CUJ 2)",
        "staging_bucket": STAGING_BUCKET,
        "serviceAccount": EXECUTION_SA,
        "requirements": [
            "cloudpickle>=3.0.0",
            "pydantic>=2.0.0",
            patched_wheel,
            "litellm>=1.74.9",
            "crewai-tools==1.6.1",
            "mcp[cli]>=1.26.0",
            "mcpadapt>=0.1.20",
            "fastmcp>=3.1.1",
            "python-dotenv",
            "google-cloud-aiplatform>=1.144",
        ],
        "extra_packages": [
            patched_wheel,
            "agents",
            "mock_oms_mcp",
        ],
    }

    sys.path.insert(0, SCALE_DIR)
    from agents.executor.agent import ExecutionCrewAgent

    agent = ExecutionCrewAgent(project_id=args.project, region=args.region)

    if existing_id:
        print(f"  Updating existing engine: {existing_id}")
        engine = client.agent_engines.update(
            name=existing_id, agent=agent, config=config
        )
    else:
        print("  Creating new engine...")
        engine = client.agent_engines.create(agent=agent, config=config)

    resource_name = engine.api_resource.name
    print(f"  ✅ Deployed: {resource_name}")

    _bind_service_account(client, resource_name, EXECUTION_SA)

    metadata["crew_agent_engine_id"] = resource_name
    metadata["crew_agent_sa"] = EXECUTION_SA
    metadata["crewai_patched_wheel"] = patched_wheel
    save_metadata(metadata)
    return resource_name


# ---------------------------------------------------------------------------
# Planning Agent (LangGraph) — deployed via Python SDK
# ---------------------------------------------------------------------------

def deploy_planning_agent(args: argparse.Namespace) -> str:
    """Deploy the LangGraph Planning Agent as a custom agent."""
    print("\n=== Deploying Planning Agent (LangGraph) ===")
    print(f"  Service Account: {PLANNING_SA}")

    metadata = load_metadata()
    crew_engine_id = metadata.get("crew_agent_engine_id", "")
    if not crew_engine_id:
        raise RuntimeError(
            "Execution Crew must be deployed first. Run with --crew-only first."
        )

    sys.path.insert(0, SCALE_DIR)
    from agents.planner.agent import PlanningAgent

    agent = PlanningAgent(
        project_id=args.project,
        region=args.region,
        crew_engine_id=crew_engine_id,
    )

    client = vertexai.Client(project=args.project, location=args.region)
    existing_id = metadata.get("planning_agent_engine_id") if not args.force else None

    config = {
        "display_name": "Planning Agent (Identity Shield - CUJ 2)",
        "staging_bucket": STAGING_BUCKET,
        "serviceAccount": PLANNING_SA,
        "requirements": [
            "cloudpickle>=3.0.0",
            "pydantic>=2.0.0",
            "langgraph",
            "langchain-google-genai>=4.2.1",
            "langchain-core>=1.2.21",
            "google-cloud-aiplatform>=1.144",
            "google-cloud-resource-manager>=1.14.2",
        ],
        "extra_packages": [
            "agents",
        ],
    }

    if existing_id:
        print(f"  Updating existing engine: {existing_id}")
        engine = client.agent_engines.update(
            name=existing_id, agent=agent, config=config
        )
    else:
        print("  Creating new engine...")
        engine = client.agent_engines.create(agent=agent, config=config)

    resource_name = engine.api_resource.name
    print(f"  ✅ Deployed: {resource_name}")

    _bind_service_account(client, resource_name, PLANNING_SA)

    metadata["planning_agent_engine_id"] = resource_name
    metadata["planning_agent_sa"] = PLANNING_SA
    save_metadata(metadata)
    return resource_name


# ---------------------------------------------------------------------------
# Control Room (ADK Workflow) — deployed via adk CLI
# ---------------------------------------------------------------------------

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

    for line in result.stdout.splitlines():
        if "reasoningEngines/" in line:
            match = re.search(
                r"projects/[^/]+/locations/[^/]+/reasoningEngines/\d+", line
            )
            if match:
                return match.group(0)

    print("  WARNING: Could not parse engine ID from output")
    return ""


def deploy_control_room_agent(args: argparse.Namespace) -> str:
    """Deploy the Control Room Agent with full SA via adk CLI."""
    print("\n=== Deploying Control Room Agent (ADK Workflow) ===")
    print(f"  Service Account: {EXECUTION_SA}")

    metadata = load_metadata()
    existing_id = (
        metadata.get("control_room_agent_engine_id") if not args.force else None
    )

    engine_id_param = None
    if existing_id:
        engine_id_param = (
            existing_id.split("/")[-1] if "/" in existing_id else existing_id
        )

    resource_name = deploy_agent_via_adk(
        agent_dir="agents/control_room",
        display_name="Control Room Agent (CUJ 2)",
        project=args.project,
        region=args.region,
        agent_engine_id=engine_id_param,
    )

    if resource_name:
        client = vertexai.Client(project=args.project, location=args.region)
        _bind_service_account(client, resource_name, EXECUTION_SA)

        metadata["control_room_agent_engine_id"] = resource_name
        metadata["control_room_agent_sa"] = EXECUTION_SA
        save_metadata(metadata)

    return resource_name


# ---------------------------------------------------------------------------
# Teardown & list
# ---------------------------------------------------------------------------

def teardown(client: vertexai.Client) -> None:
    """Delete deployed Agent Engine instances."""
    print("\n=== Tearing Down Agent Engine Instances ===")
    metadata = load_metadata()

    for key in [
        "crew_agent_engine_id",
        "planning_agent_engine_id",
        "control_room_agent_engine_id",
    ]:
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Deploy CUJ 2 agents to Agent Engine"
    )
    parser.add_argument("--project", default=PROJECT_ID, help="GCP project ID")
    parser.add_argument("--region", default=REGION, help="GCP region")
    parser.add_argument("--teardown", action="store_true", help="Delete deployed engines")
    parser.add_argument(
        "--list", action="store_true", dest="list_engines", help="List engines"
    )
    parser.add_argument("--force", action="store_true", help="Force create new engines")
    parser.add_argument("--crew-only", action="store_true", help="Deploy only Execution Crew")
    parser.add_argument(
        "--crewai-wheel",
        default="",
        help="Path to a prebuilt patched CrewAI wheel. If omitted, one is generated locally.",
    )
    parser.add_argument(
        "--planning-only", action="store_true", help="Deploy only Planning Agent"
    )
    parser.add_argument(
        "--control-room-only", action="store_true", help="Deploy only Control Room"
    )
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

    # Determine what to deploy
    specific = args.crew_only or args.planning_only or args.control_room_only
    deploy_crew = args.crew_only or not specific
    deploy_planning = args.planning_only or not specific
    deploy_control_room = args.control_room_only or not specific

    # Enforce deployment order: crew → planner → control room
    if deploy_crew:
        deploy_execution_crew(args)

    if deploy_planning:
        deploy_planning_agent(args)

    if deploy_control_room:
        deploy_control_room_agent(args)

    print("\n=== Deployment Complete ===")
    print(f"Metadata saved to: {METADATA_FILE}")


if __name__ == "__main__":
    main()
