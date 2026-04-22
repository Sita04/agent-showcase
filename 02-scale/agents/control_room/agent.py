import asyncio
import contextvars
import httpx
import uuid
import json
import os

from google.adk import Context
from google.adk.workflow import Workflow, node
from google.adk.agents.llm_agent import LlmAgent

A2A_SERVER_URL = os.environ.get("PLANNER_AGENT_URL", "http://127.0.0.1:8080")
CONTROL_ROOM_STATUS_URL = os.environ.get("CONTROL_ROOM_STATUS_URL", "")

# Side-channel for Dashboard Updates
#
# Per-dispatch session id. The dashboard server (in-process path) sets this
# before invoking the workflow; the workflow's first node sets it from the
# JSON envelope (AE path). emit_status / emit_final_report read it to route
# events to the right browser tab so concurrent demos don't see each other's
# bubbles.
current_session_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_session_id", default=""
)

# In-process per-session queues. The dashboard server reads from these (one
# queue per active browser tab). Empty key "" is reserved for legacy callers
# without a session id; the dashboard ignores it.
dashboard_queues: dict[str, asyncio.Queue] = {}


def get_or_create_queue(session_id: str) -> asyncio.Queue:
    q = dashboard_queues.get(session_id)
    if q is None:
        q = asyncio.Queue()
        dashboard_queues[session_id] = q
    return q


async def emit_status(name: str, text: str, role: str = "control_room"):
    # XOR: HTTP when CONTROL_ROOM_STATUS_URL is set (AE or cross-process),
    # in-process queue otherwise. Doing both duplicates every status event
    # when the dashboard runs in-process with the URL set for sibling
    # processes (e.g. the Planner A2A bridge).
    session_id = current_session_id.get()
    if CONTROL_ROOM_STATUS_URL:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(
                    CONTROL_ROOM_STATUS_URL,
                    data={"name": name, "text": text, "role": role, "session_id": session_id},
                )
        except Exception as e:
            print(f"[Control Room] Failed to push status to {CONTROL_ROOM_STATUS_URL}: {e}")
    else:
        await get_or_create_queue(session_id).put(
            {"type": "status", "name": name, "text": text, "role": role}
        )


async def emit_final_report(status: str, report: str):
    """Push the final procurement report to the dashboard.

    Canonical source for the result bubble. Uses HTTP when
    CONTROL_ROOM_STATUS_URL is set (the only path that works on Agent
    Engine); otherwise pushes directly to the in-process queue.
    """
    session_id = current_session_id.get()
    if CONTROL_ROOM_STATUS_URL:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Reuse the status endpoint with a marker role; the dashboard
                # server translates this into an adk_event for the UI.
                await client.post(
                    CONTROL_ROOM_STATUS_URL,
                    data={
                        "name": "final_report",
                        "text": report,
                        "role": f"final_report:{status}",
                        "session_id": session_id,
                    },
                )
        except Exception as e:
            print(f"[Control Room] Failed to push final report to {CONTROL_ROOM_STATUS_URL}: {e}")
    else:
        await get_or_create_queue(session_id).put({
            "type": "adk_event",
            "event_type": "WorkflowComplete",
            "node_name": "control_room_orchestrator",
            "output": {"status": status, "report": report},
        })


def _classify_report(report: str) -> tuple[bool, bool]:
    """Return ``(is_success, should_retry)`` for a planner/executor report.

    Markers are split into three tiers because some failure phrases (e.g.
    "Status: FAILURE") show up in both terminal and retryable scenarios. We
    check specific signals before generic ones so a report like
    "Status: FAILURE — item does not match the requested ..." routes to the
    re-planner instead of being short-circuited as terminal.
    """
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
    # Specific terminal: budget/system/policy hits — replanning won't help.
    specific_terminal_markers = [
        "over budget",
        "failed_precondition",
        "internal system error",
        "error when invoking agent engine",
    ]
    # Specific retryable: a re-planned, broader query has a real chance.
    specific_retryable_markers = [
        "not found",
        "discontinued",
        "no inventory",
        "does not match",
        "do not match",
        "did not match",
        "wrong item",
        "incorrect item",
        "a2a server error",
        "connection error",
        "connection issue",
        "internal server error",
        "no report returned",
    ]
    # Generic failure phrasing — terminal only when no specific retryable hint.
    generic_failure_markers = [
        "status: failed",
        "status: failure",
        "outcome: failed",
        "outcome: failure",
        "reason for failure",
        "purchase order id: n/a",
        "purchase order id: not issued",
        "not issued",
        "procurement failed",
        "could not be completed",
        "could not be processed",
        "failed due to",
    ]

    if any(marker in normalized for marker in specific_terminal_markers):
        return False, False
    if any(marker in normalized for marker in specific_retryable_markers):
        return False, True
    if any(marker in normalized for marker in generic_failure_markers):
        return False, False
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

def _unwrap_envelope(node_input: str) -> tuple[str, str]:
    """Strip the dashboard's session-id envelope off the user objective.

    The dashboard sends the prompt as
    ``{"session_id": "...", "objective": "..."}`` so the orchestrator can
    route status events back to the right browser tab. Plain-text input is
    accepted unchanged so direct A2A callers (without a dashboard) still
    work.
    """
    if not isinstance(node_input, str):
        return "", str(node_input)
    stripped = node_input.lstrip()
    if not stripped.startswith("{"):
        return "", node_input
    try:
        envelope = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return "", node_input
    if not isinstance(envelope, dict) or "objective" not in envelope:
        return "", node_input
    return str(envelope.get("session_id", "")), str(envelope["objective"])


@node(name="control_room_orchestrator", rerun_on_resume=True)
async def control_room_orchestrator(ctx: Context, node_input: str):
    """
    Main Orchestrator Node.
    Uses dynamic code routing to handle the A2A delegation and CUJ 3 re-planning loops.
    """
    session_id, current_objective = _unwrap_envelope(node_input)
    if session_id:
        # AE path: the dashboard's process can't share a contextvar with the
        # AE container, so the workflow re-establishes the session id from
        # the prompt envelope. The local in-process path also benefits — one
        # source of truth either way.
        current_session_id.set(session_id)

    max_attempts = 2
    attempt = 1
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
                    "role": "user",
                    # A2A Message.metadata: the Planner reads this and sets
                    # its own contextvar so its status pushes carry the same
                    # session_id back to the dashboard.
                    "metadata": {"session_id": current_session_id.get()},
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
                                    # CUJ 2: planner emits a distinct artifact name for
                                    # security blocks. Detect blocks by artifact name
                                    # rather than substring-matching report text, which
                                    # is spoofable via prompt injection.
                                    security_artifact = next(
                                        (a for a in artifacts if a.get("name") == "security_incident_report"),
                                        None,
                                    )
                                    if security_artifact:
                                        sec_parts = security_artifact.get("parts", [])
                                        if sec_parts and "text" in sec_parts[0]:
                                            final_report = sec_parts[0]["text"]
                                        print(f"\n🛡️ [Control Room] Security block detected. Not retrying.")
                                        ctx.state["final_outcome"] = f"SECURITY BLOCK: {final_report}"
                                        await emit_final_report("Blocked", final_report)
                                        return {"status": "Blocked", "report": final_report}

                                    if artifacts and "parts" in artifacts[-1]:
                                        parts = artifacts[-1]["parts"]
                                        if len(parts) > 0 and "text" in parts[0]:
                                            final_report = parts[0]["text"]

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
            await emit_final_report("Success", final_report)
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
        await emit_final_report("Failed", final_report)
        return {"status": "Failed", "report": final_report}

    print(f"\n❌ [Control Room] Fatal Error: Max attempts reached.")
    ctx.state["final_outcome"] = f"Failed after {max_attempts} attempts. Last error: {final_report}"
    await emit_final_report("Failed", final_report)
    return {"status": "Failed", "report": final_report}

# Define the workflow graph
ControlRoomAgent = Workflow(
    name="ControlRoomAgent",
    edges=[("START", control_room_orchestrator)],
)

# Alias for `adk deploy agent_engine` which expects `root_agent`
root_agent = ControlRoomAgent
