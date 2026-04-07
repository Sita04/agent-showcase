import asyncio
from google.adk.runners import InMemoryRunner
from google.genai import types
from agent import ControlRoomAgent

async def run_demo():
    prompt = "Inventory Alert: Northeast Region is critically low on 'Rare Japanese Anime Figure'. Please order 2 units ASAP. Max budget $50 per unit."
    
    print("="*60)
    print("🏢 STARTING ADK 2.0 CONTROL ROOM AGENT")
    print("="*60)
    
    runner = InMemoryRunner(
        app_name="control_room_app",
        agent=ControlRoomAgent,
    )
    
    session = await runner.session_service.create_session(
        app_name="control_room_app", user_id="admin"
    )

    content = types.Content(role='user', parts=[types.Part.from_text(text=prompt)])
    
    async for event in runner.run_async(
        user_id="admin",
        session_id=session.id,
        new_message=content,
    ):
        pass
        
    final_session = await runner.session_service.get_session(
        app_name="control_room_app", user_id="admin", session_id=session.id
    )
    print("\n" + "="*60)
    print("🏁 FINAL WORKFLOW STATE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_demo())
