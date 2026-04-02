"""E2E test for CUJ 1: The "Happy Path" Restock.

Runs the full LangGraph -> CrewAI -> MCP flow against real services.
Requires GCP credentials and network access to the Vector Search API.

Usage:
    uv run pytest tests/e2e/ -v
"""

import os
import re

import pytest

from state import PlanState

# Skip the entire module if no real GCP project is configured.
_project = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
pytestmark = pytest.mark.skipif(
    not _project or _project == "test-project-id",
    reason="E2E tests require a real GOOGLE_CLOUD_PROJECT",
)


@pytest.fixture
def planner_graph():
    from agents.planner.graph import build_planner_graph

    return build_planner_graph()


async def test_happy_path_restock(planner_graph):
    """CUJ 1: Planning Agent delegates procurement to CrewAI, which finds
    products via vector search and places a purchase order through the
    Mock OMS."""

    initial_state: PlanState = {
        "objective": (
            "Inventory Alert: Northeast Region is critically low on "
            "'Rare Japanese Anime Figure'. "
            "Please order 2 units ASAP. Max budget $50 per unit."
        ),
    }

    final_state = await planner_graph.ainvoke(initial_state)

    # --- Step 1: Alert analysis ---
    assert final_state.get("region"), "Region was not extracted"
    assert final_state.get("item_description"), "Item description was not extracted"
    assert final_state.get("quantity_needed"), "Quantity was not extracted"
    assert final_state.get("max_budget"), "Budget was not extracted"

    # --- Step 2: Delegation succeeded ---
    assert final_state["delegation_status"] == "success", (
        f"Delegation failed: {final_state.get('execution_result')}"
    )
    assert final_state.get("execution_result"), "No execution result returned"

    # --- Step 3: Final report generated ---
    assert final_state["current_step"] == "completed"
    report = final_state.get("final_report", "")
    assert report, "No final report generated"

    # The report should mention a Purchase Order ID (PO-xxx-N pattern)
    assert re.search(r"PO-\S+", report), (
        f"Report does not contain a Purchase Order ID: {report}"
    )
