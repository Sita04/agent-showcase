from typing import Any, Dict

def render_plan_ui(plan: Dict[str, Any]) -> Dict[str, Any]:
    """
    Renders a ShoppingPlan into A2UI JSON format.
    The first card is the summary/reasoning (rendered as a banner).
    Subsequent cards are the components.
    """
    cards = []
    
    # Summary Card (Banner)
    cards.append({
        "Card": {
            "children": [
                {"Text": {"text": f"{plan.get('theme', 'Custom Plan')}", "style": "title"}},
                {"Text": {"text": f"{plan.get('reasoning', 'Tailored for your request.')}", "style": "subtitle"}}
            ]
        }
    })
    
    # Component Cards
    for component in plan.get("components", []):
        budget = component.get('budget_allocation', '0')
        desc = component.get('description_prompt', '')
        cards.append({
            "Card": {
                "children": [
                    {"Text": {"text": f"📦 {component.get('category')}", "style": "title"}},
                    {"Text": {"text": f"${budget} - {desc}", "style": "subtitle"}}
                ]
            }
        })
        
    return {
        "beginRendering": {
            "surfaceId": "proposed-plan",
            "content": {
                "Column": {
                    "children": cards
                }
            }
        }
    }
