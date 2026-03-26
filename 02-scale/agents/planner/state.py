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
