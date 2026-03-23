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

from crewai_tools import MCPServerAdapter
from mcp import StdioServerParameters
from config.default_config import config

MCP_SERVER_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..', '..',
                 'vector-search-backend', 'mcp', 'server.py')
)

OMS_MCP_SERVER_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..',
                 'mock_oms_mcp', 'server.py')
)

def get_mcp_server():
    """Create an MCPServerAdapter connected to the Vector Search MCP server."""
    return MCPServerAdapter(
        StdioServerParameters(
            command="uv",
            args=["run", "-q", MCP_SERVER_PATH],
        ),
        "search_products",
    )

def get_mock_oms_mcp():
    """Create an MCPServerAdapter connected to the Mock Order Management System MCP server."""
    return MCPServerAdapter(
        StdioServerParameters(
            command="uv",
            args=["run", "-q", OMS_MCP_SERVER_PATH],
        )
    )
