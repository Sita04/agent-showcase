"""
Main Orchestrator for the Shopping Squad.
Coordinates the Planner, parallel Scouts, and Evaluator.
"""

import asyncio
import uuid
import re
import json
import os
import stripe

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

from google.adk.workflow import Workflow, node 
from google.adk import Context
from google.adk.agents.llm_agent import LlmAgent

# Import local modules using absolute package paths
from agents.planner import create_planner_agent 
from agents.scout import create_scout_agent
from agents.evaluator import shopping_evaluator
from agents.schemas import CartItem, EvaluationReport, ShoppingPlan, CartItemOptions
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
import os

# Global cart for demo purposes to avoid state persistence issues
GLOBAL_CART = []


def _extract_text(input_val):
    if isinstance(input_val, str):
        return input_val
    if hasattr(input_val, "parts"):
        return "".join([p.text for p in input_val.parts if hasattr(p, "text") and p.text])
    return str(input_val)

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
            "SYSTEM RULE: You are a pure text pipe. Output the EXACT text provided below verbatim. "
            "Do NOT introduce yourself, do NOT output your internal name, and do NOT add any conversational filler. "
            f"Output ALL of this text and ONLY this text:\n\n{text}"
        )
    )
    # Trigger the agent with a generic wake word so it evaluates cleanly
    await ctx.run_node(speaker, "Present the text dictated in your system instruction.") 

def _parse_plan_from_state(ctx: Context, original_plan) -> ShoppingPlan | None:
    # Always normalize to ShoppingPlan if possible
    plan_to_check = original_plan if original_plan is not None else ctx.state.get("shopping_plan")
    
    if plan_to_check:
        try:
            if isinstance(plan_to_check, ShoppingPlan):
                return plan_to_check
            elif isinstance(plan_to_check, dict):
                return ShoppingPlan.model_validate(plan_to_check)
            else:
                return ShoppingPlan.model_validate_json(str(plan_to_check))
        except Exception as e:
            print(f"❌ Failed to parse plan: {e}")
            
    return None



@node(rerun_on_resume=True)
async def shopping_workflow(ctx: Context, node_input):
    print(f"DEBUG: shopping_workflow entered with node_input: {node_input}")
    print(f"DEBUG: current awaiting_selection state: {ctx.state.get('awaiting_selection')}")
    max_attempts = 2
    attempt = 0
    run_id = uuid.uuid4().hex[:6]
    attempt_history = []
    
    # ----------------------------------------------------
    # HITL STATE MACHINE: Final Selection Phase
    # ----------------------------------------------------
    if ctx.state.get("awaiting_selection"):
        options = ctx.state.get("found_options", [])
        
        def add_to_agent_cart(sku: str, name: str, price: float, img_url: str = ""):
            """Add an item to the agent's cart state. Call this when the user selects an item to purchase."""
            global GLOBAL_CART
            if not any(item['sku'] == sku for item in GLOBAL_CART):
                GLOBAL_CART.append({"sku": sku, "name": name, "price": price, "img_url": img_url})
                ctx.state["agent_cart"] = GLOBAL_CART
                return f"Added {name} to your order."
            return f"{name} is already in your order."
            
        def remove_from_agent_cart(sku: str):
            """Remove an item from the agent's cart state. Call this when the user unselects an item."""
            global GLOBAL_CART
            initial_len = len(GLOBAL_CART)
            GLOBAL_CART = [item for item in GLOBAL_CART if item['sku'] != sku]
            ctx.state["agent_cart"] = GLOBAL_CART
            if len(GLOBAL_CART) < initial_len:
                return "Removed from your order."
            return "Item not found in your order."
            
        def finalize_order():
            """Call this after you have generated the payment link and are done with the session."""
            ctx.state["awaiting_selection"] = False
            return "Order finalized."
            
        def create_checkout_link() -> str:
            """Creates a real Stripe checkout link for the items in the cart. Call this when the user wants to checkout."""
            global GLOBAL_CART
            if not GLOBAL_CART:
                return "Cart is empty!"
                
            line_items = []
            for item in GLOBAL_CART:
                line_items.append({
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": item["name"],
                        },
                        "unit_amount": int(item["price"] * 100),
                    },
                    "quantity": 1,
                })
                
            try:
                origin = "http://localhost:8080"
                session = stripe.checkout.Session.create(
                    payment_method_types=["card"],
                    line_items=line_items,
                    mode="payment",
                    success_url=f"{origin}/?success=true",
                    cancel_url=f"{origin}/?canceled=true",
                )
                return f"Here is your payment link: {session.url}"
            except Exception as e:
                return f"Error creating payment link: {str(e)}"

        cart_items = GLOBAL_CART
        print(f"DEBUG: Current Cart in prompt: {cart_items}")
        
        selection_agent = LlmAgent(
            name=f"sys_speaker_selection_{run_id}_{uuid.uuid4().hex[:4]}",
            model="gemini-2.5-flash",
            instruction=f"""
            The user is building their shopping cart by selecting items from the options we just found:
            {options}
            
            Current Cart: {cart_items}
            
            Match the user's request to the specific items from the provided options list. The user message will typically include the item name and its SKU (e.g., SKU: ...). Use the SKU to reliably identify the item in the options list.
            
            INSTRUCTIONS:
            1. If the user wants to ADD an item, call `add_to_agent_cart` (be sure to pass the `img_url` from the options list if available!).
            2. If the user wants to REMOVE an item, call `remove_from_agent_cart`.
            3. If the user wants to CHECKOUT, call `create_checkout_link` to generate a real Stripe payment link for the items in the cart. Then call `finalize_order`!
            4. If they ask what's in their cart, list the items in the current cart.
            
            OUTPUT INSTRUCTIONS:
            Create an extremely friendly response in Markdown!
            - If adding an item, confirm it was added.
            - If removing an item, confirm it was removed.
            - If checking out, include the payment link returned by `create_checkout_link` in your response!
            - Do NOT list the available options again. Just confirm the action and ask what else they would like to do.
            """,
            tools=[
                add_to_agent_cart,
                remove_from_agent_cart,
                finalize_order,
                create_checkout_link
            ]
        )
        await ctx.run_node(selection_agent, node_input)
        
        # Only complete the workflow if finalize_order was called (which sets awaiting_selection to False)
        if not ctx.state.get("awaiting_selection"):
            return {"status": "Completed! End of Shopping Workflow."}
        else:
            return {"status": "Awaiting more selections"}

    # ----------------------------------------------------
    # HITL STATE MACHINE: Budget Approval Phase
    # ----------------------------------------------------
    if ctx.state.get("awaiting_approval"):
        user_reply = _extract_text(node_input).lower().strip()
        # Accept a much broader set of positive affirmations
        positive_affirmations = ["yes", "y", "sure", "ok", "okay", "approve", "approved", "looks good", "proceed", "go ahead"]
        
        import re
        if any(re.search(rf"\b{word}\b", user_reply) for word in positive_affirmations):
            # User approved! Clear flag and load the plan to proceed to scouts
            ctx.state["awaiting_approval"] = False
            plan = _parse_plan_from_state(ctx, None)
            if not plan: return "Failed to retrieve approved plan from memory."
        else:
            # User rejected or provided feedback! Generate a new plan.
            ctx.state["awaiting_approval"] = False
            dynamic_planner = create_planner_agent(name=f"planner_user_ref__{run_id}")
            plan = await ctx.run_node(dynamic_planner, f"User rejected plan with feedback: {_extract_text(node_input)}. Update it.")
            plan = _parse_plan_from_state(ctx, plan)
            ctx.state["awaiting_approval"] = True
            
            plan_dict = plan.model_dump() if hasattr(plan, 'model_dump') else plan
            
            # Update A2UI in state so the UI cards match the new plan!
            from agents.views.plan import render_plan_ui
            ctx.state["proposed_plan_ui"] = render_plan_ui(plan_dict)
            
            components_md = "\n".join([f"- **{c.get('category')}**: ${c.get('budget_allocation')} ({c.get('description_prompt')})" for c in plan_dict.get('components', [])])
            
            msg = (
                f"### Updated Plan: {plan_dict.get('theme', 'Custom')}\n\n"
                f"**Total Budget:** ${plan_dict.get('total_budget', 0)}\n\n"
                f"**Allocations:**\n{components_md}\n\n"
                f"👉 I've updated the plan based on your feedback! Do you approve? Reply 'Yes' to begin the search!"
            )
            await _speak(ctx, msg, f"update_{run_id}_{uuid.uuid4().hex[:4]}")
            return {"status": "Awaiting human approval"}
    else:
        # First time running! Generate the initial plan.
        input_text = _extract_text(node_input)
        print(f"DEBUG: input_text for planner check = '{input_text}'")
        if "similar to" in input_text.lower() or "find_similar_items" in input_text.lower():
            from agents.schemas import ShoppingComponent
            import re
            
            # Try to extract budget
            budget_match = re.search(r'\$(\d+)', input_text)
            budget = float(budget_match.group(1)) if budget_match else 150.0
            
            plan = ShoppingPlan(
                theme="Similar Items Search",
                total_budget=budget,
                components=[
                    ShoppingComponent(
                        category="Items",
                        budget_allocation=budget,
                        description_prompt=input_text
                    )
                ],
                reasoning="Search for similar items based on user request."
            )
            ctx.state["proposed_plan"] = plan
            ctx.state["awaiting_approval"] = False
        else:
            dynamic_planner = create_planner_agent(name=f"planner_initial_{run_id}")
            plan = await ctx.run_node(dynamic_planner, node_input)
            plan = _parse_plan_from_state(ctx, plan)
            if plan is None:
                return "Planner failed to initialize."
            
            ctx.state["awaiting_approval"] = True
            
            from agents.views.plan import render_plan_ui
            plan_dict = plan.model_dump() if hasattr(plan, 'model_dump') else plan
            ctx.state["proposed_plan_ui"] = render_plan_ui(plan_dict)
            
            msg = "👉 Here's a blueprint tailored for your request. Ready to proceed?"
            await _speak(ctx, msg, f"init_{run_id}_{uuid.uuid4().hex[:4]}")
            return {"status": "Awaiting human approval"}

    while attempt < max_attempts:
        attempt += 1
        
        scout_tasks = []
        # Since we use a schema, we use dot notation: plan.components
        for i, component in enumerate(plan.components): 
            query_string = component.description_prompt
            if plan.theme and ("Daily Bicycle Commute" in plan.theme or "Bicycle" in plan.theme):
                query_string = "bicycle accessories for men"
            budget_val = component.budget_allocation
            
            # Instantiate a uniquely configured agent with baked-in prompt instructions
            # We include `attempt` and `run_id` in the name so loops and reruns don't collide!
            unique_name = f"product_scout_node_{run_id}_loop{attempt}_idx{i}"
            dynamic_scout = create_scout_agent(category=component.category, query=query_string, budget=budget_val, name=unique_name)
            
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
                f"Please review the options in the chat above and respond with your final choices for your cart (e.g. 'I'll take the first tent, and the MOON LENCE bag')."
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