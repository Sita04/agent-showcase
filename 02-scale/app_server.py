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

app = FastAPI(title="Scale Agents Control Room Dashboard")

# Add CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Persistent runner
_runner = InMemoryRunner(
    agent=ControlRoomAgent,
    app_name="control_room_app",
)

@app.get("/health")
async def health_check():
    return {"status": "ok", "message": "FastAPI is running"}

@app.post("/push_status")
async def push_status(name: str = Form(...), text: str = Form(...), role: str = Form("planner")):
    """Callback for external processes to push updates to the dashboard."""
    print(f"[DEBUG] Received status push: {name} - {text}")
    await dashboard_queue.put({"type": "status", "name": name, "text": text, "role": role})
    return {"status": "ok"}

@app.post("/chat")
async def chat(prompt: Optional[str] = Form(None)):
    user_id = "admin"

    # Clear queue
    while not dashboard_queue.empty():
        try:
            dashboard_queue.get_nowait()
        except asyncio.QueueEmpty:
            break
    
    # Create fresh session
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
        async def run_agent():
            try:
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
            except Exception as e:
                await dashboard_queue.put({"type": "status", "name": "error", "text": str(e)})
            finally:
                await dashboard_queue.put(None)

        asyncio.create_task(run_agent())

        while True:
            try:
                item = await asyncio.wait_for(dashboard_queue.get(), timeout=15.0)
                if item is None: break
                yield f"data: {json.dumps(item)}\n\n"
            except asyncio.TimeoutError:
                yield ": keep-alive\n\n"

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
app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    public_url = os.environ.get("AGENT_URL", f"http://localhost:{port}/")
    
    # Build the A2A app
    a2a_app = build_a2a_host(public_url)
    
    # Combined application routing
    from starlette.applications import Starlette
    from starlette.routing import Mount, Route
    from starlette.responses import RedirectResponse
    
    # Order matters: more specific routes first
    combined_app = Starlette(
        routes=[
            Mount("/api", app), # FastAPI endpoints
            Mount("/ui", StaticFiles(directory=ui_dir, html=True)), # Static UI files
            # Root GET redirects to UI
            Route("/", endpoint=lambda r: RedirectResponse(url="/ui/"), methods=["GET"]),
            # A2A handles everything else (POST to /, GET to /.well-known/...)
            Mount("/", a2a_app),
        ]
    )

    print(f"Starting Registry-Ready Orchestrator on port {port}...")
    uvicorn.run(combined_app, host="0.0.0.0", port=port)
