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

from typing import TypedDict, Dict, Any, Optional
from pydantic import BaseModel, Field

class AlertExtraction(BaseModel):
    """Schema for extracting details from an inventory alert."""
    region: str = Field(description="The geographic region mentioned in the alert, e.g., 'Northeast'.")
    item_description: str = Field(description="The specific item or category to restock.")
    quantity_needed: int = Field(description="The number of units required. Default to 500 if not specified.", default=500)
    max_budget: float = Field(description="The maximum allowed budget per unit. Default to 300.0 if not specified.", default=300.0)
    is_destructive: bool = Field(
        description="Whether the alert requests a destructive action (delete, drop, destroy, modify schema, wipe) rather than a legitimate procurement task.",
        default=False,
    )

class PlanState(TypedDict, total=False):
    """
    The state schema for the LangGraph Planning Agent.
    This holds the context as the graph progresses from analysis to delegation.
    """
    objective: str               # e.g., "Inventory Alert: Northeast Region is below safe levels for 'Vintage Sci-Fi Mugs'."
    region: Optional[str]        # Extracted region, e.g., "Northeast"
    item_description: Optional[str] # Extracted item, e.g., "Vintage Sci-Fi Mugs"
    quantity_needed: Optional[int]  # Extracted quantity
    max_budget: Optional[float]     # Extracted/determined budget
    
    current_step: str            # Current phase of execution
    delegation_status: str       # 'pending', 'success', 'failed'
    
    execution_result: Optional[str] # The raw output from the CrewAI worker
    final_report: Optional[str]     # The final synthesized report for the dashboard

    # CUJ 2: Identity Shield fields
    malicious_intent: Optional[bool]   # Whether the request was classified as destructive
    security_violation: Optional[str]  # IAM rejection details if a forbidden action was attempted

    # CUJ 3: Re-planning fields
    replan_attempts: Optional[int]     # Number of times the Re-Planner has broadened the query
    original_item_description: Optional[str]  # First item_description before any broadening
