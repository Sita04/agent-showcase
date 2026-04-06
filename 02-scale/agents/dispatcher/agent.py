import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import httpx
from google.adk.agents.llm_agent import LlmAgent
from google.adk import Context
from config.prompts import DISPATCHER_INSTRUCTION

class DispatcherAgent(LlmAgent):
    """
    DispatcherAgent acts as the dashboard/front-end for the MAS Orchestrator.
    It takes user requests and forwards them via A2A JSON-RPC to the LangGraph A2A Server.
    """
    
    def __init__(self, **kwargs):
        # We define a basic instruction for the agent.
        super().__init__(
            name="dispatcher",
            model="gemini-2.5-flash",
            instruction=DISPATCHER_INSTRUCTION,
            **kwargs
        )
        # The A2A LangGraph Server endpoint (matching the test_a2a_client.py target)
        self.a2a_server_url = "http://localhost:8000"
        
    async def call_a2a_server(self, text: str) -> str:
        """Sends the user's request to the LangGraph A2A Server via JSON-RPC."""
        payload = {
            "jsonrpc": "2.0",
            "id": "req-123",
            "method": "message/send",
            "params": {
                "message": {
                    "message_id": "uuid-1234",
                    "parts": [{"text": text}],
                    "role": "user"
                }
            }
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.a2a_server_url}/v1/messages", 
                    json=payload,
                    timeout=60.0
                )
                response.raise_for_status()
                data = response.json()
                
                # Extract the artifact from the A2A response
                artifacts = data.get("result", {}).get("artifacts", [])
                if artifacts and len(artifacts) > 0:
                    parts = artifacts[0].get("parts", [])
                    if parts:
                        return parts[0].get("text", "No text in artifact.")
                return f"Raw response: {data}"
            except Exception as e:
                return f"Failed to communicate with A2A server: {str(e)}"

    async def _execute(self, ctx: Context, input_data: str) -> str:
        """
        Overrides the internal execute to forward the request to the A2A server.
        """
        if not input_data:
            return "How can I help you today?"
            
        # Forward the message to the LangGraph planner
        result_text = await self.call_a2a_server(input_data)
        
        return result_text
        
    async def execute(self, ctx: Context, input_data: str) -> str:
        """
        Public execute method override to hook into the workflow.
        """
        return await self._execute(ctx, input_data)


# We can expose the agent for ADK Web testing
agent = DispatcherAgent()
