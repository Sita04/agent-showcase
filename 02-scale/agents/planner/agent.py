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

"""Agent Engine wrapper for the LangGraph Planning Agent.

Exposes the planner as a custom agent deployable to Agent Engine via
`client.agent_engines.create(agent=PlanningAgent(...))`.
"""

import logging

logger = logging.getLogger(__name__)


class PlanningAgent:
    """Agent Engine-compatible wrapper for the LangGraph planner."""

    def __init__(
        self,
        project_id: str = "",
        region: str = "us-central1",
        crew_engine_id: str = "",
    ):
        # Only pickle-safe config here
        self.project_id = project_id
        self.region = region
        self.crew_engine_id = crew_engine_id

    def set_up(self):
        """Build the LangGraph graph with optional crew AE handle."""
        import os
        # Allow env var overrides (used in source-based AE deployment)
        if not self.project_id:
            self.project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        if not self.crew_engine_id:
            self.crew_engine_id = os.environ.get("CREW_ENGINE_ID", "")
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", self.project_id)

        crew_engine = None
        if self.crew_engine_id:
            import vertexai
            client = vertexai.Client(
                project=self.project_id, location=self.region
            )
            crew_engine = client.agent_engines.get(name=self.crew_engine_id)

        try:
            from .graph import build_planner_graph
        except ImportError:
            from graph import build_planner_graph
        self._graph = build_planner_graph(crew_engine=crew_engine)

    def query(self, *, input: str) -> str:
        """Run the planner graph synchronously.

        Args:
            input: The objective string (e.g., an inventory alert).

        Returns:
            The final report from the planner.
        """
        try:
            from .state import PlanState
        except ImportError:
            from state import PlanState
        initial_state: PlanState = {"objective": input}
        final_state = self._graph.invoke(initial_state)
        return final_state.get("final_report", "No report generated.")
