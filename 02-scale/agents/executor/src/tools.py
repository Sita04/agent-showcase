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
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from crewai.tools import tool
from config.default_config import config

class MCPTools:
    """Wraps MCP calls for CrewAI agents."""

    @tool("Search Mercari Vectors")
    def search_vectors(query: str, similarity_threshold: float = config.DEFAULT_SIMILARITY_THRESHOLD):
        """
        Search the Mercari Vector Store for products matching the semantic meaning of the query.
        Returns a list of products with their prices, IDs, and similarity scores.
        
        Args:
            query: The search query (e.g., "vintage sci-fi mug").
            similarity_threshold: Minimum similarity score (0.0 to 1.0) to consider a match.
        """
        # Placeholder: This will eventually call the actual MCP Client
        print(f"DEBUG: MCP Tool Call -> search_vectors(query='{query}', threshold={similarity_threshold})")
        
        # Mock Response for now
        if "sci-fi" in query.lower():
            return [
                {"id": "item_123", "name": "Vintage Star Wars Mug 1977", "price": 25.00, "similarity": 0.92},
                {"id": "item_456", "name": "Doctor Who Tardis Teapot", "price": 45.00, "similarity": 0.88},
                {"id": "item_789", "name": "Space Cadet Coffee Cup", "price": 12.50, "similarity": 0.75}
            ]
        elif "cat" in query.lower():
             return [
                {"id": "item_999", "name": "Cute Cat Mug", "price": 15.00, "similarity": 0.95}
            ]
        else:
            return []

    @tool("Create Purchase Order")
    def create_purchase_order(product_id: str, quantity: int, vendor_id: str = config.DEFAULT_VENDOR_ID):
        """
        Create a Purchase Order for a specific product.
        
        Args:
            product_id: The unique ID of the product to purchase.
            quantity: The number of units to order.
            vendor_id: The ID of the vendor (default: 'mercari_seller').
        """
        # Placeholder: This will eventually call the actual MCP Client
        print(f"DEBUG: MCP Tool Call -> create_purchase_order(id='{product_id}', qty={quantity})")
        
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
        # Placeholder
        print(f"DEBUG: MCP Tool Call -> check_budget(amount={amount}, category='{category}')")
        
        limit = config.BUDGET_LIMIT
        if amount <= limit:
             return {"approved": True, "remaining": limit - amount}
        else:
             return {"approved": False, "reason": f"Exceeds budget of ${limit}"}
