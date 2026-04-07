import asyncio
import httpx
import uuid
import json

from google.adk import Context
from google.adk.workflow import Workflow, node
from google.adk.agents.llm_agent import LlmAgent

A2A_SERVER_URL = "http://localhost:8080"

def create_replanner_agent(attempt: int):
    """Dynamically creates an LLM Agent to handle the Re-planning (CUJ 3)."""
    return LlmAgent(
        name=f"replanner_agent_attempt_{attempt}",
        model="gemini-2.5-flash",
        instruction="""
        You are a strategic re-planner for a retail orchestration system. 
        The previous procurement request failed. Look at the user's original objective and the failure reason.
        Your job is to rewrite the objective to be broader or more likely to succeed (e.g., changing a specific 
        rare item to a broader category), while keeping the original intent and budget constraints.
        
        OUTPUT INSTRUCTIONS:
        Output ONLY the new text for the objective. Do not include quotes, preambles, or formatting.
        """
    )

@node(name="control_room_orchestrator", rerun_on_resume=True)
async def control_room_orchestrator(ctx: Context, node_input: str):
    """
    Main Orchestrator Node.
    Uses dynamic code routing to handle the A2A delegation and CUJ 3 re-planning loops.
    """
    max_attempts = 2
    attempt = 1
    current_objective = node_input
    report = "No delegation attempted."
    is_success = False
    
    print(f"\n🚨 [Control Room] Received Alert: {current_objective}")
    
    while attempt <= max_attempts:
        print(f"\n➡️  [Control Room] Delegating to LangGraph (Attempt {attempt}):\n    '{current_objective}'")
        
        # --- 1. Call A2A Server (Sub-agent Delegation) ---
        msg_id = str(uuid.uuid4())
        json_rpc_payload = {
            "jsonrpc": "2.0",
            "id": f"req-cr-{attempt}",
            "method": "message/send",
            "params": {
                "message": {
                    "message_id": msg_id,
                    "parts": [{"text": current_objective}],
                    "role": "user"
                }
            }
        }

        try:
            async with httpx.AsyncClient(timeout=120.0) as client: 
                response = await client.post(f"{A2A_SERVER_URL}/", json=json_rpc_payload)
                
                if response.status_code != 200:
                    report = f"A2A Server error: {response.status_code}"
                    is_success = False
                else:
                    result = response.json()
                    if "error" in result:
                        report = str(result['error'])
                        is_success = False
                    else:
                        task = result.get("result", {})
                        artifacts = task.get("artifacts", [])
                        report = "No report returned."
                        if artifacts and "parts" in artifacts[-1]:
                            parts = artifacts[-1]["parts"]
                            if len(parts) > 0 and "text" in parts[0]:
                                report = parts[0]["text"]
                        
                        # Evaluate outcome
                        if "not found" in report.lower() or "discontinued" in report.lower() or "no inventory" in report.lower():
                            is_success = False
                        else:
                            is_success = True
        except Exception as e:
            report = f"Connection error: {str(e)}"
            is_success = False

        # --- 2. Evaluate and Re-plan (CUJ 3) ---
        if is_success:
            print(f"\n🎉 [Control Room] Workflow completed successfully:\n{report}")
            ctx.state["final_outcome"] = report
            return {"status": "Success", "report": report}
        
        print(f"\n⚠️ [Control Room] Attempt {attempt} failed:\n    Reason: {report}")
        
        if attempt < max_attempts:
            print(f"\n💡 [Control Room] Triggering Re-Planner Agent...")
            replanner = create_replanner_agent(attempt)
            feedback_prompt = f"Original Objective: {current_objective}\nFailure Reason: {report}\nPlease broaden the search."
            
            # Using ctx.run_node to dynamically invoke an LLM agent mid-workflow!
            new_objective_raw = await ctx.run_node(replanner, feedback_prompt)
            
            # Parse the LLM output safely
            if hasattr(new_objective_raw, "parts"):
                current_objective = "".join([p.text for p in new_objective_raw.parts if hasattr(p, "text") and p.text])
            elif isinstance(new_objective_raw, str):
                current_objective = new_objective_raw
            else:
                current_objective = str(new_objective_raw)
                
            current_objective = current_objective.strip()
            print(f"💡 [Control Room] New Objective Generated:\n    '{current_objective}'")
            
        attempt += 1

    print(f"\n❌ [Control Room] Fatal Error: Max attempts reached.")
    ctx.state["final_outcome"] = f"Failed after {max_attempts} attempts. Last error: {report}"
    return {"status": "Failed", "report": report}

# Define the workflow graph using the newly decorated node
ControlRoomAgent = Workflow(
    name="ControlRoomAgent",
    edges=[("START", control_room_orchestrator)],
)
