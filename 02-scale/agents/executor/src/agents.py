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

from crewai import Agent, LLM
try:
    from ...config.prompts import EXECUTOR_AGENT_PROMPTS
    from ...config.default_config import config
except ImportError:
    from config.prompts import EXECUTOR_AGENT_PROMPTS
    from config.default_config import config

class ExecutorAgents:
    """Defines the specialized agents for the Execution Layer."""

    def __init__(self):
        # Configure the LLM to use Vertex AI
        os.environ["VERTEXAI_PROJECT"] = config.GOOGLE_CLOUD_PROJECT
        os.environ["VERTEXAI_LOCATION"] = config.GOOGLE_CLOUD_LOCATION_GLOBAL

        self.llm = LLM(
            model=config.AGENT_MODEL,
            temperature=config.AGENT_TEMPERATURE,
            max_tokens=config.AGENT_MAX_TOKENS,
        )

    def sourcing_specialist(self, mcp_tools):
        prompts = EXECUTOR_AGENT_PROMPTS["sourcing_specialist"]
        return Agent(
            role=prompts["role"],
            goal=prompts["goal"],
            backstory=prompts["backstory"],
            tools=mcp_tools,
            verbose=True,
            allow_delegation=False,
            memory=False,
            reasoning=False,
            max_reasoning_attempts=config.MAX_REASONING_ATTEMPTS,
            llm=self.llm
        )

    def procurement_officer(self, mcp_tools):
        prompts = EXECUTOR_AGENT_PROMPTS["procurement_officer"]
        return Agent(
            role=prompts["role"],
            goal=prompts["goal"],
            backstory=prompts["backstory"],
            tools=mcp_tools,
            verbose=True,
            allow_delegation=False,
            memory=False,
            reasoning=False,
            max_reasoning_attempts=config.MAX_REASONING_ATTEMPTS,
            llm=self.llm
        )
