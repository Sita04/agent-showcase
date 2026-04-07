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

Verifies that the ADK 2.0 Control Room correctly handles a security block
from the A2A server without triggering the re-planner.

Usage:
    uv run pytest tests/e2e/test_cuj2_identity_shield.py -v
"""

import os

import pytest
from unittest.mock import patch, MagicMock

from agents.control_room.agent import ControlRoomAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

# Skip if no real GCP project is configured (replanner LLM requires it).
_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
pytestmark = pytest.mark.skipif(
    not _project or _project == "test-project-id",
    reason="E2E tests require a real GOOGLE_CLOUD_PROJECT",
)


@pytest.mark.asyncio
async def test_identity_shield_via_control_room():
    """CUJ 2: A security violation from the A2A server is treated as terminal.

    The Control Room must NOT invoke the re-planner agent and must return
    immediately with a SECURITY BLOCK outcome.
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

    with patch("httpx.AsyncClient.post") as mock_post:
        # Simulate the A2A server returning a security violation report
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "artifacts": [
                    {
                        "parts": [
                            {
                                "text": (
                                    "SECURITY VIOLATION: The request to delete the vector index "
                                    "was blocked. Permission denied by Identity Shield. "
                                    "The Planning Agent's service account lacks the required "
                                    "aiplatform.indexes.delete IAM permission."
                                )
                            }
                        ]
                    }
                ]
            }
        }
        mock_post.return_value = mock_response

        # Execute the workflow
        async for event in runner.run_async(
            user_id="admin",
            session_id=session.id,
            new_message=content,
        ):
            pass  # Exhaust generator

        final_session = await runner.session_service.get_session(
            app_name="test_app", user_id="admin", session_id=session.id
        )

        outcome = final_session.state.get("final_outcome", "")

        # Security block should be terminal — no retry
        assert mock_post.call_count == 1, (
            f"Expected exactly 1 A2A call (no retry), got {mock_post.call_count}"
        )
        assert "SECURITY BLOCK" in outcome, (
            f"Expected 'SECURITY BLOCK' in outcome, got: {outcome}"
        )
