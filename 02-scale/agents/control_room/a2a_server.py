import asyncio
import json
import os
import sys
import click
import uvicorn
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (AgentCapabilities, AgentCard, AgentSkill, InternalError,
                       InvalidParamsError, Part, TextPart,
                       UnsupportedOperationError)
from a2a.utils import new_task
from a2a.utils.errors import ServerError

from google.adk.runners import InMemoryRunner
from google.genai.types import Content as GenAIContent, Part as GenAIPart

load_dotenv()


class ControlRoomAgentExecutor(AgentExecutor):
    """Wraps the Control Room ADK Workflow as an A2A executor.

    Insulates the dashboard from `google-cloud-aiplatform` SDK churn: the
    dashboard talks JSON-RPC over A2A, and the bridge owns the SDK-side
    plumbing (today: in-process via InMemoryRunner; future: optionally
    forward to an AE-hosted engine).
    """

    SUPPORTED_CONTENT_TYPES = ["text", "text/plain"]

    def __init__(self):
        super().__init__()
        from agents.control_room.agent import ControlRoomAgent
        self._runner = InMemoryRunner(
            agent=ControlRoomAgent,
            app_name="control_room_app",
        )

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        objective = context.get_user_input()
        if not objective:
            raise ServerError(error=InvalidParamsError(message="User query (objective) cannot be empty."))

        task = context.current_task or new_task(context.message)
        await event_queue.enqueue_event(task)
        updater = TaskUpdater(event_queue, task.id, task.context_id)

        # Recover the dashboard session id from A2A Message.metadata so
        # emit_status / emit_final_report on the workflow side can route
        # pushes back to the right tab via /api/push_status. Mirrors the
        # pattern PlannerAgentExecutor uses.
        sid = ""
        try:
            metadata = getattr(context.message, "metadata", None) or {}
            if isinstance(metadata, dict):
                sid = str(metadata.get("session_id", "") or "")
        except Exception:
            pass
        from agents.control_room.agent import current_session_id as _cr_session_id
        _cr_session_id.set(sid)

        user_id = "admin"
        try:
            print(f"\n🚀 [Control Room A2A] objective='{objective}' (sid={sid})")
            session = await self._runner.session_service.create_session(
                app_name="control_room_app", user_id=user_id,
            )
            new_message = GenAIContent(role="user", parts=[GenAIPart.from_text(text=objective)])

            final_report = "Execution failed."
            final_status = "Failed"
            async for event in self._runner.run_async(
                session_id=session.id, user_id=user_id, new_message=new_message,
            ):
                output = getattr(event, "output", None)
                if isinstance(output, dict):
                    if "report" in output:
                        final_report = output["report"]
                    if "status" in output:
                        final_status = output["status"]
                elif isinstance(output, str):
                    final_report = output

            # Wrap the workflow result in the same JSON envelope
            # emit_final_report uses, so callers that already parse that
            # shape (the dashboard) get one consistent representation.
            payload = json.dumps({"status": final_status, "report": final_report})
            await updater.add_artifact(
                [Part(root=TextPart(text=payload))], name="orchestration_report",
            )
            await updater.complete()
            print(f"✅ [Control Room A2A] complete status={final_status}")

        except asyncio.CancelledError:
            try:
                await updater.failed()
            except Exception:
                pass
            raise
        except Exception as e:
            print(f"❌ [Control Room A2A] {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            try:
                await updater.failed()
            except Exception:
                pass
            raise ServerError(
                error=InternalError(message=f"Control Room execution failed: {type(e).__name__}")
            ) from e

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        raise ServerError(error=UnsupportedOperationError())


@click.command()
def main():
    host = "0.0.0.0"
    port = int(os.environ.get("PORT", 8082))
    public_url = os.environ.get("CONTROL_ROOM_AGENT_URL", f"http://localhost:{port}/")

    async def start_server():
        agent_card = AgentCard(
            name="Global-Retail-Orchestrator-A2A",
            description="ADK 2.0 Control Room Workflow exposed via A2A JSON-RPC. Coordinates planning + execution.",
            url=public_url,
            version="1.0.0",
            default_input_modes=ControlRoomAgentExecutor.SUPPORTED_CONTENT_TYPES,
            default_output_modes=ControlRoomAgentExecutor.SUPPORTED_CONTENT_TYPES,
            capabilities=AgentCapabilities(streaming=True),
            skills=[
                AgentSkill(
                    id="orchestrate_logistics",
                    name="Orchestrate Logistics",
                    description="Receives a procurement objective and runs the full ADK Workflow (Planner -> Executor) end-to-end.",
                    tags=["logistics", "retail", "orchestration", "control-room"],
                    examples=[
                        "Restock 2 Google Droid figures for the Tokyo office",
                    ],
                ),
            ],
        )
        executor = ControlRoomAgentExecutor()
        handler = DefaultRequestHandler(agent_executor=executor, task_store=InMemoryTaskStore())
        server = A2AStarletteApplication(agent_card=agent_card, http_handler=handler)
        print(f"Starting Control Room A2A server at {public_url}")
        config = uvicorn.Config(server.build(), host=host, port=port)
        await uvicorn.Server(config).serve()

    asyncio.run(start_server())


if __name__ == "__main__":
    main()
