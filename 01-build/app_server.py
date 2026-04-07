import os
import uvicorn
from typing import Optional
from fastapi import FastAPI, Form, File, UploadFile
from fastapi.staticfiles import StaticFiles

# Helper to load .env manually since python-dotenv might not be available
def load_env():
    # Try finding .env in agents/ folder or workspace root
    paths = ["agents/.env", "../../.env"]
    for env_path in paths:
        if os.path.exists(env_path):
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        if "=" in line:
                            key, val = line.split("=", 1)
                            os.environ[key.strip()] = val.strip().strip('"').strip("'")
            print(f"Loaded environment from {env_path}")
            break # Prioritize the first one found

load_env()

from google.adk.runners import Runner

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.genai.types import Content as GenAIContent, Part as GenAIPart

from agents.agent import root_agent

app = FastAPI(title="Shopping Squad UI")

# Persistent services for run isolation
_session_service = InMemorySessionService()
_runner = Runner(
    agent=root_agent,
    app_name="shopping_squad",
    session_service=_session_service,
    memory_service=InMemoryMemoryService(),
    auto_create_session=True
)

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "FastAPI is running"}

@app.post("/api/chat")
async def chat(prompt: Optional[str] = Form(None), image: Optional[UploadFile] = File(None)):
    session_id = "demo_session_1"
    user_id = "demo_user_1"
    
    parts = []
    if prompt:
        parts.append(GenAIPart.from_text(text=prompt))
    if image:
        image_bytes = await image.read()
        parts.append(GenAIPart.from_bytes(data=image_bytes, mime_type=image.content_type))
        
    if not parts:
        return {"status": "error", "reply": "Empty message received"}

    new_message = GenAIContent(role="user", parts=parts)
    
    reply_text = ""
    # Run the workflow and collect outputs
    success_triggered = False
    async for event in _runner.run_async(
        session_id=session_id,
        user_id=user_id,
        new_message=new_message
    ):
        # Clean debug logs
        print(f"\n[DEBUG] Event: {type(event)} | Node: {getattr(event, 'node_name', 'N/A')}")
        
        # Check event.output which holds the text for speaker agents
        output_data = getattr(event, 'output', None)
        node_name = getattr(event, 'node_name', '')
        
        if node_name.startswith("sys_speaker_success_"):
            success_triggered = True
            
        if node_name.startswith("sys_speaker_") and isinstance(output_data, str):
            reply_text += output_data
        elif event.content:
            # Fallback for other text events
            for p in event.content.parts:
                txt = p.get('text') if isinstance(p, dict) else getattr(p, 'text', '')
                if txt:
                    reply_text += txt

    # Read session state to see if sub-agents found anything
    session = await _runner.session_service.get_session(
        app_name="shopping_squad",
        user_id=user_id,
        session_id=session_id
    )
    
    # Only attach product cards if the search JUST completed successfully!
    found_options = []
    if success_triggered:
        found_options = session.state.get("found_options", [])

    response_data = {"status": "success"}
    if found_options:
        response_data["found_options"] = found_options

    if reply_text:
        response_data["reply"] = reply_text
    elif not found_options:
        response_data["reply"] = "Processing... check terminal logs."

    return response_data


# Mount static files at root (Mount this LAST)
app.mount("/", StaticFiles(directory="ui", html=True), name="ui")

if __name__ == "__main__":
    # Use port 8080 to avoid clashing with 'adk web' if it's on 8000
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
