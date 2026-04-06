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
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from state import PlanState, AlertExtraction
from agents.config.prompts import PLANNER_SYSTEM_PROMPT, REPORT_GENERATOR_PROMPT
from agents.executor.src.crew import LogisticsExecutionCrew
from agents.config.default_config import config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PlannerAgent")

class PlannerNodes:
    def __init__(self):
        # We use the modern LangChain Google GenAI integration (replaces ChatVertexAI)
        self.llm = ChatGoogleGenerativeAI(
            model=config.PLANNING_MODEL.replace("vertex_ai/", ""), # Remove the crewai vertex prefix if present
            temperature=0,
        )
        # LLM bound to output our specific extraction schema
        self.structured_llm = self.llm.with_structured_output(AlertExtraction)
        
    def analyze_alert(self, state: PlanState) -> PlanState:
        """Node 1: Extract intent from the raw objective string."""
        logger.info("--- [Planner] Step 1: Analyzing Alert ---")
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
            "delegation_status": "pending"
        }

    def delegate_to_executor(self, state: PlanState) -> PlanState:
        """Node 2: The A2A Bridge. Call the CrewAI swarm."""
        logger.info("--- [Planner] Step 2: Delegating to Execution Swarm (CrewAI) ---")
        
        try:
            # Instantiate the sub-agent swarm
            crew = LogisticsExecutionCrew()
            
            # Execute the synchronous run
            result = crew.run(
                task_description=state.get("item_description") or "Unknown Item",
                budget=state.get("max_budget") or 50.0,
                quantity=state.get("quantity_needed") or 1
            )
            
            return {
                "current_step": "executed",
                "delegation_status": "success",
                "execution_result": str(result)
            }
            
        except Exception as e:
            logger.error(f"Execution Swarm failed: {e}")
            return {
                "current_step": "executed",
                "delegation_status": "failed",
                "execution_result": f"Error: {str(e)}"
            }

    def generate_report(self, state: PlanState) -> PlanState:
        """Node 3: Synthesize the final outcome."""
        logger.info("--- [Planner] Step 3: Generating Final Report ---")
        
        prompt = REPORT_GENERATOR_PROMPT.format(
            objective=state.get("objective", "Unknown Objective"),
            execution_result=state.get("execution_result", "No result returned.")
        )
        
        response = self.llm.invoke(prompt)
        
        return {
            "current_step": "completed",
            "final_report": str(response.content)
        }

# Graph Construction
def build_planner_graph():
    nodes = PlannerNodes()
    workflow = StateGraph(PlanState)

    # Add Nodes
    workflow.add_node("analyze_alert", nodes.analyze_alert)
    workflow.add_node("delegate", nodes.delegate_to_executor)
    workflow.add_node("generate_report", nodes.generate_report)

    # Add Edges (Strict linear flow for now)
    workflow.set_entry_point("analyze_alert")
    workflow.add_edge("analyze_alert", "delegate")
    workflow.add_edge("delegate", "generate_report")
    workflow.add_edge("generate_report", END)

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
