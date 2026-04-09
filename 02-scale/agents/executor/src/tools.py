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

from contextlib import contextmanager

from crewai.tools import tool
from mcpadapt.core import MCPAdapt
from mcpadapt.crewai_adapter import CrewAIAdapter
try:
    from ...config.default_config import config
except ImportError:
    from config.default_config import config

VECTOR_SEARCH_MCP_URL = "https://ac-web2-761793285222.us-central1.run.app/mcp"

def get_mcp_server():
    """Create an MCPAdapt bridge connected to the Vector Search MCP server."""
    return MCPAdapt(
        {"url": VECTOR_SEARCH_MCP_URL, "transport": "streamable-http"},
        CrewAIAdapter(),
        connect_timeout=60,
    )

def get_mock_oms_mcp():
    """Yield in-process mock OMS tools for Agent Engine compatibility.

    The vector search MCP server remains remote and MCP-backed. The mock OMS is a
    tiny local fake, so keeping it in-process avoids Agent Engine subprocess /
    stdio MCP instability while preserving the same task semantics.
    """

    @tool("check_budget")
    def check_budget(amount: float, category: str) -> dict:
        """Check if a purchase amount is within the configured budget."""
        limit = config.BUDGET_LIMIT
        if amount <= limit:
            return {"approved": True, "remaining": limit - amount}
        return {"approved": False, "reason": f"Exceeds budget of ${limit}"}

    @tool("create_purchase_order")
    def create_purchase_order(
        product_id: str,
        quantity: int,
        vendor_id: str = config.DEFAULT_VENDOR_ID,
    ) -> dict:
        """Create a mock purchase order for a product."""
        return {
            "status": "success",
            "po_id": f"PO-{product_id}-{quantity}",
            "message": (
                f"Successfully ordered {quantity} units of {product_id} from {vendor_id}."
            ),
        }

    @contextmanager
    def _oms_tools_context():
        yield [check_budget, create_purchase_order]

    return _oms_tools_context()
