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

from crewai import Task
from config.prompts import EXECUTOR_TASK_PROMPTS

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
            agent=agent
        )

    def procurement_task(self, agent, quantity):
        prompts = EXECUTOR_TASK_PROMPTS["procurement"]
        return Task(
            description=prompts["description"].format(
                quantity=quantity
            ),
            expected_output=prompts["expected_output"],
            agent=agent,
            context=[] # Will be filled dynamically with the output of the previous task
        )
