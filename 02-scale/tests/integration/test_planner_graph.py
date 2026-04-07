"""Tests for the LangGraph planner nodes and graph with mocked LLM."""

from unittest.mock import patch, MagicMock
import pytest

from agents.planner.state import AlertExtraction, PlanState


@pytest.fixture
def planner_nodes():
    """Create PlannerNodes with mocked LLM."""
    extraction = AlertExtraction(
        region="Northeast",
        item_description="Vintage Sci-Fi Mugs",
        quantity_needed=500,
        max_budget=50.0,
    )
    with patch("agents.planner.graph.ChatGoogleGenerativeAI") as MockLLM:
        mock_llm = MagicMock()
        MockLLM.return_value = mock_llm

        # structured_llm must return a real AlertExtraction (graph.py checks isinstance)
        mock_structured = MagicMock()
        mock_structured.invoke.return_value = extraction
        mock_llm.with_structured_output.return_value = mock_structured

        # llm.invoke returns AIMessage-like object
        mock_response = MagicMock()
        mock_response.content = "Final Report: SUCCESS. PO-123 created."
        mock_llm.invoke.return_value = mock_response

        from agents.planner.graph import PlannerNodes

        yield PlannerNodes()


class TestAnalyzeAlert:
    def test_extracts_fields(self, planner_nodes, sample_plan_state):
        result = planner_nodes.analyze_alert(sample_plan_state)
        assert result["region"] == "Northeast"
        assert result["item_description"] == "Vintage Sci-Fi Mugs"
        assert result["quantity_needed"] == 500
        assert result["max_budget"] == 50.0
        assert result["current_step"] == "analyzed"
        assert result["delegation_status"] == "pending"


class TestDelegateToExecutor:
    @patch("agents.executor.src.crew.LogisticsExecutionCrew")
    def test_success(self, MockCrew, planner_nodes, sample_plan_state):
        MockCrew.return_value.run.return_value = "PO-123 created successfully"
        result = planner_nodes.delegate_to_executor(sample_plan_state)
        assert result["delegation_status"] == "success"
        assert "PO-123" in result["execution_result"]
        assert result["current_step"] == "executed"

    @patch("agents.executor.src.crew.LogisticsExecutionCrew")
    def test_failure(self, MockCrew, planner_nodes, sample_plan_state):
        MockCrew.return_value.run.side_effect = Exception("MCP connection failed")
        result = planner_nodes.delegate_to_executor(sample_plan_state)
        assert result["delegation_status"] == "failed"
        assert result["execution_result"].startswith("Error:")
        assert "MCP connection failed" in result["execution_result"]


class TestGenerateReport:
    def test_generates_report(self, planner_nodes, sample_plan_state):
        state = {**sample_plan_state, "execution_result": "PO-123 created"}
        result = planner_nodes.generate_report(state)
        assert result["current_step"] == "completed"
        assert result["final_report"] == "Final Report: SUCCESS. PO-123 created."


class TestFullGraph:
    @patch("agents.executor.src.crew.LogisticsExecutionCrew")
    @patch("agents.planner.graph.ChatGoogleGenerativeAI")
    async def test_end_to_end(self, MockLLM, MockCrew):
        extraction = AlertExtraction(
            region="Northeast",
            item_description="Mugs",
            quantity_needed=100,
            max_budget=25.0,
        )
        mock_llm = MagicMock()
        MockLLM.return_value = mock_llm

        mock_structured = MagicMock()
        mock_structured.invoke.return_value = extraction
        mock_llm.with_structured_output.return_value = mock_structured

        mock_report = MagicMock()
        mock_report.content = "Final report text"
        mock_llm.invoke.return_value = mock_report

        MockCrew.return_value.run.return_value = "PO-456 created"

        from agents.planner.graph import build_planner_graph

        graph = build_planner_graph()
        initial_state: PlanState = {
            "objective": "Restock Mugs in Northeast"
        }
        final_state = await graph.ainvoke(initial_state)

        assert final_state["region"] == "Northeast"
        assert final_state["delegation_status"] == "success"
        assert final_state["current_step"] == "completed"
        assert final_state["final_report"] == "Final report text"
