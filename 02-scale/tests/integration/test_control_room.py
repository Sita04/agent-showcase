"""Integration tests for the Control Room Agent.

Tests the delegate_to_planner tool function directly with mocked httpx.
All external dependencies (A2A server) are mocked so tests run without
GCP credentials or a live server.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from agents.control_room.agent import (
    delegate_to_planner,
    ControlRoomAgent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _a2a_response(text: str, status_code: int = 200):
    """Build a mock httpx response with the given artifact text."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {
        "result": {
            "artifacts": [{"parts": [{"text": text}]}],
        }
    }
    return resp


def _a2a_error_response(error_msg: str):
    """Build a mock httpx response with a JSON-RPC error."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"error": {"code": -1, "message": error_msg}}
    return resp


# ---------------------------------------------------------------------------
# Tests: delegate_to_planner tool function
# ---------------------------------------------------------------------------

class TestDelegateToPlannerSuccess:
    """CUJ 1: A2A call succeeds on first attempt."""

    @pytest.mark.asyncio
    async def test_success_returns_report(self):
        with patch("agents.control_room.agent.httpx.AsyncClient") as MockClient:
            mock_post = AsyncMock(return_value=_a2a_response(
                "SUCCESS: PO-999 created for 5x Vintage Mugs. Total $45."
            ))
            MockClient.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=mock_post)
            )
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await delegate_to_planner("Order 5 Vintage Mugs")

        assert result["status"] == "success"
        assert "PO-999" in result["report"]

    @pytest.mark.asyncio
    async def test_empty_artifacts_returns_no_report(self):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"result": {"artifacts": []}}

        with patch("agents.control_room.agent.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=AsyncMock(return_value=resp))
            )
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await delegate_to_planner("Order mugs")

        assert result["status"] == "success"
        assert result["report"] == "No report returned."


class TestDelegateToPlannerSecurityBlock:
    """CUJ 2: Security violations are detected and returned as security_block."""

    @pytest.mark.asyncio
    async def test_permission_denied_detected(self):
        with patch("agents.control_room.agent.httpx.AsyncClient") as MockClient:
            mock_post = AsyncMock(return_value=_a2a_response(
                "SECURITY VIOLATION: Permission denied by Identity Shield."
            ))
            MockClient.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=mock_post)
            )
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await delegate_to_planner("Delete the vector index")

        assert result["status"] == "security_block"
        assert "Permission denied" in result["report"]

    @pytest.mark.asyncio
    async def test_blocked_by_iam_detected(self):
        with patch("agents.control_room.agent.httpx.AsyncClient") as MockClient:
            mock_post = AsyncMock(return_value=_a2a_response(
                "Request blocked by IAM policy enforcement."
            ))
            MockClient.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=mock_post)
            )
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await delegate_to_planner("Drop all indexes")

        assert result["status"] == "security_block"

    @pytest.mark.asyncio
    async def test_identity_shield_detected(self):
        with patch("agents.control_room.agent.httpx.AsyncClient") as MockClient:
            mock_post = AsyncMock(return_value=_a2a_response(
                "Blocked by Identity Shield enforcement layer."
            ))
            MockClient.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=mock_post)
            )
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await delegate_to_planner("Destroy schema")

        assert result["status"] == "security_block"


class TestDelegateToPlannerErrors:
    """Network and protocol error handling."""

    @pytest.mark.asyncio
    async def test_http_error_status(self):
        with patch("agents.control_room.agent.httpx.AsyncClient") as MockClient:
            mock_post = AsyncMock(return_value=_a2a_response("", status_code=500))
            MockClient.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=mock_post)
            )
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await delegate_to_planner("Order mugs")

        assert result["status"] == "error"
        assert "500" in result["report"]

    @pytest.mark.asyncio
    async def test_jsonrpc_error_response(self):
        with patch("agents.control_room.agent.httpx.AsyncClient") as MockClient:
            mock_post = AsyncMock(return_value=_a2a_error_response("Internal error"))
            MockClient.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(post=mock_post)
            )
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await delegate_to_planner("Order mugs")

        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_connection_error(self):
        with patch("agents.control_room.agent.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(
                return_value=MagicMock(
                    post=AsyncMock(side_effect=ConnectionError("refused"))
                )
            )
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await delegate_to_planner("Order mugs")

        assert result["status"] == "error"
        assert "Connection error" in result["report"]


class TestControlRoomAgent:
    """Verify the LlmAgent is configured correctly."""

    def test_agent_name(self):
        assert ControlRoomAgent.name == "ControlRoomAgent"

    def test_agent_has_delegate_tool(self):
        tool_names = [t.__name__ for t in ControlRoomAgent.tools]
        assert "delegate_to_planner" in tool_names
