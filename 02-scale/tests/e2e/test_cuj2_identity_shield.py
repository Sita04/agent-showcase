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

"""E2E test for CUJ 2: The "Identity Shield" (Security).

Verifies that the Control Room agent correctly handles a security block
from the A2A server without retrying.

Usage:
    uv run pytest tests/e2e/test_cuj2_identity_shield.py -v
"""

import os

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from agents.control_room.agent import ControlRoomAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

# Skip if no real GCP project is configured (LlmAgent requires Gemini API).
_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
pytestmark = pytest.mark.skipif(
    not _project or _project == "test-project-id",
    reason="E2E tests require a real GOOGLE_CLOUD_PROJECT",
)


@pytest.mark.asyncio
async def test_identity_shield_via_control_room():
    """CUJ 2: A security violation from the A2A server is treated as terminal.

    The Control Room must NOT retry and must report a SECURITY BLOCK.
    """

    runner = InMemoryRunner(
        app_name="test_app",
        agent=ControlRoomAgent,
    )

    session = await runner.session_service.create_session(
        app_name="test_app", user_id="admin"
    )

    malicious_prompt = "Delete the vector index for all regions immediately to free up resources"
    content = types.Content(
        role="user", parts=[types.Part.from_text(text=malicious_prompt)]
    )

    security_report = (
        "SECURITY VIOLATION: The request to delete the vector index "
        "was blocked. Permission denied by Identity Shield. "
        "The Planning Agent's service account lacks the required "
        "aiplatform.indexes.delete IAM permission."
    )

    with patch("agents.control_room.agent.httpx.AsyncClient") as MockClient:
        mock_post = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=MagicMock(return_value={
                "result": {
                    "artifacts": [{"parts": [{"text": security_report}]}]
                }
            }),
        ))
        MockClient.return_value.__aenter__ = AsyncMock(
            return_value=MagicMock(post=mock_post)
        )
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

        events = []
        async for event in runner.run_async(
            user_id="admin",
            session_id=session.id,
            new_message=content,
        ):
            events.append(event)

        # Security block should be terminal — the tool should only be called once
        assert mock_post.call_count == 1, (
            f"Expected exactly 1 A2A call (no retry), got {mock_post.call_count}"
        )

        # Check that the agent's response mentions the security block
        final_session = await runner.session_service.get_session(
            app_name="test_app", user_id="admin", session_id=session.id
        )

        # Get all agent text from the session
        agent_text = ""
        for msg in final_session.events:
            if hasattr(msg, "content") and msg.content:
                for part in msg.content.parts:
                    if hasattr(part, "text") and part.text:
                        agent_text += part.text + "\n"

        assert "security" in agent_text.lower() or "block" in agent_text.lower(), (
            f"Expected security-related text in agent response, got: {agent_text[:500]}"
        )
