"""Tests for planner prompt templates and AlertExtraction schema."""

import pytest
from pydantic import ValidationError
from agents.planner.state import AlertExtraction
from agents.config.prompts import PLANNER_SYSTEM_PROMPT, REPORT_GENERATOR_PROMPT


class TestAlertExtraction:
    def test_valid_construction_with_defaults(self):
        extraction = AlertExtraction(
            region="Northeast",
            item_description="Vintage Sci-Fi Mugs",
        )
        assert extraction.region == "Northeast"
        assert extraction.item_description == "Vintage Sci-Fi Mugs"
        assert extraction.quantity_needed == 500
        assert extraction.max_budget == 50.0

    def test_custom_values(self):
        extraction = AlertExtraction(
            region="West",
            item_description="Anime Figures",
            quantity_needed=10,
            max_budget=25.0,
        )
        assert extraction.quantity_needed == 10
        assert extraction.max_budget == 25.0

    def test_missing_region_raises(self):
        with pytest.raises(ValidationError):
            AlertExtraction(item_description="Mugs")  # type: ignore[call-arg]

    def test_missing_item_description_raises(self):
        with pytest.raises(ValidationError):
            AlertExtraction(region="Northeast")  # type: ignore[call-arg]


class TestPromptTemplates:
    def test_planner_system_prompt_not_empty(self):
        assert len(PLANNER_SYSTEM_PROMPT) > 0
        assert "Planning Agent" in PLANNER_SYSTEM_PROMPT

    def test_report_generator_prompt_renders(self):
        rendered = REPORT_GENERATOR_PROMPT.format(
            objective="Restock Northeast",
            execution_result="PO-123 created",
        )
        assert "Restock Northeast" in rendered
        assert "PO-123 created" in rendered
