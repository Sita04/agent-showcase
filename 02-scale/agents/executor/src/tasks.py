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

import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pydantic import BaseModel, Field
from typing import List, Optional
from crewai import Task
try:
    from ...config.prompts import EXECUTOR_TASK_PROMPTS
except ImportError:
    from config.prompts import EXECUTOR_TASK_PROMPTS

class ProductCandidate(BaseModel):
    id: str = Field(description="Product ID")
    name: str = Field(description="Product Name")
    price: float = Field(description="Product Price")
    similarity_score: float = Field(description="Similarity Score")
    match_reason: str = Field(description="Why it fits the description")

class SourcingOutput(BaseModel):
    candidates: List[ProductCandidate] = Field(description="List of top candidates found")

class ProcurementOutput(BaseModel):
    selected_product_id: Optional[str] = Field(description="The selected Product ID", default=None)
    selected_product_name: Optional[str] = Field(description="The selected Product Name", default=None)
    total_cost: float = Field(description="Total Cost of the order", default=0.0)
    purchase_order_id: Optional[str] = Field(description="The Purchase Order ID if successful", default=None)
    status: str = Field(description="Status: SUCCESS or FAILED")
    reason: Optional[str] = Field(description="Reason if failed", default=None)

class ExecutorTasks:
    """Defines the tasks for the Execution Layer."""

    def sourcing_task(self, agent, item_description, max_budget):
        prompts = EXECUTOR_TASK_PROMPTS["sourcing"]
        return Task(
            description=prompts["description"].format(
                item_description=item_description, 
                max_budget=max_budget
            ),
            expected_output=prompts["expected_output"],
            output_pydantic=SourcingOutput,
            agent=agent
        )

    def procurement_task(self, agent, quantity):
        prompts = EXECUTOR_TASK_PROMPTS["procurement"]
        return Task(
            description=prompts["description"].format(
                quantity=quantity
            ),
            expected_output=prompts["expected_output"],
            output_pydantic=ProcurementOutput,
            agent=agent,
            context=[] # Will be filled dynamically with the output of the previous task
        )
