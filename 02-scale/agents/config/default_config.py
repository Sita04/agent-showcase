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
from dataclasses import dataclass
from dotenv import load_dotenv
from pathlib import Path

# Load .env from the project root (02-scale)
root_dir = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=root_dir / ".env")

@dataclass
class DefaultConfig:
    # Project & Environment
    GOOGLE_CLOUD_PROJECT: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    GOOGLE_CLOUD_LOCATION_GLOBAL: str = "global"
    GOOGLE_CLOUD_LOCATION_REGIONAL: str = "us-central1"
    
    # Models
    AGENT_MODEL: str = "vertex_ai/gemini-3.1-flash-lite"
    PLANNING_MODEL: str = "vertex_ai/gemini-2.5-flash"
    EMBEDDER_MODEL: str = "text-embedding-005"
    
    # Agent Settings
    AGENT_TEMPERATURE: float = 0.0
    AGENT_MAX_TOKENS: int = 4096
    MAX_REASONING_ATTEMPTS: int = 3
    
    # Framework Fallbacks
    DUMMY_OPENAI_KEY: str = "NA"
    
    # Tool Settings
    DEFAULT_SIMILARITY_THRESHOLD: float = 0.7
    DEFAULT_VENDOR_ID: str = "mercari_seller"
    BUDGET_LIMIT: float = 2000.0

    def __post_init__(self):
        if not self.GOOGLE_CLOUD_PROJECT:
            raise ValueError("GOOGLE_CLOUD_PROJECT environment variable is not set. Please set it in your .env file or environment.")

config = DefaultConfig()
