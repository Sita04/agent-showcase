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
try:
    from .agents import ExecutorAgents
    from .tasks import ExecutorTasks
    from .tools import get_mcp_server, get_mock_oms_mcp
except ImportError:
    from src.agents import ExecutorAgents
    from src.tasks import ExecutorTasks
    from src.tools import get_mcp_server, get_mock_oms_mcp
from dotenv import load_dotenv
import logging
import threading
import time
try:
    from ...config.default_config import config
except ImportError:
    from config.default_config import config
from contextlib import ExitStack

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

    def run(self, task_description: str, budget: float, quantity: int,
            step_callback=None, status_callback=None):
        """
        Executes a restock request.

        Args:
            task_description: The description of the item to restock (e.g., "Vintage Sci-Fi Mugs").
            budget: Maximum price per unit.
            quantity: Number of units to order.
            step_callback: Optional callback for real-time progress.
            status_callback: Optional callback for initialization status updates.
        """
        def _status(msg: str):
            if status_callback:
                status_callback(msg)

        # Connect to both MCP servers using an ExitStack to manage multiple context managers
        _status("Connecting to the product catalog (Vector Search)...")
        mcp_server = get_mcp_server()
        oms_mcp_server = get_mock_oms_mcp()

        with ExitStack() as stack:
            vector_mcp_tools = stack.enter_context(mcp_server)
            oms_mcp_tools = stack.enter_context(oms_mcp_server)
            _status("Product catalog and order management systems connected.")

            # Create Agents
            sourcing_agent = self.agents.sourcing_specialist(mcp_tools=vector_mcp_tools)
            procurement_agent = self.agents.procurement_officer(mcp_tools=oms_mcp_tools)

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

            # Heartbeat: emit timed messages during the initial gap
            # before the first step_callback fires.
            heartbeat_stop = threading.Event()

            heartbeat_messages = [
                (5,  "Calling the LLM to analyze the request and plan a search strategy..."),
                (12, "Querying the product catalog via Vector Search..."),
                (22, "Processing search results from the catalog..."),
            ]

            def _heartbeat():
                start = time.monotonic()
                for delay, msg in heartbeat_messages:
                    remaining = delay - (time.monotonic() - start)
                    if remaining > 0 and not heartbeat_stop.wait(remaining):
                        _status(msg)
                    if heartbeat_stop.is_set():
                        return

            heartbeat_thread = threading.Thread(target=_heartbeat, daemon=True)

            # Wrap step_callback so the first invocation kills the heartbeat
            original_step_callback = step_callback

            def _step_callback_wrapper(step):
                heartbeat_stop.set()
                if original_step_callback:
                    original_step_callback(step)

            # Create Crew
            crew = Crew(
                agents=[sourcing_agent, procurement_agent],
                tasks=[sourcing_task, procurement_task],
                process=Process.sequential, # Run sequentially: Source --> Procure
                verbose=True,
                memory=False,
                planning=False,  # Disabled due to JSON parsing bugs in gemini-2.5-flash
                embedder=vertex_embedder, # type: ignore
                step_callback=_step_callback_wrapper if step_callback else None
            )

            # Execute
            _status("**Sourcing Specialist** is searching the catalog for matching products...")
            heartbeat_thread.start()
            result = crew.kickoff()
            heartbeat_stop.set()
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
