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

"""
Scout Agent for the Shopping Squad.
Uses the Vector Search MCP server to find real products within a specific budget.
"""

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from .schemas import CartItem, CartItemOptions
import os
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent / '.env'
load_dotenv(dotenv_path=env_path)

# Remote MCP server is used instead of local one.

def create_scout_agent(category: str, query: str, budget: float, name="product_scout_node"):
    return LlmAgent(
        name=name,
        model="gemini-2.5-flash",
        output_key=name,
        instruction=f"""
        You are a Specialist Scout. Your goal is to find AT LEAST 3 perfect items that match 
        the user's query and fit strictly within the provided budget.
        
        Category: {category}
        
        User Query: {query}
        Maximum Budget: {budget}
        
        1. Use the 'search_products' tool with your query, passing `rows=5` to limit results.
        2. Look for items that match the aesthetic 'vibes' provided in the prompt.
        3. IMPORTANT: Use the `filter` parameter to guarantee items are strictly under budget!
           Example: `{{"price": {{"$lte": {budget}}}}}` 
        4. Select exactly 3 different options that are strictly under the Maximum Budget.
        5. FIND SIMILAR: If the user query contains an item ID (e.g., starting with 'm' followed by numbers), you MUST use the `find_similar_items` tool and pass that ID as `item_id`. Pass `rows=5` to limit results. Do NOT use `search_products` in this case!
        6. If the user asks to find items similar to an image or description (without an ID), first use `search_products` to find a matching item and get its ID, then use `find_similar_items` with that ID!
        7. CRITICAL UX RULE: You must present your findings to the user in a friendly, beautiful Markdown format. Give each discovered item a bold title, include its ID in parentheses like `(ID: item_id)`, format its price in green (`<span style='color:green'>$X</span>`), and add a 1-sentence description. DO NOT output huge raw JSON blocks to the user.
        8. CRITICAL NEGATIVE CONSTRAINT: Do NOT select waist packs, fanny packs, or small pouches if the user is looking for a backpack! Focus only on full-size backpacks.
        9. CRITICAL NEGATIVE CONSTRAINT: Do NOT select items that are explicitly for kids, children, or youth if the user persona implies an adult male (or if the query specifies 'men'). Filter these out manually from your final selection!
        10. At the VERY END of your message, you MUST append your structured JSON data secretly inside an HTML comment box. The frontend UI will hide the comment, so the user won't see the ugly code! Include the 'Score' from the search tool as the 'similarity' value!
        Format EXACTLY like this:
        <!--[JSON_PAYLOAD]
        {{
           "category": "{category}",
           "options": [
              {{"id": "...", "name": "...", "price": 25.0, "img_url": "...", "url": "...", "description": "...", "similarity": 0.95}}
           ]
        }}
        [/JSON_PAYLOAD]-->
        CRITICAL: DO NOT use placeholder values like "0.0" or "..." in the JSON! Fill them in with the REAL prices, IDs, and similarity scores from your search!
        """,
        tools=[
            McpToolset(
                connection_params=StreamableHTTPConnectionParams(
                    url=os.environ.get("MCP_SERVER_URL"),
                ),
                tool_filter=["search_products", "find_similar_items"],
            )
        ],
    )