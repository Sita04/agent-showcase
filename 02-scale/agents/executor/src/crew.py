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

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from crewai import Crew, Process, LLM
from src.agents import ExecutorAgents
from src.tasks import ExecutorTasks
from src.tools import get_mcp_server
from dotenv import load_dotenv
import logging
from config.default_config import config

# Set up logging to capture any reasoning errors
logging.basicConfig(level=logging.INFO)

# Load environment variables and set dummy OpenAI API key
load_dotenv()
os.environ["OPENAI_API_KEY"] = config.DUMMY_OPENAI_KEY

class LogisticsExecutionCrew:
    """Orchestrates the Sourcing and Procurement Agents."""

    def __init__(self):
        self.agents = ExecutorAgents()
        self.tasks = ExecutorTasks()

    def run(self, task_description: str, budget: float, quantity: int):
        """
        Executes a restock request.
        
        Args:
            task_description: The description of the item to restock (e.g., "Vintage Sci-Fi Mugs").
            budget: Maximum price per unit.
            quantity: Number of units to order.
        """
        # Connect to the Vector Search MCP server
        mcp_server = get_mcp_server()
        with mcp_server as mcp_tools:
            # Create Agents
            sourcing_agent = self.agents.sourcing_specialist(mcp_tools=mcp_tools)
            procurement_agent = self.agents.procurement_officer()

            # Define Tasks
            sourcing_task = self.tasks.sourcing_task(
                agent=sourcing_agent,
                item_description=task_description,
                max_budget=budget
            )

            procurement_task = self.tasks.procurement_task(
                agent=procurement_agent,
                quantity=quantity
            )

            # Link context manually (optional in new CrewAI versions, but good practice)
            procurement_task.context = [sourcing_task]

            # Configure Embedder
            from typing import Any
            vertex_embedder: Any = {
                "provider": "google-vertex",
                "config": {
                    "model_name": config.EMBEDDER_MODEL,
                    "project_id": config.GOOGLE_CLOUD_PROJECT,
                    "location": config.GOOGLE_CLOUD_LOCATION_REGIONAL
                }
            }

            # Create Crew
            crew = Crew(
                agents=[sourcing_agent, procurement_agent],
                tasks=[sourcing_task, procurement_task],
                process=Process.sequential, # Run sequentially: Source --> Procure
                verbose=True,
                memory=False,
                planning=True,
                planning_llm=LLM(model=config.PLANNING_MODEL),
                embedder=vertex_embedder # type: ignore
            )

            # Execute
            result = crew.kickoff()
            return result

# Example Usage (for testing)
if __name__ == "__main__":
    crew = LogisticsExecutionCrew()
    print("Starting Crew execution...")
    result = crew.run(task_description="Rare Japanese Anime Figure", budget=50.0, quantity=2)
    print("\n\n########################")
    print("## Final Result: ##")
    print("########################\n")
    print(result)
