import os
import uvicorn
from typing import Optional
from fastapi import FastAPI, Form, File, UploadFile, Request
from fastapi.staticfiles import StaticFiles
import stripe

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
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.genai.types import Content as GenAIContent, Part as GenAIPart

from agents.agent import root_agent
from agents.views.search import render_search_ui

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
async def chat(prompt: Optional[str] = Form(None), image: Optional[UploadFile] = File(None), persona: Optional[str] = Form(None), session_id: Optional[str] = Form(None)):
    if not session_id:
        session_id = "demo_session_1"
    user_id = "demo_user_1"
    
    parts = []
    
    full_prompt = prompt or ""
    if persona and persona != "none":
        full_prompt = f"[User Persona: {persona}] {full_prompt}".strip()
        
    if full_prompt:
        parts.append(GenAIPart.from_text(text=full_prompt))
    if image:
        image_bytes = await image.read()
        parts.append(GenAIPart.from_bytes(data=image_bytes, mime_type=image.content_type))
        
    if not parts:
        return {"status": "error", "reply": "Empty message received"}

    new_message = GenAIContent(role="user", parts=parts)
    
    # Intercept scenario requests
    if prompt in ["Show scenarios", "Show my scenarios", "Here are some scenarios"]:
        if persona == "adam":
            return {
                "status": "success",
                "a2ui_data": {
                    "beginRendering": {
                        "surfaceId": "scenario-options",
                        "content": {
                            "Column": {
                                "children": [
                                    {
                                        "Button": {
                                            "child": {"Text": {"text": "Solo Yosemite Trip ($600)"}},
                                            "action": {
                                                "command": "send_message",
                                                "params": {"message": "Solo backpacking trip to Yosemite. Budget: $600"}
                                            }
                                        }
                                    },
                                    {
                                        "Button": {
                                            "child": {"Text": {"text": "Daily Bicycle Commute ($300)"}},
                                            "action": {
                                                "command": "send_message",
                                                "params": {"message": "Upgrade daily bicycle commute gear. Budget: $300"}
                                            }
                                        }
                                    },
                                    {
                                        "Button": {
                                            "child": {"Text": {"text": "Expedition Prep ($1200)"}},
                                            "action": {
                                                "command": "send_message",
                                                "params": {"message": "Durable gear for a hiking expedition. Budget: $1200"}
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        elif persona == "lucy":
            return {
                "status": "success",
                "a2ui_data": {
                    "beginRendering": {
                        "surfaceId": "scenario-options",
                        "content": {
                            "Column": {
                                "children": [
                                    {
                                        "Button": {
                                            "child": {"Text": {"text": "Music Festival Tech ($250)"}},
                                            "action": {
                                                "command": "send_message",
                                                "params": {"message": "Aesthetic tech for a music festival. Budget: $250"}
                                            }
                                        }
                                    },
                                    {
                                        "Button": {
                                            "child": {"Text": {"text": "Art Studio Supplies ($150)"}},
                                            "action": {
                                                "command": "send_message",
                                                "params": {"message": "Supplies for my art studio. Budget: $150"}
                                            }
                                        }
                                    },
                                    {
                                        "Button": {
                                            "child": {"Text": {"text": "Aesthetic Tech ($200)"}},
                                            "action": {
                                                "command": "send_message",
                                                "params": {"message": "Desk accessories and tech. Budget: $200"}
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        elif persona == "elena":
            return {
                "status": "success",
                "a2ui_data": {
                    "beginRendering": {
                        "surfaceId": "scenario-options",
                        "content": {
                            "Column": {
                                "children": [
                                    {
                                        "Button": {
                                            "child": {"Text": {"text": "Business Casual Wardrobe ($800)"}},
                                            "action": {
                                                "command": "send_message",
                                                "params": {"message": "Business casual capsule wardrobe. Budget: $800"}
                                            }
                                        }
                                    },
                                    {
                                        "Button": {
                                            "child": {"Text": {"text": "Corporate Gala ($300)"}},
                                            "action": {
                                                "command": "send_message",
                                                "params": {"message": "Elegant dress for a corporate gala. Budget: $300"}
                                            }
                                        }
                                    },
                                    {
                                        "Button": {
                                            "child": {"Text": {"text": "Weekend Getaway ($400)"}},
                                            "action": {
                                                "command": "send_message",
                                                "params": {"message": "Casual chic outfits for a weekend getaway. Budget: $400"}
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        else:
            return {
                "status": "success",
                "reply": "Please select a persona to see scenarios."
            }

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
                    # Ignore system status messages
                    if txt.strip().lower().startswith("status:"):
                        continue
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
    
    proposed_plan_ui = session.state.get("proposed_plan_ui")
    
    if found_options:
        # Use A2UI view to render products
        response_data["a2ui_data"] = render_search_ui(found_options, persona)
    elif proposed_plan_ui:
        response_data["a2ui_data"] = proposed_plan_ui

    if reply_text and not found_options:
        response_data["reply"] = reply_text
    elif not found_options:
        response_data["reply"] = ""

    return response_data


from pydantic import BaseModel
from typing import List

class CartItem(BaseModel):
    sku: str
    name: str
    price: float
    imgSrc: Optional[str] = None

@app.post("/api/cart")
async def cart_action(action: str = Form(...), sku: str = Form(...)):
    # This endpoint handles cart actions silently without involving the ADK workflow.
    return {"status": "success", "message": f"Action {action} for SKU {sku} processed"}

@app.post("/api/reset")
async def reset_session():
    session_id = "demo_session_1"
    user_id = "demo_user_1"
    session = await _runner.session_service.get_session(
        app_name="shopping_squad",
        user_id=user_id,
        session_id=session_id
    )
    if session:
        session.state.clear()
    return {"status": "success", "message": "Session cleared"}

@app.post("/api/create-checkout-session")
async def create_checkout_session(items: List[CartItem], request: Request):
    try:
        line_items = []
        from collections import defaultdict
        grouped = defaultdict(lambda: {"name": "", "price": 0.0, "quantity": 0})
        
        for item in items:
            grouped[item.sku]["name"] = item.name
            grouped[item.sku]["price"] = item.price
            grouped[item.sku]["quantity"] += 1
            
        for sku, data in grouped.items():
            line_items.append({
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": data["name"],
                    },
                    "unit_amount": int(data["price"] * 100),
                },
                "quantity": data["quantity"],
            })
            
        origin = request.headers.get("origin") or "http://localhost:8080"
        
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=line_items,
            mode="payment",
            success_url=f"{origin}/?success=true",
            cancel_url=f"{origin}/?canceled=true",
        )
        return {"url": session.url}
    except Exception as e:
        print(f"Error creating stripe session: {e}")
        return {"error": str(e)}, 400

# Mount static files at root (Mount this LAST)
app.mount("/", StaticFiles(directory="ui", html=True), name="ui")

if __name__ == "__main__":
    # Use port 8080 to avoid clashing with 'adk web' if it's on 8000
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)