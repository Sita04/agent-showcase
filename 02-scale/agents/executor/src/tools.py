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

from crewai.tools import tool
from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters
from config.default_config import config

MCP_SERVER_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..',
                 'vector-search-backend', 'mcp', 'server.py')
)


def get_mcp_server():
    """Create an MCPServerAdapter connected to the Vector Search MCP server."""
    return MCPServerAdapter(
        StdioServerParameters(
            command="uv",
            args=["run", MCP_SERVER_PATH],
        ),
        "search_products",
    )


class LocalTools:
    """Local tools that don't need MCP (mock order/budget system)."""

    @tool("Create Purchase Order")
    def create_purchase_order(product_id: str, quantity: int, vendor_id: str = config.DEFAULT_VENDOR_ID):
        """
        Create a Purchase Order for a specific product.

        Args:
            product_id: The unique ID of the product to purchase.
            quantity: The number of units to order.
            vendor_id: The ID of the vendor (default: 'mercari_seller').
        """
        return {
            "status": "success",
            "po_id": f"PO-{product_id}-{quantity}",
            "message": f"Successfully ordered {quantity} units of {product_id}."
        }

    @tool("Check Budget")
    def check_budget(amount: float, category: str):
        """
        Check if a purchase amount is within the budget for a specific category.

        Args:
            amount: The total cost of the purchase.
            category: The budget category (e.g., 'marketing', 'office_supplies').
        """
        limit = config.BUDGET_LIMIT
        if amount <= limit:
            return {"approved": True, "remaining": limit - amount}
        else:
            return {"approved": False, "reason": f"Exceeds budget of ${limit}"}
