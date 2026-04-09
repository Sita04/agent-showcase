"""Integration tests for the ADK 2.0 Control Room Agent.

All external dependencies (A2A server, LLM replanner) are mocked so tests
run without GCP credentials or a live server.
"""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock

from agents.control_room.agent import (
    control_room_orchestrator,
    ControlRoomAgent,
    create_replanner_agent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _MockStreamResponse:
    """Minimal async stream response for httpx.AsyncClient.stream tests."""

    def __init__(self, lines, status_code: int = 200):
        self.status_code = status_code
        self._lines = lines

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def aiter_lines(self):
        for line in self._lines:
            yield line


def _a2a_response(text: str, status_code: int = 200):
    """Build a streaming A2A response with the given artifact text."""
    payload = {
        "result": {
            "artifacts": [{"parts": [{"text": text}]}],
        }
    }
    return _MockStreamResponse([json.dumps(payload)], status_code=status_code)


def _a2a_error_response(error_msg: str):
    """Build a streaming response with a JSON-RPC error payload."""
    payload = {"error": {"code": -1, "message": error_msg}}
    return _MockStreamResponse([json.dumps(payload)], status_code=200)


def _mock_ctx(**extra_state):
    """Create a minimal mock Context for the orchestrator node."""
    ctx = MagicMock()
    ctx.state = {}
    ctx.state.update(extra_state)

    async def _fake_run_node(agent, prompt):
        return "Broadened search: collectible mugs"

    ctx.run_node = AsyncMock(side_effect=_fake_run_node)
    return ctx


async def _run_node(ctx, node_input):
    """Run the FunctionNode and return the output from the emitted event."""
    result = None
    async for event in control_room_orchestrator.run(ctx=ctx, node_input=node_input):
        if hasattr(event, "output") and event.output is not None:
            result = event.output
    assert result is not None
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestControlRoomHappyPath:
    """CUJ 1 style: first attempt succeeds."""

    @pytest.mark.asyncio
    async def test_success_on_first_attempt(self):
        ctx = _mock_ctx()
        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.return_value = _a2a_response(
                "SUCCESS: PO-999 created for 5x Vintage Mugs. Total $45."
            )

            result = await _run_node(ctx, "Order 5 Vintage Mugs")

        assert result["status"] == "Success"
        assert "PO-999" in result["report"]
        assert mock_stream.call_count == 1
        assert "SUCCESS" in ctx.state["final_outcome"]

    @pytest.mark.asyncio
    async def test_replanner_not_invoked_on_success(self):
        ctx = _mock_ctx()
        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.return_value = _a2a_response("SUCCESS: PO-001 created.")

            await _run_node(ctx, "Order mugs")

        ctx.run_node.assert_not_called()


class TestControlRoomReplanning:
    """CUJ 3 style: first attempt fails, replanner broadens, second succeeds."""

    @pytest.mark.asyncio
    async def test_replan_on_not_found(self):
        ctx = _mock_ctx()
        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.side_effect = [
                _a2a_response("FAILED: Item not found in vector store."),
                _a2a_response("SUCCESS: PO-555 created for collectible mugs."),
            ]

            result = await _run_node(
                ctx, "Order 5 Extremely Rare Discontinued Ghost Mug"
        )

        assert result["status"] == "Success"
        assert mock_stream.call_count == 2
        ctx.run_node.assert_called_once()

        # Second call should use the broadened objective from the replanner
        second_payload = mock_stream.call_args_list[1][1]["json"]
        second_text = second_payload["params"]["message"]["parts"][0]["text"]
        assert "Broadened search" in second_text

    @pytest.mark.asyncio
    async def test_replan_on_discontinued(self):
        ctx = _mock_ctx()
        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.side_effect = [
                _a2a_response("The item was discontinued and is no longer available."),
                _a2a_response("SUCCESS: PO-777 created."),
            ]

            result = await _run_node(ctx, "Order discontinued item")

        assert result["status"] == "Success"
        assert mock_stream.call_count == 2

    @pytest.mark.asyncio
    async def test_replan_on_no_inventory(self):
        ctx = _mock_ctx()
        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.side_effect = [
                _a2a_response("No inventory found for the requested item."),
                _a2a_response("SUCCESS: PO-888 created."),
            ]

            result = await _run_node(ctx, "Order rare item")

        assert result["status"] == "Success"


class TestControlRoomFailure:
    """Both attempts fail — max retries exhausted."""

    @pytest.mark.asyncio
    async def test_max_attempts_exhausted(self):
        ctx = _mock_ctx()
        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.side_effect = [
                _a2a_response("Item not found."),
                _a2a_response("Item not found again."),
            ]

            result = await _run_node(ctx, "Order impossible item")

        assert result["status"] == "Failed"
        assert mock_stream.call_count == 2
        assert "Failed after 2 attempts" in ctx.state["final_outcome"]

    @pytest.mark.asyncio
    async def test_terminal_failure_does_not_replan(self):
        ctx = _mock_ctx()
        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.return_value = _a2a_response(
                "**Final Report**\n\n"
                "*   **Task Objective:** Restock 20 Mercari logo mugs for the Tokyo office.\n"
                "*   **Status:** FAILURE\n"
                "*   **Total Cost:** $400.00\n"
                "*   **Purchase Order ID:** Not Issued\n"
                "*   **Reason:** Over Budget"
            )

            result = await _run_node(ctx, "Restock 20 Mercari logo mugs for the Tokyo office.")

        assert result["status"] == "Failed"
        assert "Over Budget" in result["report"]
        assert mock_stream.call_count == 1
        ctx.run_node.assert_not_called()


class TestControlRoomErrorHandling:
    """Network and protocol errors."""

    @pytest.mark.asyncio
    async def test_http_error_status(self):
        ctx = _mock_ctx()
        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.side_effect = [
                _a2a_response("", status_code=500),
                _a2a_response("SUCCESS: PO-100 created."),
            ]

            result = await _run_node(ctx, "Order mugs")

        assert result["status"] == "Success"
        assert mock_stream.call_count == 2

    @pytest.mark.asyncio
    async def test_jsonrpc_error_response(self):
        ctx = _mock_ctx()
        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.side_effect = [
                _a2a_error_response("Internal server error"),
                _a2a_response("SUCCESS: PO-200 created."),
            ]

            result = await _run_node(ctx, "Order mugs")

        assert result["status"] == "Success"
        assert mock_stream.call_count == 2

    @pytest.mark.asyncio
    async def test_connection_error(self):
        ctx = _mock_ctx()
        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.side_effect = [
                ConnectionError("Connection refused"),
                _a2a_response("SUCCESS: PO-300 created."),
            ]

            result = await _run_node(ctx, "Order mugs")

        assert result["status"] == "Success"
        assert mock_stream.call_count == 2

    @pytest.mark.asyncio
    async def test_empty_artifacts(self):
        ctx = _mock_ctx()
        resp = _MockStreamResponse([json.dumps({"result": {"artifacts": []}})])

        with patch("httpx.AsyncClient.stream") as mock_stream:
            mock_stream.side_effect = [resp, _a2a_response("SUCCESS: PO-400 created.")]

            result = await _run_node(ctx, "Order mugs")

        assert result["status"] == "Success"
        assert mock_stream.call_count == 2


class TestCreateReplannerAgent:
    """Verify replanner agent factory."""

    def test_creates_agent_with_attempt_suffix(self):
        agent = create_replanner_agent(1)
        assert agent.name == "replanner_agent_attempt_1"

    def test_creates_unique_agents_per_attempt(self):
        a1 = create_replanner_agent(1)
        a2 = create_replanner_agent(2)
        assert a1.name != a2.name


class TestControlRoomWorkflow:
    """Verify the Workflow graph is wired correctly."""

    def test_workflow_name(self):
        assert ControlRoomAgent.name == "ControlRoomAgent"
