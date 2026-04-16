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

"""
Evaluator Agent for the Shopping Squad.
Acts as the gatekeeper to ensure items are under budget and exist.
"""

from google.adk import Context
from google.adk.workflow import node
from .schemas import EvaluationReport

@node(name="evaluator_node")
async def shopping_evaluator(ctx: Context, node_input: dict):
    """
    Evaluates found items against the plan's budget.
    """
    print("\n🕵️‍♂️ [Evaluator] Assessing found items against plan...")
    items = node_input.get("items", [])
    plan = node_input.get("plan")
    
    
    def get_price(i): return float(i.get("price", 0.0)) if isinstance(i, dict) else float(i.price)
    def get_name(i): return str(i.get("name", "Unknown Item")) if isinstance(i, dict) else str(i.name)
    def get_budget(c): return float(c.get("budget_allocation", 0.0)) if isinstance(c, dict) else float(c.budget_allocation)
    def get_category(c): return str(c.get("category", "Item")) if isinstance(c, dict) else str(c.category)
    def get_total_budget(p): return float(p.get("total_budget", 0.0)) if isinstance(p, dict) else float(p.total_budget)
    def get_components(p): return p.get("components", []) if isinstance(p, dict) else p.components
    def get_options(o): return o.get("options", []) if isinstance(o, dict) else getattr(o, "options", [])
    
    def get_cheapest_option(o):
        opts = get_options(o)
        if not opts: return None
        return min(opts, key=lambda x: get_price(x))
    
    # 1. Check for Scout Failures
    # An item might be None or a string error message if the LLM failed to return a proper structure.
    if any(item is None or isinstance(item, str) or not get_options(item) for item in items):
        return EvaluationReport(
            is_valid=False,
            total_cost=0.0,
            feedback="One or more categories failed to find options. Try broadening the search terms."
        )

    # 2. Strict Total Budget Math
    total_cost = sum(get_price(get_cheapest_option(item_opts)) for item_opts in items)
    is_budget_ok = total_cost <= get_total_budget(plan)
    
    feedback_notes = []
    if not is_budget_ok:
        feedback_notes.append(f"Total cost ${total_cost:.2f} exceeds total budget of ${get_total_budget(plan):.2f}")

    # 3. Component-level alignment checks (To guide planner, but not block if total is fine)
    # If the total budget IS okay, we don't strictly need to fail just because one item went slightly over its micro-allocation limits!
    for item_opts, component in zip(items, get_components(plan)):
        cheapest = get_cheapest_option(item_opts)
        p = get_price(cheapest)
        b = get_budget(component)
        if p > b and not is_budget_ok:
            feedback_notes.append(
                f"Even the cheapest '{get_name(cheapest)}' (${p:.2f}) is over the ${b:.2f} limit."
            )
            
    # 4. Final Report
    if is_budget_ok:
        return EvaluationReport(is_valid=True, total_cost=total_cost, feedback="")
    
    return EvaluationReport(
        is_valid=False, 
        total_cost=total_cost, 
        feedback=" | ".join(feedback_notes)
    )