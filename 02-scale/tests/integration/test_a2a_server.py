"""Tests for the A2A server via httpx ASGI transport (no real server needed)."""

import uuid
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

a2a_server_apps = pytest.importorskip("a2a.server.apps")

import httpx
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill
from a2a.utils.errors import ServerError


@pytest.fixture
def mock_graph():
    mock = MagicMock()
    mock.ainvoke = AsyncMock(
        return_value={"final_report": "SUCCESS: PO-TEST-1 created. Total cost: $100."}
    )
    return mock


@pytest.fixture
def a2a_app(mock_graph):
    with patch("graph.build_planner_graph", return_value=mock_graph):
        from agents.planner.a2a_server import PlannerAgentExecutor

        agent_card = AgentCard(
            name="Test-Orchestrator",
            description="Test agent",
            url="http://localhost:8080/",
            version="1.0.0",
            default_input_modes=["text", "text/plain"],
            default_output_modes=["text", "text/plain"],
            capabilities=AgentCapabilities(streaming=False),
            skills=[
                AgentSkill(
                    id="test_skill",
                    name="Test Skill",
                    description="A test skill",
                    tags=["test"],
                )
            ],
        )
        executor = PlannerAgentExecutor()
        handler = DefaultRequestHandler(
            agent_executor=executor, task_store=InMemoryTaskStore()
        )
        app = A2AStarletteApplication(
            agent_card=agent_card, http_handler=handler
        )
        yield app.build()


@pytest.fixture
def a2a_client(a2a_app):
    transport = httpx.ASGITransport(app=a2a_app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_agent_card_endpoint(a2a_client):
    async with a2a_client as client:
        response = await client.get("/.well-known/agent.json")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Test-Orchestrator"
        assert len(data["skills"]) == 1


async def test_message_send(a2a_client):
    async with a2a_client as client:
        payload = {
            "jsonrpc": "2.0",
            "id": "req-test-1",
            "method": "message/send",
            "params": {
                "message": {
                    "message_id": str(uuid.uuid4()),
                    "parts": [{"kind": "text", "text": "Restock mugs in Northeast"}],
                    "role": "user",
                }
            },
        }
        response = await client.post("/", json=payload)
        assert response.status_code == 200
        result = response.json()
        assert "result" in result
        # Verify the response contains the expected report from the mocked graph
        task = result["result"]
        artifacts = task.get("artifacts", [])
        assert len(artifacts) > 0
        report_text = artifacts[-1]["parts"][0]["text"]
        assert "PO-TEST-1" in report_text


async def test_cancel_raises():
    with patch("graph.build_planner_graph"):
        from agents.planner.a2a_server import PlannerAgentExecutor

        executor = PlannerAgentExecutor()
        with pytest.raises(ServerError):
            await executor.cancel(MagicMock(), MagicMock())
