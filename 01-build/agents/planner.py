"""
Planner Agent for the Shopping Squad.
Responsible for decomposing vague user requests into structured shopping plans
with specific budget allocations and thematic guidance.
"""

from google.adk.agents import Agent
from agents.schemas import ShoppingPlan

def create_planner_agent(name="shopping_planner_node"):
    return Agent(
        name=name,
        model="gemini-2.5-flash",
        output_schema=ShoppingPlan,
        output_key="shopping_plan",
        instruction="""
        You are a specialized JSON generator for the Shopping Squad.
        
        TASK: Convert the user's request into a ShoppingPlan object.
        
        CONSTRAINTS:
        - Return ONLY raw JSON. 
        - DO NOT use markdown code blocks (no ```json).
        - DO NOT include any text before or after the JSON.
        - Sum of budget_allocation must be <= total_budget.
        
        RESPONSE FORMAT: JSON only.
        """
    )
