import asyncio
import httpx
import uuid
import json
import os

from google.adk import Context
from google.adk.workflow import Workflow, node
from google.adk.agents.llm_agent import LlmAgent

A2A_SERVER_URL = os.environ.get("PLANNER_AGENT_URL", "http://127.0.0.1:8080")

# Side-channel for Dashboard Updates
# This allows us to send real-time progress to the UI without
# fighting ADK 2.0's strict node return types.
dashboard_queue = asyncio.Queue()


async def emit_status(name: str, text: str, role: str = "control_room"):
    await dashboard_queue.put({"type": "status", "name": name, "text": text, "role": role})


def _classify_report(report: str) -> tuple[bool, bool]:
    """Return ``(is_success, should_retry)`` for a planner/executor report."""
    # Strip markdown bold/italic markers so "**Outcome:** SUCCESS" matches
    normalized = (report or "").replace("*", "").strip().lower()

    success_markers = [
        "status: success",
        "outcome: success",
        "success: po-",
        "successfully ordered",
        "po_id",
        "purchase order id: po-",
    ]
    retryable_failure_markers = [
        "not found",
        "discontinued",
        "no inventory",
        "a2a server error",
        "connection error",
        "internal server error",
        "no report returned",
    ]
    terminal_failure_markers = [
        "status: failed",
        "status: failure",
        "outcome: failed",
        "reason for failure",
        "failed_precondition",
        "internal system error",
        "connection issue",
        "over budget",
        "purchase order id: n/a",
        "purchase order id:** n/a",
        "purchase order id: not issued",
        "not issued",
        "procurement failed",
        "could not be completed",
        "could not be processed",
        "failed due to",
        "error when invoking agent engine",
    ]

    if any(marker in normalized for marker in terminal_failure_markers):
        return False, False
    if any(marker in normalized for marker in retryable_failure_markers):
        return False, True
    if any(marker in normalized for marker in success_markers):
        return True, False
    # Bias toward surfacing unknown outcomes as failures rather than false success.
    return False, False

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
    is_success = False
    should_retry = False
    
    print(f"\n🚨 [Control Room] Received Alert: {current_objective}")
    await emit_status("system", f"Received request: {current_objective}")

    while attempt <= max_attempts:
        if attempt == 1:
            msg = "Routing the request to the Planning Agent..."
        else:
            msg = f"Retrying with a revised plan (attempt {attempt})..."
        print(f"\n➡️  [Control Room] {msg}\n    '{current_objective}'")
        await emit_status("system", msg)

        # 1. Call A2A Server (Sub-agent Delegation)

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

        final_report = "No report returned."
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                # Use stream to catch intermediate artifacts from the A2A server
                obj_preview = current_objective[:80] + ("..." if len(current_objective) > 80 else "")
                await emit_status("a2a", f"→ Planner: **message/send** \"{obj_preview}\"", role="a2a")
                async with client.stream("POST", f"{A2A_SERVER_URL}/", json=json_rpc_payload) as response:
                    if response.status_code != 200:
                        await emit_status("a2a", f"← Planner: **HTTP {response.status_code}**", role="a2a")
                        final_report = f"A2A Server error: {response.status_code}"
                        is_success = False
                        should_retry = True
                    else:
                        await emit_status("a2a", "← Planner: **connection established**, streaming response...", role="a2a")
                        async for line in response.aiter_lines():
                            if not line: continue
                            try:
                                data = json.loads(line)

                                if "error" in data:
                                    error = data["error"]
                                    final_report = (
                                        "A2A Server error: "
                                        f"{error.get('message', 'Unknown error')}"
                                    )
                                    is_success = False
                                    should_retry = True
                                    break
                                
                                # Handle intermediate notifications (artifacts)
                                if data.get("method") == "task/update":
                                    task_state = data.get("params", {}).get("status", {}).get("state", "")
                                    if task_state:
                                        await emit_status("a2a", f"← Planner: **task/update** state={task_state}", role="a2a")
                                    artifacts = data.get("params", {}).get("artifacts", [])
                                    for art in artifacts:
                                        # Skip the final report artifact — it will be
                                        # displayed via the adk_event return value.
                                        if art.get("name") == "orchestration_report":
                                            continue
                                        parts = art.get("parts", [])
                                        if parts and "text" in parts[0]:
                                            update_msg = parts[0]["text"]
                                            print(f"  [A2A Update] {update_msg}")
                                            # Push to dashboard queue for real-time visibility!
                                            await emit_status("execution", update_msg)
                                
                                # Handle the final result
                                if "result" in data:
                                    task_status = data["result"].get("status", {}).get("state", "completed")
                                    await emit_status("a2a", f"← Planner: **result** state={task_status}", role="a2a")
                                    await emit_status("system", "Received the procurement report. Evaluating the outcome...")
                                    task = data["result"]
                                    artifacts = task.get("artifacts", [])
                                    if artifacts and "parts" in artifacts[-1]:
                                        parts = artifacts[-1]["parts"]
                                        if len(parts) > 0 and "text" in parts[0]:
                                            final_report = parts[0]["text"]
                                    
                                    # CUJ 2: Detect security blocks (terminal — no replanning)
                                    security_keywords = ["permission denied", "security violation", "blocked by iam", "identity shield"]
                                    if any(kw in final_report.lower() for kw in security_keywords):
                                        print(f"\n🛡️ [Control Room] Security block detected. Not retrying.")
                                        ctx.state["final_outcome"] = f"SECURITY BLOCK: {final_report}"
                                        return {"status": "Blocked", "report": final_report}

                                    is_success, should_retry = _classify_report(final_report)
                            except Exception as e:
                                print(f"  [Control Room] Error parsing stream line: {e}")
        except Exception as e:
            await emit_status("system", f"Lost connection to the Planning Agent: {str(e)}")
            final_report = f"Connection error: {str(e)}"
            is_success = False
            should_retry = True

        # 2. Evaluate and Re-plan (CUJ 3)
        if is_success:
            print(f"\n🎉 [Control Room] Workflow completed successfully:\n{final_report}")
            ctx.state["final_outcome"] = final_report
            return {"status": "Success", "report": final_report}
        
        # Extract a short reason for the status line — avoid dumping the full
        # report, which will already be rendered via the adk_event return value.
        reason_line = final_report.split("\n")[0][:120] if final_report else "Unknown error"
        print(f"\n⚠️ [Control Room] Attempt {attempt} failed:\n    Reason: {final_report}")
        await emit_status("replanning", f"Attempt {attempt} was not successful: {reason_line}")

        if should_retry:
            if attempt < max_attempts:
                print(f"\n💡 [Control Room] Triggering Re-Planner Agent...")
                await emit_status("replanning", "Re-planning with a broader search strategy...")
                replanner = create_replanner_agent(attempt)
                feedback_prompt = f"Original Objective: {current_objective}\nFailure Reason: {final_report}\nPlease broaden the search."
                
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
                await emit_status("replanning", f"New Objective: {current_objective}")
                
                attempt += 1
                continue
            break

        print(f"\n❌ [Control Room] Fatal Error: Terminal failure.")
        ctx.state["final_outcome"] = final_report
        return {"status": "Failed", "report": final_report}

    print(f"\n❌ [Control Room] Fatal Error: Max attempts reached.")
    ctx.state["final_outcome"] = f"Failed after {max_attempts} attempts. Last error: {final_report}"
    return {"status": "Failed", "report": final_report}

# Define the workflow graph
ControlRoomAgent = Workflow(
    name="ControlRoomAgent",
    edges=[("START", control_room_orchestrator)],
)

# Alias for `adk deploy agent_engine` which expects `root_agent`
root_agent = ControlRoomAgent
