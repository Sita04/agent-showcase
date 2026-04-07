"""E2E Test for CUJ 3: Cross-Framework Error Handling / Re-planning.

This test simulates the Control Room handling a failure from the A2A server.
It verifies that the LlmAgent retries with a broadened objective when the
first attempt returns a "not found" error.
"""

import os
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from agents.control_room.agent import ControlRoomAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

# Skip if no real GCP project is configured, as the LlmAgent LLM requires it.
_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
pytestmark = pytest.mark.skipif(
    not _project or _project == "test-project-id",
    reason="E2E tests require a real GOOGLE_CLOUD_PROJECT",
)

@pytest.mark.asyncio
async def test_control_room_replanning():
    """CUJ 3: Control Room retries with broadened search after a 'not found' error."""

    runner = InMemoryRunner(
        app_name="test_app",
        agent=ControlRoomAgent,
    )

    session = await runner.session_service.create_session(
        app_name="test_app", user_id="admin"
    )

    initial_prompt = "Order 5 units of 'Extremely Rare Discontinued Ghost Mug'"
    content = types.Content(role='user', parts=[types.Part.from_text(text=initial_prompt)])

    call_count = 0

    async def mock_post_side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            # 1st attempt: "not found" triggers replanning
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "result": {
                    "artifacts": [{"parts": [{"text": "Status: FAILED. Reason: The item was discontinued and not found."}]}]
                }
            }
            return resp
        else:
            # 2nd attempt: success with broadened search
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = {
                "result": {
                    "artifacts": [{"parts": [{"text": "Status: SUCCESS. PO-12345 generated for broader search."}]}]
                }
            }
            return resp

    with patch("agents.control_room.agent.httpx.AsyncClient") as MockClient:
        mock_post = AsyncMock(side_effect=mock_post_side_effect)
        MockClient.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(post=mock_post)
        )
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        async for event in runner.run_async(
            user_id="admin",
            session_id=session.id,
            new_message=content,
        ):
            pass  # Exhaust generator

        # The LLM should have retried after the first "not found" error
        assert mock_post.call_count == 2, (
            f"Expected 2 A2A calls (initial + retry), got {mock_post.call_count}"
        )

        # Verify the second call used a different (broadened) objective
        first_payload = mock_post.call_args_list[0][1]["json"]
        second_payload = mock_post.call_args_list[1][1]["json"]

        first_text = first_payload["params"]["message"]["parts"][0]["text"]
        second_text = second_payload["params"]["message"]["parts"][0]["text"]

        assert second_text != first_text, (
            "Second call should use a broadened/rewritten prompt, not the same one."
        )
