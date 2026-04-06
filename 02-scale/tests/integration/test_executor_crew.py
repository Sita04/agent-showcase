"""Tests for LogisticsExecutionCrew orchestration with mocked dependencies."""

from unittest.mock import patch, MagicMock
from contextlib import contextmanager


@contextmanager
def _mock_mcp_context(tools=None):
    yield tools or [MagicMock()]


@patch("agents.executor.src.crew.LLM")
@patch("agents.executor.src.crew.Crew")
@patch("agents.executor.src.crew.ExecutorTasks")
@patch("agents.executor.src.crew.ExecutorAgents")
@patch("agents.executor.src.crew.get_mock_oms_mcp")
@patch("agents.executor.src.crew.get_mcp_server")
def test_run_orchestrates_correctly(
    mock_get_mcp, mock_get_oms, MockAgents, MockTasks, MockCrew, MockLLM
):
    # MCP context managers yield tool lists
    mock_get_mcp.return_value = _mock_mcp_context([MagicMock(name="vector_tool")])
    mock_get_oms.return_value = _mock_mcp_context([MagicMock(name="oms_tool")])

    # Crew.kickoff returns a result
    mock_crew_instance = MagicMock()
    mock_crew_instance.kickoff.return_value = "PO-789 created"
    MockCrew.return_value = mock_crew_instance

    from agents.executor.src.crew import LogisticsExecutionCrew

    crew = LogisticsExecutionCrew()
    result = crew.run(
        task_description="Anime Figures",
        budget=50.0,
        quantity=2,
    )

    assert result == "PO-789 created"
    mock_crew_instance.kickoff.assert_called_once()
    MockCrew.assert_called_once()


@patch("agents.executor.src.crew.LLM")
@patch("agents.executor.src.crew.Crew")
@patch("agents.executor.src.crew.ExecutorTasks")
@patch("agents.executor.src.crew.ExecutorAgents")
@patch("agents.executor.src.crew.get_mock_oms_mcp")
@patch("agents.executor.src.crew.get_mcp_server")
def test_mcp_context_managers_used(
    mock_get_mcp, mock_get_oms, MockAgents, MockTasks, MockCrew, MockLLM
):
    mock_vector_cm = MagicMock()
    mock_vector_cm.__enter__ = MagicMock(return_value=[MagicMock()])
    mock_vector_cm.__exit__ = MagicMock(return_value=False)
    mock_get_mcp.return_value = mock_vector_cm

    mock_oms_cm = MagicMock()
    mock_oms_cm.__enter__ = MagicMock(return_value=[MagicMock()])
    mock_oms_cm.__exit__ = MagicMock(return_value=False)
    mock_get_oms.return_value = mock_oms_cm

    MockCrew.return_value.kickoff.return_value = "done"

    from agents.executor.src.crew import LogisticsExecutionCrew

    crew = LogisticsExecutionCrew()
    crew.run(task_description="Test", budget=10.0, quantity=1)

    mock_vector_cm.__enter__.assert_called_once()
    mock_vector_cm.__exit__.assert_called_once()
    mock_oms_cm.__enter__.assert_called_once()
    mock_oms_cm.__exit__.assert_called_once()
