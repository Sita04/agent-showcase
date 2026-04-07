import httpx
import uuid

from google.adk.agents.llm_agent import LlmAgent

A2A_SERVER_URL = "http://localhost:8080"


async def delegate_to_planner(objective: str) -> dict:
    """Delegate an objective to the LangGraph Planning Agent via A2A JSON-RPC.

    Sends the objective to the A2A server and returns the planner's report.
    The report may indicate success, failure (item not found), or a security
    violation (permission denied).

    Args:
        objective: The natural language objective to send to the planner,
            e.g. "Order 500 Vintage Sci-Fi Mugs for Northeast region, max $50/unit".

    Returns:
        A dict with 'status' ("success", "error", or "security_block") and 'report'.
    """
    msg_id = str(uuid.uuid4())
    json_rpc_payload = {
        "jsonrpc": "2.0",
        "id": f"req-cr-{msg_id[:8]}",
        "method": "message/send",
        "params": {
            "message": {
                "message_id": msg_id,
                "parts": [{"text": objective}],
                "role": "user",
            }
        },
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(f"{A2A_SERVER_URL}/", json=json_rpc_payload)

            if response.status_code != 200:
                return {
                    "status": "error",
                    "report": f"A2A Server error: {response.status_code}",
                }

            result = response.json()
            if "error" in result:
                return {"status": "error", "report": str(result["error"])}

            task = result.get("result", {})
            artifacts = task.get("artifacts", [])
            report = "No report returned."
            if artifacts and "parts" in artifacts[-1]:
                parts = artifacts[-1]["parts"]
                if len(parts) > 0 and "text" in parts[0]:
                    report = parts[0]["text"]

            # CUJ 2: Detect security blocks (terminal — no replanning)
            security_keywords = [
                "permission denied",
                "security violation",
                "blocked by iam",
                "identity shield",
            ]
            if any(kw in report.lower() for kw in security_keywords):
                return {"status": "security_block", "report": report}

            return {"status": "success", "report": report}

    except Exception as e:
        return {"status": "error", "report": f"Connection error: {str(e)}"}


CONTROL_ROOM_INSTRUCTION = """\
You are the Global Retail IT Control Room orchestrator. You coordinate
a multi-agent system by delegating tasks to the LangGraph Planning Agent.

## How to work

1. When you receive an inventory alert or procurement request, call
   `delegate_to_planner` with the objective.

2. Read the returned status:
   - **"success"**: Report the result to the user. Include the full report text.
   - **"security_block"**: This is a SECURITY VIOLATION. Report it immediately
     as "SECURITY BLOCK: <report>". Do NOT retry or try to work around it.
   - **"error"**: The delegation failed. If the report mentions "not found",
     "discontinued", or "no inventory", broaden the search terms and call
     `delegate_to_planner` again with a rewritten objective. You may retry
     up to once. If it still fails, report the failure.

3. Keep responses concise and professional.

## Important rules

- NEVER retry after a security_block. Security violations are terminal.
- When broadening a search, keep the original budget and quantity constraints
  but use more general product terms.
- Always include the full planner report in your response.
"""

ControlRoomAgent = LlmAgent(
    name="ControlRoomAgent",
    model="gemini-2.5-flash",
    instruction=CONTROL_ROOM_INSTRUCTION,
    tools=[delegate_to_planner],
)

# Alias for `adk deploy agent_engine` which expects `root_agent`
root_agent = ControlRoomAgent
