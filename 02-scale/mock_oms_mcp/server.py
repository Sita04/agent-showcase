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

from mcp.server.fastmcp import FastMCP
import sys
import os

# Add the project root to the path so we can import the shared config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agents.config.default_config import config

# Initialize the FastMCP Server
mcp = FastMCP("Mock Order Management System")

@mcp.tool()
def check_budget(amount: float, category: str) -> dict:
    """
    Check if a purchase amount is within the budget for a specific category.

    Args:
        amount: The total cost of the purchase.
        category: The budget category (e.g., 'marketing', 'office_supplies', 'collectibles').
    """
    limit = config.BUDGET_LIMIT
    if amount <= limit:
        return {"approved": True, "remaining": limit - amount}
    else:
        return {"approved": False, "reason": f"Exceeds budget of ${limit}"}


@mcp.tool()
def create_purchase_order(product_id: str, quantity: int, vendor_id: str = config.DEFAULT_VENDOR_ID) -> dict:
    """
    Create a Purchase Order for a specific product.

    Args:
        product_id: The unique ID of the product to purchase.
        quantity: The number of units to order.
        vendor_id: The ID of the vendor.
    """
    return {
        "status": "success",
        "po_id": f"PO-{product_id}-{quantity}",
        "message": f"Successfully ordered {quantity} units of {product_id} from {vendor_id}."
    }

if __name__ == "__main__":
    # Start the server using stdio transport
    mcp.run(transport="stdio")
