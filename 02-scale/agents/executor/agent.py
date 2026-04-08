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

"""Agent Engine wrapper for the CrewAI Logistics Execution Crew.

Exposes the crew as a custom agent deployable to Agent Engine via
`client.agent_engines.create(agent=ExecutionCrewAgent(...))`.
"""

import json
import logging

logger = logging.getLogger(__name__)


class ExecutionCrewAgent:
    """Agent Engine-compatible wrapper for LogisticsExecutionCrew."""

    def __init__(self, project_id: str = "", region: str = "us-central1"):
        # Only pickle-safe config here
        self.project_id = project_id
        self.region = region

    def set_up(self):
        """Initialize environment and import the crew class."""
        import os
        if not self.project_id:
            self.project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", self.project_id)
        os.environ.setdefault("OPENAI_API_KEY", "NA")
        os.environ.setdefault("VERTEXAI_PROJECT", self.project_id)
        os.environ.setdefault("VERTEXAI_LOCATION", "global")

        try:
            from .src.crew import LogisticsExecutionCrew
        except ImportError:
            from src.crew import LogisticsExecutionCrew
        self._crew_class = LogisticsExecutionCrew

    def query(self, *, input: str) -> str:
        """Run the crew with JSON-encoded parameters.

        Args:
            input: JSON string with keys: task_description, budget, quantity.

        Returns:
            Crew execution result as a string.
        """
        params = json.loads(input)
        crew = self._crew_class()
        result = crew.run(
            task_description=params.get("task_description", "Unknown Item"),
            budget=float(params.get("budget", 50.0)),
            quantity=int(params.get("quantity", 1)),
        )
        return str(result)
