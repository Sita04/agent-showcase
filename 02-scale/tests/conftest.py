import os
import sys

# Set env vars BEFORE any application code is imported.
# default_config.py runs `config = DefaultConfig()` at module level,
# which raises ValueError if GOOGLE_CLOUD_PROJECT is unset.
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project-id")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "TRUE")

# Add source directories to sys.path to match runtime import resolution.
# The application code uses bare imports like `from state import PlanState`.
_SCALE_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for _p in [
    _SCALE_ROOT,
    os.path.join(_SCALE_ROOT, "agents"),
    os.path.join(_SCALE_ROOT, "agents", "planner"),
    os.path.join(_SCALE_ROOT, "agents", "executor"),
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest
from agents.planner.state import PlanState
from agents.planner.prompts import AlertExtraction
from agents.config.default_config import DefaultConfig


@pytest.fixture
def sample_plan_state() -> PlanState:
    return PlanState(
        objective="Inventory Alert: Northeast Region is critically low on 'Vintage Sci-Fi Mugs'. Order 500 units. Max budget $50 per unit.",
        region="Northeast",
        item_description="Vintage Sci-Fi Mugs",
        quantity_needed=500,
        max_budget=50.0,
        current_step="initial",
        delegation_status="pending",
        execution_result=None,
        final_report=None,
    )


@pytest.fixture
def mock_alert_extraction() -> AlertExtraction:
    return AlertExtraction(
        region="Northeast",
        item_description="Vintage Sci-Fi Mugs",
        quantity_needed=500,
        max_budget=50.0,
    )


@pytest.fixture
def mock_config() -> DefaultConfig:
    return DefaultConfig(
        GOOGLE_CLOUD_PROJECT="test-project-id",
        BUDGET_LIMIT=100.0,
        DEFAULT_VENDOR_ID="mercari_seller",
    )
