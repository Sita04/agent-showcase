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
try:
    from ...config.default_config import config
except ImportError:
    from config.default_config import config

VECTOR_SEARCH_MCP_URL = "https://ac-web2-761793285222.us-central1.run.app/mcp"

OMS_MCP_SERVER_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', '..',
                 'mock_oms_mcp', 'server.py')
)

def get_mcp_server():
    """Create an MCPServerAdapter connected to the Vector Search MCP server."""
    return MCPServerAdapter(
        {"url": VECTOR_SEARCH_MCP_URL, "transport": "streamable-http"},
        "search_products",
    )

def _resolve_oms_server_path() -> str:
    """Resolve the Mock OMS server path, with fallback for Agent Engine."""
    if os.path.exists(OMS_MCP_SERVER_PATH):
        return OMS_MCP_SERVER_PATH
    # Fallback: find via importlib (works when deployed via extra_packages)
    import importlib.util
    spec = importlib.util.find_spec("mock_oms_mcp.server")
    if spec and spec.origin:
        return spec.origin
    return OMS_MCP_SERVER_PATH

def get_mock_oms_mcp():
    """Create an MCPServerAdapter connected to the Mock Order Management System MCP server."""
    return MCPServerAdapter(
        StdioServerParameters(
            command=sys.executable,
            args=[_resolve_oms_server_path()],
        )
    )
