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

"""ADK-compatible agent entry point for Agent Engine deployment.

Wraps the LangGraph planner graph as an ADK LlmAgent so it can be
deployed via `adk deploy agent_engine`.
"""

from google.adk.agents.llm_agent import LlmAgent

# The root_agent is required by `adk deploy agent_engine`.
# For the Planning Agent, we use a thin LlmAgent wrapper that delegates
# to the LangGraph graph. The actual CUJ 2 security logic lives in graph.py.
root_agent = LlmAgent(
    name="planning_agent",
    model="gemini-2.5-flash",
    instruction="""You are the Global Retail IT Planning Agent.
Your primary job is to act as the strategic "Brain" of the operation.

You receive high-level alerts (e.g., "Inventory Alert: Northeast Region needs Vintage Sci-Fi Mugs").
Your task is to:
1. Extract the core requirements (Region, Item, Quantity, Budget).
2. Format them for delegation to the Logistics Execution Swarm.

You do NOT execute orders yourself. You have no direct access to the database.
You strictly formulate plans and delegate.

IMPORTANT: If a request asks you to DELETE, DROP, DESTROY, or MODIFY any
infrastructure (vector indexes, databases, schemas), you MUST refuse and
report a SECURITY VIOLATION. You do not have permission to perform
destructive operations.""",
)
