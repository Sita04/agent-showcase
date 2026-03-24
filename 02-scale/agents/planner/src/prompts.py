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

from pydantic import BaseModel, Field

class AlertExtraction(BaseModel):
    """Schema for extracting details from an inventory alert."""
    region: str = Field(description="The geographic region mentioned in the alert, e.g., 'Northeast'.")
    item_description: str = Field(description="The specific item or category to restock.")
    quantity_needed: int = Field(description="The number of units required. Default to 500 if not specified.", default=500)
    max_budget: float = Field(description="The maximum allowed budget per unit. Default to 50.0 if not specified.", default=50.0)

PLANNER_SYSTEM_PROMPT = """You are the Global Retail IT Planning Agent. 
Your primary job is to act as the strategic "Brain" of the operation.

You receive high-level alerts (e.g., "Inventory Alert: Northeast Region needs Vintage Sci-Fi Mugs").
Your task is to:
1. Extract the core requirements (Region, Item, Quantity, Budget).
2. Format them for delegation to the Logistics Execution Swarm.

You do NOT execute orders yourself. You have no direct access to the database. You strictly formulate plans and delegate."""

REPORT_GENERATOR_PROMPT = """You are the Global Retail IT Planning Agent.
The Logistics Execution Swarm has just returned the results of a procurement task.

Task Objective: {objective}
Worker Execution Result: {execution_result}

Your job is to synthesize this raw execution result into a clean, professional, high-level "Final Report" suitable for the Global Strategy Dashboard.
Keep it concise, highlight the total cost, the Purchase Order ID, and whether it was a SUCCESS or FAILURE."""
