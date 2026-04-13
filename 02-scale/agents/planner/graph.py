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

import asyncio
import json
import logging
import os

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from google.cloud import aiplatform_v1
from google.cloud import resourcemanager_v3
from google.api_core.exceptions import PermissionDenied, Forbidden, NotFound

try:
    from .state import PlanState, AlertExtraction
except ImportError:
    from state import PlanState, AlertExtraction

try:
    from agents.config.prompts import PLANNER_SYSTEM_PROMPT, REPORT_GENERATOR_PROMPT, SECURITY_REPORT_PROMPT
    from agents.config.default_config import config
except ImportError:
    from config.prompts import (
        PLANNER_SYSTEM_PROMPT,
        REPORT_GENERATOR_PROMPT,
        SECURITY_REPORT_PROMPT,
    )
    from config.default_config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PlannerAgent")


def _push_to_dashboard(msg: str, name: str = "execution", role: str = "planner"):
    """Push a status update directly to the Control Room dashboard.

    This bypasses the A2A artifact mechanism which does not stream
    intermediate updates when using ``message/send``.
    """
    try:
        import requests
        status_url = os.environ.get(
            "CONTROL_ROOM_STATUS_URL",
            "http://127.0.0.1:8000/api/push_status",
        )
        requests.post(
            status_url,
            data={"name": name, "text": msg, "role": role},
            timeout=1.0,
        )
    except Exception:
        pass


class PlannerNodes:
    def __init__(self, crew_engine=None, on_update=None):
        # We use the modern LangChain Google GenAI integration (replaces ChatVertexAI)
        self.llm = ChatGoogleGenerativeAI(
            model=config.PLANNING_MODEL.replace("vertex_ai/", ""), # Remove the crewai vertex prefix if present
            vertexai=True,
            project=config.GOOGLE_CLOUD_PROJECT,
            location=config.GOOGLE_CLOUD_LOCATION_REGIONAL,
            temperature=0,
        )
        # LLM bound to output our specific extraction schema
        self.structured_llm = self.llm.with_structured_output(AlertExtraction)
        # Optional: handle to the Execution Crew on Agent Engine
        self.crew_engine = crew_engine
        # Optional callback for real-time updates
        self.on_update = on_update

    def _has_project_permission(self, project_id: str, permission: str) -> bool:
        """Check whether the current runtime identity has a project-level permission."""
        client = resourcemanager_v3.ProjectsClient()
        response = client.test_iam_permissions(
            resource=f"projects/{project_id}",
            permissions=[permission],
        )
        return permission in response.permissions
        
    async def analyze_alert(self, state: PlanState) -> PlanState:
        """Node 1: Extract intent from the raw objective string."""
        logger.info("--- [Planner] Step 1: Analyzing Alert ---")
        _push_to_dashboard("Understanding the procurement request...", "system")
        if self.on_update:
            await self.on_update("Understanding the procurement request...")

        objective = state.get("objective", "")

        # Use structured LLM to parse the alert
        raw_result = self.structured_llm.invoke(
            [
                ("system", PLANNER_SYSTEM_PROMPT),
                ("user", f"Extract the details from this alert: {objective}")
            ]
        )

        # Ensure Pyright knows it's an AlertExtraction object
        if not isinstance(raw_result, AlertExtraction):
            raise ValueError("Failed to extract structured data from alert")

        result: AlertExtraction = raw_result

        logger.info(f"Extracted: {result}")

        parsed_msg = (
            f"Identified: **{result.item_description}** "
            f"× {result.quantity_needed} units for **{result.region}** office"
        )
        _push_to_dashboard(parsed_msg, "system", role="planner")
        if self.on_update:
            await self.on_update(parsed_msg)

        return {
            "region": result.region,
            "item_description": result.item_description,
            "quantity_needed": result.quantity_needed,
            "max_budget": result.max_budget,
            "current_step": "analyzed",
            "delegation_status": "pending",
            "malicious_intent": result.is_destructive,
        }

    async def delegate_to_executor(self, state: PlanState) -> PlanState:
        """Node 2: Call the CrewAI Execution Crew (via Agent Engine or in-process)."""
        logger.info("--- [Planner] Step 2: Delegating to Execution Swarm (CrewAI) ---")
        
        task_description = state.get("item_description") or "Unknown Item"
        budget = state.get("max_budget") or 50.0
        quantity = state.get("quantity_needed") or 1
        loop = asyncio.get_running_loop()

        async def publish_execution_update(msg: str, name: str = "execution"):
            _push_to_dashboard(msg, name=name, role="executor")
            if self.on_update:
                await self.on_update(msg)

        def schedule_execution_update(msg: str, name: str = "execution") -> None:
            _push_to_dashboard(msg, name=name, role="executor")
            if self.on_update:
                asyncio.run_coroutine_threadsafe(
                    self.on_update(msg),
                    loop,
                )

        # --- Real-time Thought Stream Integration ---
        # Intercept CrewAI logs and pipe them to the dashboard
        class DashboardCallbackHandler(logging.Handler):
            def emit(self, record):
                try:
                    log_msg = self.format(record)
                    # Filter for meaningful agent activity
                    if any(x in log_msg for x in ["Working Agent:", "Action:", "Thought:", "Final Answer:"]):
                        # Strip some of the internal formatting for cleaner UI
                        clean_msg = log_msg.split(" - ")[-1] if " - " in log_msg else log_msg
                        schedule_execution_update(clean_msg)
                except Exception:
                    pass

        thought_handler = DashboardCallbackHandler()
        thought_handler.setLevel(logging.INFO)
        # Attach to both crewai and the root logger during execution
        logging.getLogger("crewai").addHandler(thought_handler)

        await publish_execution_update(
            f"Assembling a specialized agent team to source and procure **{task_description}**..."
        )

        try:
            if self.crew_engine is not None:
                # Call the Execution Crew on Agent Engine
                input_payload = json.dumps({
                    "task_description": task_description,
                    "budget": budget,
                    "quantity": quantity,
                })
                result = self.crew_engine.query(input=input_payload)
            else:
                # Fallback: run CrewAI in-process (local dev)
                try:
                    from ..executor.src.crew import LogisticsExecutionCrew
                except ImportError:
                    from agents.executor.src.crew import LogisticsExecutionCrew
                crew = LogisticsExecutionCrew()
                
                # Bridge CrewAI's sync step_callback to our dashboard pusher
                def _parse_tool_input(raw):
                    """Try to parse tool_input as a dict."""
                    if isinstance(raw, dict):
                        return raw
                    if isinstance(raw, str):
                        try:
                            parsed = json.loads(raw)
                            if isinstance(parsed, dict):
                                return parsed
                        except (json.JSONDecodeError, ValueError):
                            pass
                    return {}

                def _extract_step_message(step):
                    """Build a human-readable message from a CrewAI step."""
                    step_type = type(step).__name__

                    # ToolResult — show a brief summary of what came back
                    if step_type == "ToolResult":
                        result = getattr(step, 'result', '') or ''
                        if "results" in result:
                            return None  # Skip raw results; the next AgentAction will summarize
                        if "Error" in result or "error" in result:
                            return f"Tool returned an error, retrying with a different approach..."
                        return None  # Skip other raw results

                    # AgentAction — the interesting one
                    tool = getattr(step, 'tool', None)
                    raw_input = getattr(step, 'tool_input', None)
                    thought = getattr(step, 'thought', '') or ''
                    inputs = _parse_tool_input(raw_input)

                    # Clean up thought — extract just the reasoning
                    thought_text = ""
                    for line in thought.split('\n'):
                        stripped = line.strip().lstrip('-').strip()
                        if stripped.lower().startswith('thought:'):
                            thought_text = stripped[len('thought:'):].strip()
                            break

                    if tool == "search_products" or tool == "find_similar_items":
                        query = inputs.get("query", "")
                        if query:
                            msg = f"Searching the product catalog for \"**{query}**\""
                        else:
                            msg = "Searching the product catalog"
                        if thought_text:
                            return f"{thought_text}\n{msg}..."
                        return f"{msg}..."
                    elif tool == "check_budget":
                        amount = inputs.get("amount")
                        if amount is not None:
                            return f"Checking if **${amount}** is within budget..."
                        return "Validating the purchase against budget..."
                    elif tool == "create_purchase_order":
                        pid = inputs.get("product_id", "")
                        qty = inputs.get("quantity", "")
                        if pid and qty:
                            return f"Placing purchase order for **{pid}** × {qty} units..."
                        return "Placing the purchase order..."
                    elif tool:
                        return f"Using {tool}..."

                    # No tool — show the thought if available
                    if thought_text:
                        return thought_text
                    return None

                def crew_step_callback(step):
                    msg = _extract_step_message(step)
                    if msg:
                        schedule_execution_update(msg)

                # Sync callback for CrewAI init status (runs in worker thread)
                def crew_status_callback(msg: str):
                    schedule_execution_update(msg)

                # Use asyncio.to_thread to keep the event loop alive while CrewAI runs
                result = await asyncio.to_thread(
                    crew.run,
                    task_description=task_description,
                    budget=budget,
                    quantity=quantity,
                    step_callback=crew_step_callback,
                    status_callback=crew_status_callback,
                )

            await publish_execution_update("Agent team completed sourcing and procurement.")

            # Clean up handler
            logging.getLogger("crewai").removeHandler(thought_handler)

            return {
                "current_step": "executed",
                "delegation_status": "success",
                "execution_result": str(result)
            }

        except Exception as e:
            logger.error(f"Execution Swarm failed: {e}")
            await publish_execution_update(f"Agent team encountered an error: {str(e)}")
            logging.getLogger("crewai").removeHandler(thought_handler)
            return {
                "current_step": "executed",
                "delegation_status": "failed",
                "execution_result": f"Error: {str(e)}"
            }

    async def attempt_forbidden_action(self, state: PlanState) -> PlanState:
        """CUJ 2 Node: Attempt a forbidden vector store operation."""
        logger.info("--- [Planner] SECURITY: Attempting forbidden action (delete_index) ---")
        _push_to_dashboard("Checking IAM permissions for the requested action...", "system")
        if self.on_update:
            await self.on_update("Checking IAM permissions for the requested action...")
            
        project = config.GOOGLE_CLOUD_PROJECT
        location = "us-central1"
        index_name = f"projects/{project}/locations/{location}/indexes/0000000000000000000"
        permission = "aiplatform.indexes.delete"

        try:
            if not self._has_project_permission(project, permission):
                return {
                    "current_step": "security_check",
                    "security_violation": (
                        "Blocked by Identity Shield: "
                        f"Missing IAM permission {permission}"
                    ),
                }

            client = aiplatform_v1.IndexServiceClient(
                client_options={"api_endpoint": f"{location}-aiplatform.googleapis.com"}
            )
            client.delete_index(name=index_name)
            return {
                "current_step": "security_check",
                "security_violation": "WARNING: delete_index succeeded — service account has excessive permissions!",
            }
        except (PermissionDenied, Forbidden) as e:
            logger.info(f"BLOCKED by IAM: {e}")
            if self.on_update:
                await self.on_update("Security: Identity Shield blocked the action!")
            return {
                "current_step": "security_check",
                "security_violation": f"Blocked by Identity Shield: {e}",
            }
        except Exception as e:
            logger.error(f"Unexpected error during security check: {e}")
            return {
                "current_step": "security_check",
                "security_violation": f"Blocked: {e}",
            }

    async def generate_security_report(self, state: PlanState) -> PlanState:
        """CUJ 2 Node: Generate a security incident report after IAM rejection."""
        logger.info("--- [Planner] SECURITY: Generating Security Report ---")
        _push_to_dashboard("Generating the security incident report...", "system")
        if self.on_update:
            await self.on_update("Generating the security incident report...")

        prompt = SECURITY_REPORT_PROMPT.format(
            objective=state.get("objective", "Unknown"),
            security_violation=state.get("security_violation", "Unknown violation"),
        )

        response = self.llm.invoke(prompt)

        return {
            "current_step": "completed",
            "final_report": str(response.content),
        }

    async def generate_report(self, state: PlanState) -> PlanState:
        """Node 3: Synthesize the final outcome."""
        logger.info("--- [Planner] Step 3: Generating Final Report ---")
        _push_to_dashboard("Generating the final procurement report...", "system")
        if self.on_update:
            await self.on_update("Generating the final procurement report...")
        
        prompt = REPORT_GENERATOR_PROMPT.format(
            objective=state.get("objective", "Unknown Objective"),
            execution_result=state.get("execution_result", "No result returned.")
        )
        
        response = self.llm.invoke(prompt)
        
        return {
            "current_step": "completed",
            "final_report": str(response.content)
        }

def route_after_analysis(state: PlanState) -> str:
    """CUJ 2: Route destructive requests to the security path."""
    if state.get("malicious_intent"):
        return "attempt_forbidden_action"
    return "delegate"


# Graph Construction
def build_planner_graph(crew_engine=None, on_update=None):
    nodes = PlannerNodes(crew_engine=crew_engine, on_update=on_update)
    workflow = StateGraph(PlanState)

    # Add Nodes
    workflow.add_node("analyze_alert", nodes.analyze_alert)
    workflow.add_node("delegate", nodes.delegate_to_executor)
    workflow.add_node("generate_report", nodes.generate_report)
    workflow.add_node("attempt_forbidden_action", nodes.attempt_forbidden_action)
    workflow.add_node("generate_security_report", nodes.generate_security_report)

    # Conditional routing after analysis (CUJ 2: Identity Shield)
    workflow.set_entry_point("analyze_alert")
    workflow.add_conditional_edges(
        "analyze_alert",
        route_after_analysis,
        {
            "delegate": "delegate",
            "attempt_forbidden_action": "attempt_forbidden_action",
        },
    )

    # Normal path (CUJ 1 / CUJ 3)
    workflow.add_edge("delegate", "generate_report")
    workflow.add_edge("generate_report", END)

    # Security path (CUJ 2)
    workflow.add_edge("attempt_forbidden_action", "generate_security_report")
    workflow.add_edge("generate_security_report", END)

    # Compile the graph
    return workflow.compile()

# Example Usage
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    
    graph = build_planner_graph()
    
    initial_state: PlanState = {
        "objective": "Inventory Alert: Northeast Region is critically low on 'Rare Japanese Anime Figure'. Please order 2 units ASAP. Max budget $50 per unit."
    }
    
    print("==================================================")
    print("🚀 STARTING LANGGRAPH PLANNER")
    print("==================================================")
    
    final_state = None
    for s in graph.stream(initial_state):
        print(s)
        final_state = s
        
    print("\n==================================================")
    print("🏁 FINAL OUTPUT FROM DASHBOARD:")
    print("==================================================")
    
    if final_state and "generate_report" in final_state:
        print(final_state["generate_report"]["final_report"])
    else:
        print("Execution did not reach the report generation stage.")
