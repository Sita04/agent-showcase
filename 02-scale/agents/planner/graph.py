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
    from config.prompts import PLANNER_SYSTEM_PROMPT, REPORT_GENERATOR_PROMPT, SECURITY_REPORT_PROMPT
    from config.default_config import config
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PlannerAgent")

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
        if self.on_update:
            await self.on_update("Planner: Analyzing incoming alert...")
        
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

        # Internal helper to push to dashboard
        def push_to_dashboard(msg: str, name: str = "execution"):
            try:
                import requests
                # Use synchronous requests here since we are in a node or thread
                requests.post(
                    "http://127.0.0.1:8000/api/push_status", 
                    data={"name": name, "text": msg},
                    timeout=1.0
                )
            except Exception:
                pass 

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
                        push_to_dashboard(clean_msg)
                except Exception:
                    pass

        thought_handler = DashboardCallbackHandler()
        thought_handler.setLevel(logging.INFO)
        # Attach to both crewai and the root logger during execution
        logging.getLogger("crewai").addHandler(thought_handler)

        if self.on_update:
            await self.on_update(f"Executor: Starting CrewAI for '{task_description}'...")
        
        push_to_dashboard(f"Starting CrewAI for '{task_description}'...")

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
                def crew_step_callback(step):
                    agent_role = "Agent"
                    if hasattr(step, 'agent'):
                        agent_role = getattr(step.agent, 'role', 'Agent')
                    
                    # Capture specific tool usage if available
                    tool_msg = ""
                    if hasattr(step, 'tool'):
                        tool_msg = f" using {step.tool}"
                    
                    msg = f"**{agent_role}**: Finished a step{tool_msg}."
                    push_to_dashboard(msg)

                # Use asyncio.to_thread to keep the event loop alive while CrewAI runs
                import asyncio
                result = await asyncio.to_thread(
                    crew.run,
                    task_description=task_description,
                    budget=budget,
                    quantity=quantity,
                    step_callback=crew_step_callback
                )

            if self.on_update:
                await self.on_update("Executor: CrewAI task completed.")
            
            push_to_dashboard("CrewAI task completed successfully.")

            # Clean up handler
            logging.getLogger("crewai").removeHandler(thought_handler)

            return {
                "current_step": "executed",
                "delegation_status": "success",
                "execution_result": str(result)
            }

        except Exception as e:
            logger.error(f"Execution Swarm failed: {e}")
            if self.on_update:
                await self.on_update(f"Executor: Failed with error: {str(e)}")
            return {
                "current_step": "executed",
                "delegation_status": "failed",
                "execution_result": f"Error: {str(e)}"
            }

    async def attempt_forbidden_action(self, state: PlanState) -> PlanState:
        """CUJ 2 Node: Attempt a forbidden vector store operation."""
        logger.info("--- [Planner] SECURITY: Attempting forbidden action (delete_index) ---")
        if self.on_update:
            await self.on_update("Security: Checking permissions for destructive action...")
            
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
        if self.on_update:
            await self.on_update("Planner: Synthesizing security incident report...")

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
        if self.on_update:
            await self.on_update("Planner: Synthesizing final procurement report...")
        
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
