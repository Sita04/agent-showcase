"""
Main Orchestrator for the Shopping Squad.
Coordinates the Planner, parallel Scouts, and Evaluator.
"""

import asyncio
import uuid
import re
import json

from google.adk.workflow import Workflow, node 
from google.adk import Context
from google.adk.agents.llm_agent import LlmAgent

# Import local modules using absolute package paths
from agents.planner import create_planner_agent 
from agents.scout import create_scout_agent
from agents.evaluator import shopping_evaluator
from agents.schemas import CartItem, EvaluationReport, ShoppingPlan, CartItemOptions

async def _speak(ctx: Context, text: str, name_hash: str):
    """
    Helper function to bypass ADK's native UI rendering quirks.
    By piping strings through a dedicated presentation LlmAgent, 
    we force the Frontend to render our custom feedback as a fully realized
    markdown Chat Bubble instead of a minimal 'trace' box.
    """
    speaker = LlmAgent(
        name=f"sys_speaker_{name_hash}",
        model="gemini-2.5-flash",
        instruction=(
            "You are a system presentation agent. Your ONLY job is to present the exact markdown text provided below. "
            "You MUST ignore all previous conversation history and context that may have been passed to you. "
            f"Do not add any conversational filler. Output the following verbatim:\n\n{text}"
        )
    )
    # Trigger the agent with a generic wake word so it evaluates cleanly
    await ctx.run_node(speaker, "Present the text dictated in your system instruction.") 

def _parse_plan_from_state(ctx: Context, original_plan) -> ShoppingPlan | None:
    if original_plan is not None:
        return original_plan
        
    print("DEBUG: plan was None, falling back to ctx.state")
    plan_data = ctx.state.get("shopping_plan")
    if plan_data:
        try:
            if isinstance(plan_data, dict):
                return ShoppingPlan.model_validate(plan_data)
            else:
                return ShoppingPlan.model_validate_json(plan_data)
        except Exception as e:
            print(f"❌ Failed to parse plan from state: {e}")
            
    return None



@node(rerun_on_resume=True)
async def shopping_workflow(ctx: Context, node_input: str):
    max_attempts = 2
    attempt = 0
    run_id = uuid.uuid4().hex[:6]
    attempt_history = []
    
    # ----------------------------------------------------
    # HITL STATE MACHINE: Final Selection Phase
    # ----------------------------------------------------
    if ctx.state.get("awaiting_selection"):
        options = ctx.state.get("found_options", [])
        selection_agent = LlmAgent(
            name=f"selection_agent_{run_id}_{uuid.uuid4().hex[:4]}",
            model="gemini-2.5-flash",
            instruction=f"""
            The user is finalizing their shopping cart based on the options we just found:
            {options}
            
            Match the user's natural language choices to the specific items from the provided list.
            If they are vague (e.g., 'the green one' or 'the first tent'), politely deduce the correct item.
            
            OUTPUT INSTRUCTIONS:
            Create a final, extremely friendly Order Confirmation in Markdown!
            - Express excitement for their purchases.
            - List exactly which chosen items are going into their cart, their final prices, and a 1-sentence description.
            - Calculate the final total cost and show it in bold at the bottom!
            """
        )
        await ctx.run_node(selection_agent, node_input)
        ctx.state["awaiting_selection"] = False
        return {"status": "Completed! End of Shopping Workflow."}

    # ----------------------------------------------------
    # HITL STATE MACHINE: Budget Approval Phase
    # ----------------------------------------------------
    if ctx.state.get("awaiting_approval"):
        user_reply = node_input.lower().strip()
        # Accept a much broader set of positive affirmations
        positive_affirmations = ["yes", "y", "sure", "ok", "okay", "approve", "approved", "looks good", "proceed", "go ahead"]
        if any(word in user_reply for word in positive_affirmations):
            # User approved! Clear flag and load the plan to proceed to scouts
            ctx.state["awaiting_approval"] = False
            plan = _parse_plan_from_state(ctx, None)
            if not plan: return "Failed to retrieve approved plan from memory."
        else:
            # User rejected or provided feedback! Generate a new plan.
            ctx.state["awaiting_approval"] = False
            dynamic_planner = create_planner_agent(name=f"planner_user_ref__{run_id}")
            plan = await ctx.run_node(dynamic_planner, f"User rejected plan with feedback: {node_input}. Update it.")
            plan = _parse_plan_from_state(ctx, plan)
            ctx.state["awaiting_approval"] = True
            
            plan_dict = plan.model_dump() if hasattr(plan, 'model_dump') else plan
            components_md = "\n".join([f"- **{c.get('category')}**: ${c.get('budget_allocation')} ({c.get('description_prompt')})" for c in plan_dict.get('components', [])])
            
            msg = (
                f"### Updated Plan: {plan_dict.get('theme', 'Custom')}\n\n"
                f"**Total Budget:** ${plan_dict.get('total_budget', 0)}\n\n"
                f"**Allocations:**\n{components_md}\n\n"
                f"👉 *I've updated the plan based on your feedback! Do you approve? Reply 'Yes' to begin the search!*"
            )
            await _speak(ctx, msg, f"update_{run_id}_{uuid.uuid4().hex[:4]}")
            return {"status": "Awaiting human approval"}
    else:
        # First time running! Generate the initial plan.
        dynamic_planner = create_planner_agent(name=f"planner_initial_{run_id}")
        plan = await ctx.run_node(dynamic_planner, node_input)
        plan = _parse_plan_from_state(ctx, plan)
        if plan is None:
            return "Planner failed to initialize."
        
        ctx.state["awaiting_approval"] = True
        
        plan_dict = plan.model_dump() if hasattr(plan, 'model_dump') else plan
        components_md = "\n".join([f"- **{c.get('category')}**: ${c.get('budget_allocation')} ({c.get('description_prompt')})" for c in plan_dict.get('components', [])])
        
        msg = (
            f"### Proposed Blueprint: {plan_dict.get('theme', 'Custom')}\n\n"
            f"**Total Budget:** ${plan_dict.get('total_budget', 0)}\n\n"
            f"**Allocations:**\n{components_md}\n\n"
            f"👉 *Do you approve of this budget and breakdown? Reply 'Yes' to proceed, or suggest adjustments!*"
        )
        await _speak(ctx, msg, f"init_{run_id}_{uuid.uuid4().hex[:4]}")
        return {"status": "Awaiting human approval"}

    while attempt < max_attempts:
        attempt += 1
        
        scout_tasks = []
        # Since we use a schema, we use dot notation: plan.components
        for i, component in enumerate(plan.components): 
            query_string = f"{component.category} {component.description_prompt}"
            budget_val = component.budget_allocation
            
            # Instantiate a uniquely configured agent with baked-in prompt instructions
            # We include `attempt` and `run_id` in the name so loops and reruns don't collide!
            unique_name = f"product_scout_node_{run_id}_loop{attempt}_idx{i}"
            dynamic_scout = create_scout_agent(query=query_string, budget=budget_val, name=unique_name)
            
            # Since all context is now in the prompt, pass a simple wake word message
            task = ctx.run_node(dynamic_scout, "Execute search.")
            scout_tasks.append(task)
        
        # Run all scouts in parallel
        raw_items = await asyncio.gather(*scout_tasks)
        
        # ADK 2.0 Alpha bug: Pydantic outputs from LlmAgents are often suppressed in the return value 
        # and dumped directly into ctx.state under the node's name. We must fetch them!
        found_items = []
        for i, item in enumerate(raw_items):
            if item is None:
                scout_key = f"product_scout_node_{run_id}_loop{attempt}_idx{i}"
                item = ctx.state.get(scout_key)
                
            # If the Scout returned our beautiful conversational text, extract the hidden JSON!
            if isinstance(item, str):
                import re, json
                match = re.search(r'<!--\s*\[JSON_PAYLOAD\]\s*(.*?)\s*\[/JSON_PAYLOAD\]\s*-->', item, re.DOTALL | re.IGNORECASE)
                if match:
                    try:
                        parsed = json.loads(match.group(1))
                        item = CartItemOptions(**parsed)
                    except Exception as e:
                        print(f"DEBUG: Failed to parse scout xml json data: {e}")
            elif isinstance(item, dict):
                item = CartItemOptions(**item)
                
            found_items.append(item)
        
        # Call the final evaluator (passing items and plan as a dict positionally)
        report = await ctx.run_node(
            shopping_evaluator, 
            {"items": found_items, "plan": plan}
        )
        # ADK Function Nodes serialize Pydantic returns into dictionaries
        is_valid = report.get("is_valid") if isinstance(report, dict) else report.is_valid
        
        # Record the outcome of this iteration
        attempt_history.append({
            "attempt": attempt,
            "plan": plan.model_dump() if hasattr(plan, 'model_dump') else plan,
            "items_found": found_items,
            "feedback": report.get("feedback") if isinstance(report, dict) else getattr(report, "feedback", ""),
            "is_valid": is_valid
        })
        
        if is_valid:
            ctx.state["found_options"] = [i.model_dump() if hasattr(i, 'model_dump') else i for i in found_items]
            ctx.state["awaiting_selection"] = True
            
            msg = (
                f"🎉 **Search Complete!**\n\n"
                f"I've verified that the lowest-priced combination easily fits your master budget.\n\n"
                f"Please review the options in the chat above and respond with your final choices for your cart (e.g. *'I'll take the first tent, and the MOON LENCE bag'*)."
            )
            await _speak(ctx, msg, f"success_{run_id}_{attempt}")
            return {"status": "Awaiting human selection"}
        
        # If refinement is needed, the loop continues
        feedback = report.get("feedback") if isinstance(report, dict) else report.feedback
        refinement_planner = create_planner_agent(name=f"planner_refinement_{run_id}_{attempt}")
        plan = await ctx.run_node(refinement_planner, str(feedback))
        plan = _parse_plan_from_state(ctx, plan)
        if plan is None:
            return "Planner refinement failed."

    return {
        "status": f"Failed after {max_attempts} attempts",
        "history": attempt_history
    }


# --- WORKFLOW ENTRY POINT ---

root_agent = Workflow(
    name="shopping_squad_root",
    edges=[("START", shopping_workflow)], # Workflow starts here
)