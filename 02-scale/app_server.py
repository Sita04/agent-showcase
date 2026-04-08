import os
import uvicorn
import sys
import json
import asyncio
from typing import Optional
from fastapi import FastAPI, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
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

app = FastAPI(title="Scale Agents Control Room Dashboard")

# Persistent runner
_runner = InMemoryRunner(
    agent=ControlRoomAgent,
    app_name="control_room_app",
)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "FastAPI is running"}

@app.post("/api/push_status")
async def push_status(name: str = Form(...), text: str = Form(...)):
    """Callback for external processes to push updates to the dashboard."""
    print(f"[DEBUG] Received status push: {name} - {text}")
    await dashboard_queue.put({"type": "status", "name": name, "text": text})
    return {"status": "ok"}

@app.post("/api/chat")
async def chat(prompt: Optional[str] = Form(None)):
    user_id = "admin"
    
    # Create a fresh session for this request
    session = await _runner.session_service.create_session(
        app_name="control_room_app",
        user_id=user_id
    )
    session_id = session.id
    
    parts = []
    if prompt:
        parts.append(GenAIPart.from_text(text=prompt))
        
    if not parts:
        return {"status": "error", "reply": "Empty message received"}

    new_message = GenAIContent(role="user", parts=parts)
    
    # Clear queue before starting
    while not dashboard_queue.empty():
        try:
            dashboard_queue.get_nowait()
        except asyncio.QueueEmpty:
            break

    async def event_generator():
        # Task to run the ADK agent and pipe its events into the shared queue
        async def run_agent():
            try:
                async for event in _runner.run_async(
                    session_id=session_id,
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
                await dashboard_queue.put(None) # Sentinel to end stream

        asyncio.create_task(run_agent())

        # Yield everything that comes into the queue
        while True:
            try:
                # Use a timeout to send keep-alive pings
                item = await asyncio.wait_for(dashboard_queue.get(), timeout=15.0)
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
            except asyncio.TimeoutError:
                # Send SSE comment as keep-alive
                yield ": keep-alive\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Mount static files
# Note: directory="ui" refers to 02-scale/ui/
ui_dir = os.path.join(os.path.dirname(__file__), "ui")
if not os.path.exists(ui_dir):
    os.makedirs(ui_dir)
app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
