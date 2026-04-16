import os
import uvicorn
import sys
import json
import asyncio
from typing import Optional
from fastapi import FastAPI, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from starlette.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Ensure we can import from agents/
sys.path.append(os.path.join(os.path.dirname(__file__), "agents"))

# Load .env
load_dotenv()

import vertexai

PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "gcp-samples-ic0")
REGION = os.environ.get("GOOGLE_CLOUD_REGION", "us-central1")
vertexai.init(project=PROJECT_ID, location=REGION)

# Resolve which Control Room agent to use:
#   * env var unset      → fall back to deployment_metadata.json (convenience)
#   * env var = ""       → force local in-process runner
#   * env var = "local"  → force local in-process runner
#   * any other value    → use that as the Agent Engine resource name
# Distinguishing "unset" from "explicitly empty" lets a developer override the
# auto-loaded metadata without renaming the file.
_LOCAL_SENTINELS = {"", "local", "none"}
METADATA_FILE = "deployment_metadata.json"
_env_engine_id = os.environ.get("CONTROL_ROOM_AGENT_ENGINE_ID")
if _env_engine_id is None:
    CONTROL_ROOM_AGENT_ENGINE_ID = ""
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE) as f:
                CONTROL_ROOM_AGENT_ENGINE_ID = json.load(f).get("control_room_agent_engine_id", "")
        except Exception as e:
            print(f"Failed to read metadata file: {e}")
elif _env_engine_id.strip().lower() in _LOCAL_SENTINELS:
    CONTROL_ROOM_AGENT_ENGINE_ID = ""
    print("CONTROL_ROOM_AGENT_ENGINE_ID set to a local sentinel — skipping metadata file.")
else:
    CONTROL_ROOM_AGENT_ENGINE_ID = _env_engine_id

control_room_engine = None
if CONTROL_ROOM_AGENT_ENGINE_ID:
    print(f"Using remote Control Room Agent: {CONTROL_ROOM_AGENT_ENGINE_ID}")
    client = vertexai.Client(project=PROJECT_ID, location=REGION)
    control_room_engine = client.agent_engines.get(name=CONTROL_ROOM_AGENT_ENGINE_ID)
else:
    print("WARNING: CONTROL_ROOM_AGENT_ENGINE_ID not found. Falling back to local runner.")

from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.genai.types import Content as GenAIContent, Part as GenAIPart

from agents.control_room.agent import ControlRoomAgent, dashboard_queue

# A2A Server Imports
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentSkill, InternalError,
                       InvalidParamsError, Part, TextPart)
from a2a.utils import new_task
from a2a.utils.errors import ServerError

# Control Room A2A Implementation

class ControlRoomAgentExecutor(AgentExecutor):
    """
    AgentExecutor that wraps the Control Room ADK Workflow.
    Allows the orchestrator to be invoked via standardized A2A JSON-RPC.
    """
    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        objective = context.get_user_input()
        if not objective:
            raise ServerError(error=InvalidParamsError(message="User query cannot be empty."))

        # Initialize A2A task tracking
        task = context.current_task or new_task(context.message)
        await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        try:
            print(f"\n🚀 [A2A Entrypoint] Triggering Control Room with objective: '{objective}'")
            user_id = "admin"
            session = await _runner.session_service.create_session(
                app_name="control_room_app", user_id=user_id
            )
            
            new_message = GenAIContent(role="user", parts=[GenAIPart.from_text(text=objective)])
            
            final_report = "Execution failed."
            async for event in _runner.run_async(
                session_id=session.id, user_id=user_id, new_message=new_message
            ):
                # Optionally pipe artifacts from internal ADK events to A2A updater
                output = getattr(event, 'output', None)
                if output and isinstance(output, dict) and "report" in output:
                    final_report = output["report"]
                elif output and isinstance(output, str):
                    final_report = output

            # Send result back to caller
            await updater.add_artifact(
                [Part(root=TextPart(text=final_report))], 
                name="orchestration_report"
            )
            await updater.complete()
            print(f"✅ [A2A Entrypoint] Workflow complete.")

        except Exception as e:
            print(f"❌ [A2A Entrypoint] Error: {e}")
            await updater.failed()
            raise ServerError(error=InternalError(message=str(e)))

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass

# FastAPI Setup

api_app = FastAPI(title="Scale Agents Control Room Dashboard")

# Add CORS for local development
api_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_runner = None
if not control_room_engine:
    # Persistent runner for local dev
    _runner = InMemoryRunner(
        agent=ControlRoomAgent,
        app_name="control_room_app",
    )

@api_app.get("/health")
async def health_check():
    return {"status": "ok", "message": "FastAPI is running"}

def _enqueue_dashboard_push(name: str, text: str, role: str) -> None:
    """Translate a side-channel push into the right dashboard event shape."""
    if role.startswith("final_report"):
        # role looks like "final_report:Success" / "final_report:Blocked" / "final_report:Failed"
        _, _, status = role.partition(":")
        dashboard_queue.put_nowait({
            "type": "adk_event",
            "event_type": "WorkflowComplete",
            "node_name": "control_room_orchestrator",
            "output": {"status": status or "Success", "report": text},
        })
        return
    dashboard_queue.put_nowait({"type": "status", "name": name, "text": text, "role": role})


@api_app.post("/push_status")
async def push_status(name: str = Form(...), text: str = Form(...), role: str = Form("planner")):
    """Callback for external processes to push updates to the dashboard."""
    print(f"[DEBUG] Received status push: {name} - {text}")
    _enqueue_dashboard_push(name, text, role)
    return {"status": "ok"}

@api_app.post("/chat")
async def chat(prompt: Optional[str] = Form(None)):
    user_id = "admin"

    # Clear queue
    while not dashboard_queue.empty():
        try:
            dashboard_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
    
    # Create fresh session if running locally
    session = None
    if _runner:
        session = await _runner.session_service.create_session(
            app_name="control_room_app",
            user_id=user_id
        )
    
    parts = []
    if prompt:
        parts.append(GenAIPart.from_text(text=prompt))
    if not parts:
        return {"status": "error", "reply": "Empty message received"}

    new_message = GenAIContent(role="user", parts=parts)
    
    async def event_generator():
        # Per-request timeout for the upstream Agent Engine call. Cold starts can
        # take 3-5 minutes (see README), so allow ample headroom but bound it.
        AGENT_ENGINE_TIMEOUT_S = 540.0

        async def run_agent():
            try:
                if control_room_engine:
                    async with asyncio.timeout(AGENT_ENGINE_TIMEOUT_S):
                        # Call remote agent on Agent Engine using ADK 2.0 session API
                        remote_session = await control_room_engine.async_create_session(user_id=user_id)
                        session_id = remote_session["id"]

                        async for event in control_room_engine.async_stream_query(
                            user_id=user_id,
                            session_id=session_id,
                            message=prompt,
                        ):
                            # Handle remote events and pipe to dashboard
                            parts = event.get("parts", [])
                            for part in parts:
                                if "text" in part:
                                    await dashboard_queue.put({
                                        "type": "status",
                                        "name": "Control Room",
                                        "text": part["text"],
                                        "role": "control_room"
                                    })
                                elif "function_call" in part:
                                    await dashboard_queue.put({
                                        "type": "status",
                                        "name": "Control Room",
                                        "text": f"Calling tool: {part['function_call']['name']}",
                                        "role": "control_room"
                                    })
                        # Final report is pushed by the Control Room itself via
                        # the side-channel (/push_status with role=final_report:*).
                        # async_stream_query doesn't surface the orchestrator's
                        # return dict, so we don't synthesize a placeholder here.
                elif _runner and session:
                    # Call local runner
                    async for event in _runner.run_async(
                        session_id=session.id,
                        user_id=user_id,
                        new_message=new_message
                    ):
                        event_data = {
                            "type": "adk_event",
                            "event_type": type(event).__name__,
                            "node_name": getattr(event, 'node_name', 'N/A'),
                        }
                        output = getattr(event, 'output', None)
                        if output:
                            event_data["output"] = output
                        await dashboard_queue.put(event_data)
                else:
                    await dashboard_queue.put({"type": "status", "name": "error", "text": "No agent runner available."})
            except asyncio.CancelledError:
                # Generator was closed (client disconnect). Don't enqueue further updates.
                raise
            except asyncio.TimeoutError:
                await dashboard_queue.put({
                    "type": "status",
                    "name": "error",
                    "text": f"Agent Engine timed out after {AGENT_ENGINE_TIMEOUT_S}s",
                })
            except Exception as e:
                await dashboard_queue.put({"type": "status", "name": "error", "text": str(e)})
            finally:
                # Sentinel may fail if generator was cancelled; protect against double-fault.
                try:
                    await dashboard_queue.put(None)
                except Exception:
                    pass

        agent_task = asyncio.create_task(run_agent())

        try:
            while True:
                try:
                    item = await asyncio.wait_for(dashboard_queue.get(), timeout=15.0)
                    if item is None: break
                    yield f"data: {json.dumps(item)}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            # Client disconnected or stream ended — make sure the worker doesn't outlive us.
            if not agent_task.done():
                agent_task.cancel()
                try:
                    await agent_task
                except (asyncio.CancelledError, Exception):
                    pass

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Registry Entrypoint (A2A Host Integration)

def build_a2a_host(public_url: str):
    """Builds the A2A compliant host for the Control Room."""
    agent_card = AgentCard(
        name="Global-Retail-Orchestrator",
        description="Top-level coordinator for global retail logistics. Orchestrates strategic planning and tactical execution.",
        url=public_url,
        version="1.0.0",
        default_input_modes=["text", "text/plain"],
        default_output_modes=["text", "text/plain"],
        capabilities=AgentCapabilities(streaming=True),
        skills=[
            AgentSkill(
                id="orchestrate_logistics",
                name="Orchestrate Logistics",
                description="Receives inventory alerts and executes a multi-agent procurement workflow.",
                tags=["logistics", "retail", "orchestration"],
                examples=["Inventory Alert: Northeast Region is critically low on 'Rare Japanese Anime Figure'."],
            ),
            AgentSkill(
                id="security_incident_response",
                name="Security Enforcement",
                description="Detects and blocks unauthorized destructive actions via the Identity Shield.",
                tags=["security", "iam", "governance"],
            )
        ],
    )
    
    agent_executor = ControlRoomAgentExecutor()
    handler = DefaultRequestHandler(
        agent_executor=agent_executor, 
        task_store=InMemoryTaskStore()
    )
    server = A2AStarletteApplication(agent_card=agent_card, http_handler=handler)
    return server.build()

# Mount static files
ui_dir = os.path.join(os.path.dirname(__file__), "ui")

port = int(os.environ.get("PORT", 8080))
public_url = os.environ.get("AGENT_URL", f"http://localhost:{port}/")

# Build the A2A app
a2a_app = build_a2a_host(public_url)

# Combined application routing
from fastapi import FastAPI
from fastapi.responses import RedirectResponse

combined_app = FastAPI()

# Order matters: more specific routes first
combined_app.mount("/api", api_app)
combined_app.mount("/ui", StaticFiles(directory=ui_dir, html=True))

@combined_app.get("/")
async def root_redirect():
    return RedirectResponse(url="/ui/")

@combined_app.post("/push_status")
async def push_status_root(name: str = Form(...), text: str = Form(...), role: str = Form("planner")):
    print(f"[DEBUG] Received status push on root: {name} - {text}")
    _enqueue_dashboard_push(name, text, role)
    return {"status": "ok"}
    
combined_app.mount("/", a2a_app)

# Expose 'app' for uvicorn in production
app = combined_app

if __name__ == "__main__":
    print(f"Starting Registry-Ready Orchestrator on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
