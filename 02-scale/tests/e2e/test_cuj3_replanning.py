"""E2E Test for CUJ 3: Cross-Framework Error Handling / Re-planning.

This test simulates the ADK 2.0 Control Room handling a failure from the
A2A server. It verifies that the dynamic graph transitions to the
replanner_agent, rewrites the objective, and retries the delegation.
"""

import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from agents.control_room.agent import ControlRoomAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

# Skip if no real GCP project is configured, as the replanner LLM requires it.
_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
pytestmark = pytest.mark.skipif(
    not _project or _project == "test-project-id",
    reason="E2E tests require a real GOOGLE_CLOUD_PROJECT",
)

@pytest.mark.asyncio
async def test_control_room_replanning():
    """CUJ 3: ADK 2.0 Control Room dynamic re-planning on error."""

    runner = InMemoryRunner(
        app_name="test_app",
        agent=ControlRoomAgent,
    )

    session = await runner.session_service.create_session(
        app_name="test_app", user_id="admin"
    )

    initial_prompt = "Order 5 units of 'Extremely Rare Discontinued Ghost Mug'"
    content = types.Content(role='user', parts=[types.Part.from_text(text=initial_prompt)])

    # We mock the A2A server connection so we can simulate the "ItemNotFound" error
    # without needing the live Uvicorn + CrewAI server running.
    with patch("httpx.AsyncClient.post") as mock_post:
        # 1st attempt: Simulate A2A returning a "not found" error.
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 200
        mock_response_fail.json.return_value = {
            "result": {
                "artifacts": [{"parts": [{"text": "Status: FAILED. Reason: The item was discontinued and not found."}]}]
            }
        }

        # 2nd attempt: Simulate A2A succeeding with the broadened search.
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "result": {
                "artifacts": [{"parts": [{"text": "Status: SUCCESS. PO-12345 generated for broader search."}]}]
            }
        }

        # mock_post is an AsyncMock that returns MagicMocks when awaited
        mock_post.side_effect = [mock_response_fail, mock_response_success]
        
        # Execute the workflow
        async for event in runner.run_async(
            user_id="admin",
            session_id=session.id,
            new_message=content,
        ):
            pass # Exhaust generator
            
        final_session = await runner.session_service.get_session(
            app_name="test_app", user_id="admin", session_id=session.id
        )
        
        outcome = final_session.state.get("final_outcome", "")
        
        # Assertions
        assert mock_post.call_count == 2, "Workflow should have retried the A2A call after failing."
        assert "SUCCESS" in outcome, "The workflow should have ultimately succeeded."
        
        # Verify the prompt sent in the second attempt was broadened by the LLM
        first_call_payload = mock_post.call_args_list[0][1]["json"]
        second_call_payload = mock_post.call_args_list[1][1]["json"]
        
        first_text = first_call_payload["params"]["message"]["parts"][0]["text"]
        second_text = second_call_payload["params"]["message"]["parts"][0]["text"]
        
        assert first_text == initial_prompt, "First call should use the initial prompt."
        assert second_text != initial_prompt, "Second call should use the re-planned (broadened) prompt."
        assert "Extremely Rare Discontinued" not in second_text or len(second_text) != len(initial_prompt), "Re-planner LLM should have modified the text."
