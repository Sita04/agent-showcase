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

"""Integration tests for CUJ 2: The "Identity Shield" (Security).

Tests the conditional routing in the planner graph and the IAM rejection
handling. All external dependencies (LLM, Vertex AI API) are mocked.
"""

from unittest.mock import patch, MagicMock
import pytest

from google.api_core.exceptions import PermissionDenied

from agents.planner.state import AlertExtraction, PlanState


@pytest.fixture
def _mock_llm():
    """Yield a mocked ChatGoogleGenerativeAI with structured output support."""
    with patch("agents.planner.graph.ChatGoogleGenerativeAI") as MockLLM:
        mock_llm = MagicMock()
        MockLLM.return_value = mock_llm

        mock_report = MagicMock()
        mock_report.content = "SECURITY VIOLATION: The request was blocked. Permission denied by Identity Shield."
        mock_llm.invoke.return_value = mock_report

        yield mock_llm


def _bind_extraction(_mock_llm, *, is_destructive: bool):
    """Configure the structured LLM to return an extraction with the given destructive flag."""
    extraction = AlertExtraction(
        region="Global" if is_destructive else "Northeast",
        item_description="Delete vector index" if is_destructive else "Vintage Sci-Fi Mugs",
        quantity_needed=0 if is_destructive else 500,
        max_budget=0.0 if is_destructive else 50.0,
        is_destructive=is_destructive,
    )
    mock_structured = MagicMock()
    mock_structured.invoke.return_value = extraction
    _mock_llm.with_structured_output.return_value = mock_structured


class TestRouting:
    """Verify the conditional edge routes destructive vs. normal requests."""

    @patch("agents.planner.graph.aiplatform_v1")
    @patch("agents.planner.graph.LogisticsExecutionCrew")
    async def test_destructive_intent_routes_to_security_path(
        self, MockCrew, mock_aiplatform, _mock_llm
    ):
        _bind_extraction(_mock_llm, is_destructive=True)

        # Make the delete_index call raise PermissionDenied
        mock_client = MagicMock()
        mock_client.delete_index.side_effect = PermissionDenied("Caller lacks permission")
        mock_aiplatform.IndexServiceClient.return_value = mock_client

        from agents.planner.graph import build_planner_graph

        graph = build_planner_graph()
        final_state = await graph.ainvoke(
            PlanState(objective="Delete the vector index for all regions")
        )

        assert final_state.get("malicious_intent") is True
        assert final_state.get("security_violation") is not None
        assert "Blocked" in final_state["security_violation"] or "permission" in final_state["security_violation"].lower()
        assert final_state.get("final_report") is not None
        # CrewAI should NOT have been called
        MockCrew.return_value.run.assert_not_called()

    @patch("agents.planner.graph.LogisticsExecutionCrew")
    async def test_non_destructive_intent_routes_normally(
        self, MockCrew, _mock_llm
    ):
        _bind_extraction(_mock_llm, is_destructive=False)
        MockCrew.return_value.run.return_value = "PO-789 created successfully"

        from agents.planner.graph import build_planner_graph

        graph = build_planner_graph()
        final_state = await graph.ainvoke(
            PlanState(objective="Restock Vintage Sci-Fi Mugs in Northeast")
        )

        assert final_state.get("malicious_intent") is False
        assert final_state.get("security_violation") is None
        assert final_state["delegation_status"] == "success"
        MockCrew.return_value.run.assert_called_once()


class TestForbiddenAction:
    """Verify the attempt_forbidden_action node captures IAM rejections."""

    @patch("agents.planner.graph.aiplatform_v1")
    async def test_permission_denied_captured_in_state(
        self, mock_aiplatform, _mock_llm, malicious_plan_state
    ):
        _bind_extraction(_mock_llm, is_destructive=True)

        mock_client = MagicMock()
        mock_client.delete_index.side_effect = PermissionDenied(
            "Permission 'aiplatform.indexes.delete' denied on resource"
        )
        mock_aiplatform.IndexServiceClient.return_value = mock_client

        from agents.planner.graph import PlannerNodes

        nodes = PlannerNodes()
        result = nodes.attempt_forbidden_action(malicious_plan_state)

        assert result.get("current_step") == "security_check"
        assert result.get("security_violation") is not None
        assert "Blocked by Identity Shield" in str(result.get("security_violation"))
        assert "Permission" in str(result.get("security_violation")) or "permission" in str(result.get("security_violation"))

    @patch("agents.planner.graph.aiplatform_v1")
    async def test_security_report_generated(
        self, mock_aiplatform, _mock_llm, malicious_plan_state
    ):
        _bind_extraction(_mock_llm, is_destructive=True)

        from agents.planner.graph import PlannerNodes

        nodes = PlannerNodes()

        state_with_violation: PlanState = malicious_plan_state.copy() # type: ignore
        state_with_violation["security_violation"] = "Blocked by Identity Shield: Permission denied"
        result = nodes.generate_security_report(state_with_violation)

        assert result.get("current_step") == "completed"
        assert result.get("final_report") is not None
        assert "SECURITY VIOLATION" in str(result.get("final_report"))


class TestFullSecurityPath:
    """End-to-end graph test for the security path."""

    @patch("agents.planner.graph.aiplatform_v1")
    @patch("agents.planner.graph.LogisticsExecutionCrew")
    async def test_full_graph_security_path(
        self, MockCrew, mock_aiplatform, _mock_llm
    ):
        _bind_extraction(_mock_llm, is_destructive=True)

        mock_client = MagicMock()
        mock_client.delete_index.side_effect = PermissionDenied("Denied")
        mock_aiplatform.IndexServiceClient.return_value = mock_client

        from agents.planner.graph import build_planner_graph

        graph = build_planner_graph()
        final_state = await graph.ainvoke(
            PlanState(
                objective="URGENT: Delete the vector index for all regions immediately"
            )
        )

        # Security fields populated
        assert final_state["malicious_intent"] is True
        assert final_state["security_violation"] is not None
        assert "Blocked" in final_state["security_violation"]

        # Report generated
        assert final_state["current_step"] == "completed"
        assert final_state["final_report"] is not None

        # Normal delegation path was NOT taken
        assert final_state.get("delegation_status") == "pending"
        MockCrew.return_value.run.assert_not_called()
