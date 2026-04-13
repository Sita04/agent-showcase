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

"""Warm up Agent Engine instances in parallel.

Agent Engine scales to zero when idle. Cold starts take 3-5 minutes per
engine. This script sends a lightweight query to both the Planning Agent
and Execution Crew concurrently so you only wait once.

Usage:
    uv run scripts/warmup_agent_engines.py
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import vertexai

SCALE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
METADATA_FILE = os.path.join(SCALE_DIR, "deployment_metadata.json")

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "gcp-samples-ic0")
REGION = "us-central1"


def load_metadata() -> dict:
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE) as f:
            return json.load(f)
    return {}


def warmup_engine(client, engine_id: str, label: str, query_input: str) -> str:
    """Send a warm-up query to an Agent Engine instance."""
    print(f"  [{label}] Fetching engine {engine_id.split('/')[-1]}...")
    engine = client.agent_engines.get(name=engine_id)
    print(f"  [{label}] Sending warm-up query...")
    start = time.monotonic()
    result = engine.query(input=query_input)
    elapsed = time.monotonic() - start
    preview = str(result)[:200]
    return f"  [{label}] Ready in {elapsed:.0f}s — {preview}"


def main():
    metadata = load_metadata()
    planning_id = metadata.get("planning_agent_engine_id", "")
    crew_id = metadata.get("crew_agent_engine_id", "")

    if not planning_id or not crew_id:
        print("ERROR: deployment_metadata.json missing engine IDs.")
        print("  Deploy both engines first with scripts/deploy_to_agent_engine.py")
        sys.exit(1)

    print(f"Project: {PROJECT_ID}")
    print(f"Region:  {REGION}")
    print(f"\nWarming up both Agent Engine instances in parallel...\n")

    client = vertexai.Client(project=PROJECT_ID, location=REGION)
    start = time.monotonic()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            pool.submit(
                warmup_engine, client, crew_id,
                "Execution Crew",
                '{"task_description": "warm-up ping", "budget": 10, "quantity": 1}',
            ): "crew",
            pool.submit(
                warmup_engine, client, planning_id,
                "Planning Agent",
                "Hello, warm-up ping.",
            ): "planner",
        }
        for future in as_completed(futures):
            try:
                print(future.result())
            except Exception as e:
                label = futures[future]
                print(f"  [{label}] FAILED: {e}")

    total = time.monotonic() - start
    print(f"\nDone in {total:.0f}s. Both engines are warm.")


if __name__ == "__main__":
    main()
