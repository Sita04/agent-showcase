import os

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

MCP_SERVER_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "server.py"
)

root_agent = LlmAgent(
    model="gemini-2.5-flash",
    name="product_search_agent",
    instruction="Help users find products in the Mercari catalog. "
    "Use search_products to search and generate_sample_query for inspiration.",
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="uv",
                    args=["run", MCP_SERVER_PATH],
                ),
                timeout=30,
            ),
            tool_filter=["search_products", "generate_sample_query"],
        )
    ],
)
