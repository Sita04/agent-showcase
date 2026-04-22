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

"""Agent Engine wrapper for the CrewAI Logistics Execution Crew.

Exposes the crew as a custom agent deployable to Agent Engine via
`client.agent_engines.create(agent=ExecutionCrewAgent(...))`.
"""

import json
import logging
import re

logger = logging.getLogger(__name__)


_MERCARI_ID_RE = re.compile(r"\bm\d{8,}\b")


def _extract_products_from_text(text: str, max_items: int = 8) -> list[dict]:
    """Same heuristic as the planner's local step callback: walk JSON for
    product-shaped objects, fall back to Mercari id regex (id-only). Kept
    inline so this module stays standalone for Agent Engine deploys."""
    if not text:
        return []
    products: list[dict] = []

    def _to_product(node: dict) -> dict | None:
        pid = node.get("id") or node.get("product_id")
        if not isinstance(pid, str) or not pid:
            return None
        return {
            "id": pid,
            "name": node.get("name") or node.get("title") or "",
            "price": node.get("price"),
            "description": (
                node.get("description")
                or node.get("desc")
                or node.get("summary")
                or ""
            ),
        }

    def _walk(node):
        if isinstance(node, dict):
            entry = _to_product(node)
            if entry:
                products.append(entry)
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    try:
        _walk(json.loads(text))
    except (json.JSONDecodeError, ValueError, TypeError):
        pass

    if not products:
        for pid in _MERCARI_ID_RE.findall(text):
            products.append({"id": pid, "name": "", "price": None, "description": ""})

    seen: set[str] = set()
    out: list[dict] = []
    for entry in products:
        pid = entry.get("id")
        if not pid or pid in seen:
            continue
        seen.add(pid)
        out.append(entry)
        if len(out) >= max_items:
            break
    return out


def _format_found_candidates_message(products: list[dict]) -> str:
    ids = [p["id"] for p in products]
    preview = ", ".join(f"`{i}`" for i in ids[:5])
    extra = "" if len(ids) <= 5 else f" (+{len(ids) - 5} more)"
    return (
        f"Found {len(ids)} candidate(s): {preview}{extra}\n"
        f"<!--PRODUCTS:{json.dumps(products)}-->"
    )


class ExecutionCrewAgent:
    """Agent Engine-compatible wrapper for LogisticsExecutionCrew."""

    def __init__(self, project_id: str = "", region: str = "us-central1"):
        # Only pickle-safe config here
        self.project_id = project_id
        self.region = region

    def set_up(self):
        """Initialize environment and import the crew class."""
        import os
        if not self.project_id:
            self.project_id = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", self.project_id)
        os.environ.setdefault("OPENAI_API_KEY", "NA")
        os.environ.setdefault("VERTEXAI_PROJECT", self.project_id)
        os.environ.setdefault("VERTEXAI_LOCATION", "global")

        try:
            from .src.crew import LogisticsExecutionCrew
        except ImportError:
            from src.crew import LogisticsExecutionCrew
        self._crew_class = LogisticsExecutionCrew

    def query(self, *, input: str) -> str:
        """Run the crew with JSON-encoded parameters.

        Args:
            input: JSON string with keys: task_description, budget, quantity.

        Returns:
            Crew execution result as a string.
        """
        import os
        import requests

        status_url = os.environ.get("CONTROL_ROOM_STATUS_URL", "")

        # The planner forwards the dashboard tab's session_id in the input
        # envelope so every push from the crew routes to the right per-tab
        # queue. Without this, the dashboard's per-session router drops
        # executor bubbles into the unrouted "" key.
        params = json.loads(input)
        session_id = str(params.get("session_id", "") or "")

        def _push(msg: str, name: str = "execution", role: str = "executor"):
            if status_url:
                try:
                    requests.post(
                        status_url,
                        data={
                            "name": name,
                            "text": msg,
                            "role": role,
                            "session_id": session_id,
                        },
                        timeout=5,
                    )
                except Exception:
                    pass

        def _status_callback(msg: str):
            _push(msg)

        def _step_callback(step):
            """Translate CrewAI step objects into human-readable messages."""
            step_type = type(step).__name__
            if step_type == "ToolResult":
                raw_result = getattr(step, "result", "") or ""
                products = _extract_products_from_text(raw_result)
                if products:
                    _push(_format_found_candidates_message(products))
                return  # Skip non-product ToolResult content
            tool = getattr(step, "tool", None)
            raw_input = getattr(step, "tool_input", None)
            inputs = {}
            if isinstance(raw_input, dict):
                inputs = raw_input
            elif isinstance(raw_input, str):
                try:
                    parsed = json.loads(raw_input)
                    if isinstance(parsed, dict):
                        inputs = parsed
                except (json.JSONDecodeError, ValueError):
                    pass

            if tool == "search_products" or tool == "find_similar_items":
                query = inputs.get("query", "")
                msg = f'Searching the product catalog for "{query}"...' if query else "Searching the product catalog..."
            elif tool == "check_budget":
                amount = inputs.get("amount")
                msg = f"Checking if ${amount} is within budget..." if amount else "Validating the purchase against budget..."
            elif tool == "create_purchase_order":
                pid = inputs.get("product_id", "")
                qty = inputs.get("quantity", "")
                msg = f"Placing purchase order for {pid} x {qty} units..." if pid else "Placing the purchase order..."
            elif tool:
                msg = f"Using {tool}..."
            else:
                return  # No tool, skip
            _push(msg)

        crew = self._crew_class()
        result = crew.run(
            task_description=params.get("task_description", "Unknown Item"),
            budget=float(params.get("budget", 50.0)),
            quantity=int(params.get("quantity", 1)),
            step_callback=_step_callback,
            status_callback=_status_callback,
        )
        return str(result)
