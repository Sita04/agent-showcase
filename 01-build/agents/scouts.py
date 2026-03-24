"""
Scout Agent for the Shopping Squad.
Uses the Vector Search MCP server to find real products within a specific budget.
"""

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from agents.schemas import CartItem, CartItemOptions
import os

# Define the path to your MCP server
MCP_SERVER_PATH = os.path.join(os.getcwd(), "mcp", "server.py")

def create_scout_agent(query: str, budget: float, name="product_scout_node"):
    return LlmAgent(
        name=name,
        model="gemini-2.5-flash",
        output_key=name,
        instruction=f"""
        You are a Specialist Scout. Your goal is to find AT LEAST 3 perfect items that match 
        the user's query and fit strictly within the provided budget.
        
        Category: {query.split(' ')[0]}
        
        User Query: {query}
        Maximum Budget: {budget}
        
        1. Use the 'search_products' tool with your query.
        2. Look for items that match the aesthetic 'vibes' provided in the prompt.
        3. IMPORTANT: Use the `filter` parameter to guarantee items are strictly under budget!
           Example: `{{"price": {{"$lte": {budget}}}}}` 
        4. Select exactly 3 different options that are strictly under the Maximum Budget.
        5. CRITICAL UX RULE: You must present your findings to the user in a friendly, beautiful Markdown format. Give each discovered item a bold title, format its price in green (`<span style='color:green'>$X</span>`), and add a 1-sentence description. DO NOT output huge raw JSON blocks to the user.
        6. At the VERY END of your message, you MUST append your structured JSON data secretly inside an HTML comment box. The frontend UI will hide the comment, so the user won't see the ugly code!
        Format EXACTLY like this:
        <!--[JSON_PAYLOAD]
        {{
           "category": "{query.split(' ')[0]}",
           "options": [
              {{"id": "...", "name": "...", "price": 0.0, "img_url": "...", "url": "...", "description": "..."}}
           ]
        }}
        [/JSON_PAYLOAD]-->
        """,
        tools=[
            McpToolset(
                connection_params=StdioConnectionParams(
                    server_params=StdioServerParameters(
                        command="uv",
                        args=["run", MCP_SERVER_PATH],
                    ),
                    timeout=30,
                ),
                tool_filter=["search_products"],
            )
        ],
    )
