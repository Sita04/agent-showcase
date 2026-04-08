import os
import uvicorn
import sys
from typing import Optional
from fastapi import FastAPI, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# Ensure we can import from agents/
sys.path.append(os.path.join(os.path.dirname(__file__), "agents"))

# Load .env
load_dotenv()

from google.adk.runners import InMemoryRunner
from google.adk.sessions import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.genai.types import Content as GenAIContent, Part as GenAIPart

from agents.control_room.agent import ControlRoomAgent

app = FastAPI(title="Scale Agents Control Room Dashboard")

# Persistent runner
_runner = InMemoryRunner(
    agent=ControlRoomAgent,
    app_name="control_room_app",
)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "FastAPI is running"}

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
    
    events = []
    # Run the workflow and collect outputs
    async for event in _runner.run_async(
        session_id=session_id,
        user_id=user_id,
        new_message=new_message
    ):
        event_data = {
            "type": type(event).__name__,
            "node_name": getattr(event, 'node_name', 'N/A'),
            "output": getattr(event, 'output', None),
        }
        events.append(event_data)
        print(f"[DEBUG] Event: {event_data}")

    # Read session state to see final outcome
    session = await _runner.session_service.get_session(
        app_name="control_room_app",
        user_id=user_id,
        session_id=session_id
    )
    
    final_outcome = session.state.get("final_outcome", "Workflow completed.")

    return {
        "status": "success",
        "final_outcome": final_outcome,
        "events": events
    }

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
