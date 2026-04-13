# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import uvicorn
from typing import Optional
from fastapi import FastAPI, Form, File, UploadFile, Request
from fastapi.staticfiles import StaticFiles
import stripe
import re

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

def render_cart_ui(cart, payment_link=None):
    cards = []
    
    # Add a header card
    cards.append({
        "Card": {
            "children": [
                {
                    "Text": {
                        "text": "Your Order" if not payment_link else "Order Summary",
                        "style": "title"
                    }
                }
            ]
        }
    })
    
    # Add a card for each item
    for item in cart:
        img_url = item.get("img_url", "https://via.placeholder.com/300x200?text=No+Image")
        cards.append({
            "Card": {
                "children": [
                    {
                        "Image": {
                            "src": img_url,
                            "alt": item["name"]
                        }
                    },
                    {
                        "Text": {
                            "text": item["name"],
                            "style": "title"
                        }
                    },
                    {
                        "Text": {
                            "text": f"${item['price']:.2f}",
                            "style": "subtitle"
                        }
                    }
                ]
            }
        })
        
    # Add a total card
    total = sum(item['price'] for item in cart)
    
    total_children = [
        {
            "Text": {
                "text": f"Total: ${total:.2f}",
                "style": "title"
            }
        }
    ]
    
    if payment_link:
        total_children.append({
            "Text": {
                "text": f'<a href="{payment_link}" class="stripe-pay-btn" style="display: inline-block; background: #6772e5; color: white; padding: 0.5rem 1rem; border-radius: 4px; text-decoration: none; text-align: center; width: 100%; box-sizing: border-box; margin-top: 0.5rem; font-weight: bold;">Pay Now with Stripe 💳</a>',
                "style": "body"
            }
        })
    else:
        # Add Checkout button
        total_children.append({
            "Button": {
                "child": {
                    "Text": {
                        "text": "Go to Checkout 🛒"
                    }
                },
                "action": {
                    "command": "send_message",
                    "params": {
                        "message": "Checkout"
                    }
                }
            }
        })
        
    cards.append({
        "Card": {
            "children": total_children
        }
    })
    
    return {
        "beginRendering": {
            "surfaceId": "cart-summary",
            "content": {
                "Column": {
                    "children": cards
                }
            }
        }
    }

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
    print(f"DEBUG: /api/chat received prompt='{prompt}', persona='{persona}', session_id='{session_id}'")
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
    if prompt and prompt.lower().strip() in ["show scenarios", "show my scenarios", "here are some scenarios", "what can i do", "what can i do?", "show scenarios?", "help"]:
        if persona == "adam":
            return {
                "status": "success",
                "a2ui_data": {
                    "beginRendering": {
                        "surfaceId": "scenario-options",
                        "content": {
                            "Row": {
                                "children": [
                                    {
                                        "Card": {
                                            "children": [
                                                {
                                                    "Image": {
                                                        "src": "/images/gemini_backpack.png",
                                                        "alt": "Reference Backpack"
                                                    }
                                                },
                                                {
                                                    "Button": {
                                                        "child": {"Text": {"text": "I want something similar ($150)"}},
                                                        "action": {
                                                            "command": "send_message",
                                                            "params": {
                                                                "message": "![backpack](/images/gemini_backpack.png) <!-- Use find_similar_items with item_id m54421969413 and filter on price less than $150 -->",
                                                                "display_message": "I am looking for a backpack similar to this image"
                                                            }
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    },
                                    {
                                        "Card": {
                                            "children": [
                                                {
                                                    "Image": {
                                                        "src": "/images/commute_bike.png",
                                                        "alt": "Commuter Bike"
                                                    }
                                                },
                                                {
                                                    "Button": {
                                                        "child": {"Text": {"text": "Bicycle Gear ($300)"}},
                                                        "action": {
                                                            "command": "send_message",
                                                            "params": {
                                                                "message": "Create a plan for mens bicycle accessories. Budget: $300",
                                                                "display_message": "Bicycle Gear ($300)"
                                                            }
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    },
                                    {
                                        "Card": {
                                            "children": [
                                                {
                                                    "Image": {
                                                        "src": "/images/expedition_gear.png",
                                                        "alt": "Expedition Gear"
                                                    }
                                                },
                                                {
                                                    "Button": {
                                                        "child": {"Text": {"text": "Expedition Prep ($500)"}},
                                                        "action": {
                                                            "command": "send_message",
                                                            "params": {
                                                                "message": "Durable gear for a hiking expedition. Budget: $500",
                                                                "display_message": "Expedition Prep ($500)"
                                                            }
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    },
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
                                        "Card": {
                                            "children": [
                                                {
                                                    "Image": {
                                                        "src": "/images/necklace.avif",
                                                        "alt": "Music Festival Necklace"
                                                    }
                                                },
                                                {
                                                    "Button": {
                                                        "child": {"Text": {"text": "I want something similar ($100)"}},
                                                        "action": {
                                                            "command": "send_message",
                                                            "params": {
                                                                "message": "![necklace](/images/necklace.avif) <!-- Use find_similar_items with item_id m94504397053 and filter on price less than $100 -->",
                                                                "display_message": "I am looking for a necklace similar to this image"
                                                            }
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    },
                                    {
                                        "Card": {
                                            "children": [
                                                {
                                                    "Image": {
                                                        "src": "/images/art_supplies.png",
                                                        "alt": "Art Studio Supplies"
                                                    }
                                                },
                                                {
                                                    "Button": {
                                                        "child": {"Text": {"text": "Art Studio Supplies ($150)"}},
                                                        "action": {
                                                            "command": "send_message",
                                                            "params": {
                                                                "message": "Supplies for my art studio. Budget: $150",
                                                                "display_message": "Art Studio Supplies ($150)"
                                                            }
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    },
                                    {
                                        "Card": {
                                            "children": [
                                                {
                                                    "Image": {
                                                        "src": "/images/aesthetic_tech.png",
                                                        "alt": "Aesthetic Tech"
                                                    }
                                                },
                                                {
                                                    "Button": {
                                                        "child": {"Text": {"text": "Aesthetic Tech ($200)"}},
                                                        "action": {
                                                            "command": "send_message",
                                                            "params": {
                                                                "message": "Desk accessories and tech. Budget: $200",
                                                                "display_message": "Aesthetic Tech ($200)"
                                                            }
                                                        }
                                                    }
                                                }
                                            ]
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
                                        "Card": {
                                            "children": [
                                                {
                                                    "Image": {
                                                        "src": "/images/business_casual.png",
                                                        "alt": "Business Casual Wardrobe"
                                                    }
                                                },
                                                {
                                                    "Button": {
                                                        "child": {"Text": {"text": "Business Casual Wardrobe ($800)"}},
                                                        "action": {
                                                            "command": "send_message",
                                                            "params": {
                                                                "message": "Business casual capsule wardrobe. Budget: $800",
                                                                "display_message": "Business Casual Wardrobe ($800)"
                                                            }
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    },
                                    {
                                        "Card": {
                                            "children": [
                                                {
                                                    "Image": {
                                                        "src": "/images/corporate_gala.png",
                                                        "alt": "Corporate Gala"
                                                    }
                                                },
                                                {
                                                    "Button": {
                                                        "child": {"Text": {"text": "Corporate Gala ($300)"}},
                                                        "action": {
                                                            "command": "send_message",
                                                            "params": {
                                                                "message": "Elegant dress for a corporate gala. Budget: $300",
                                                                "display_message": "Corporate Gala ($300)"
                                                            }
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    },
                                    {
                                        "Card": {
                                            "children": [
                                                {
                                                    "Image": {
                                                        "src": "/images/leather_journal.avif",
                                                        "alt": "Leather Journal"
                                                    }
                                                },
                                                {
                                                    "Button": {
                                                        "child": {"Text": {"text": "I want something similar ($50)"}},
                                                        "action": {
                                                            "command": "send_message",
                                                            "params": {
                                                                "message": "![journal](/images/leather_journal.avif) <!-- Use find_similar_items with item_id m85493857344 and filter on price less than $50 -->",
                                                                "display_message": "I am looking for a vintage leather journal similar to this image"
                                                            }
                                                        }
                                                    }
                                                }
                                            ]
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
        elif event.content and not node_name.startswith("planner_"):
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
        if found_options:
            print("\n--- 🔍 SEARCH RESULTS IDS 🔍 ---")
            for group in found_options:
                for item in group.get("options", []):
                    print(f"ID: {item.get('id')} | Name: {item.get('name')}")
            print("---------------------------------\n")

    response_data = {"status": "success"}
    
    proposed_plan_ui = session.state.get("proposed_plan_ui")
    
    if found_options:
        # Use A2UI view to render products
        response_data["a2ui_data"] = render_search_ui(found_options, persona)
    elif proposed_plan_ui and session.state.get("awaiting_approval"):
        response_data["a2ui_data"] = proposed_plan_ui
    elif "stripe.com" in reply_text:
        # Render checkout UI
        cart = session.state.get("agent_cart", [])
        match = re.search(r'(https://[a-zA-Z0-9.-]*stripe\.com/[^\s]+)', reply_text)
        payment_link = match.group(1) if match else ""
        
        if cart and payment_link:
            response_data["a2ui_data"] = render_cart_ui(cart, payment_link)
            # Replace reply_text with a cleaner message
            reply_text = "Your order is ready! Here is a summary and payment link:"

    if reply_text and not found_options:
        # Clean up blank lines
        reply_text = reply_text.replace('\n\n', '\n')
        
        # Remove system speaker identification leak
        reply_text = re.sub(r'You are an agent\. Your internal name is "[^"]*"\.', '', reply_text)
        
        # Cart summary rendering on every add has been removed to avoid clutter.
        # It will now only be shown during final checkout.
                    
        response_data["reply"] = reply_text.strip()
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
        
        print(f"DEBUG: Creating Stripe session with line_items: {line_items}")
        
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

@app.get("/api/clear-cart")
async def clear_cart():
    from agents.agent import GLOBAL_CART
    GLOBAL_CART.clear()
    print("DEBUG: Cart cleared on server.")
    return {"status": "success", "message": "Cart cleared"}

# Mount images directory
app.mount("/images", StaticFiles(directory="images"), name="images")

# Mount static files at root (Mount this LAST)
app.mount("/", StaticFiles(directory="ui", html=True), name="ui")

if __name__ == "__main__":
    # Use port 8080 to avoid clashing with 'adk web' if it's on 8000
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting server on port {port}...")
    uvicorn.run(app, host="0.0.0.0", port=port)
