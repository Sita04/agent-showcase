"""Tests for executor agent and task prompt templates."""

from agents.executor.src.prompts import AGENT_PROMPTS, TASK_PROMPTS


class TestAgentPrompts:
    def test_has_both_agents(self):
        assert "sourcing_specialist" in AGENT_PROMPTS
        assert "procurement_officer" in AGENT_PROMPTS

    def test_sourcing_specialist_fields(self):
        prompts = AGENT_PROMPTS["sourcing_specialist"]
        for key in ("role", "goal", "backstory"):
            assert key in prompts
            assert isinstance(prompts[key], str)
            assert len(prompts[key]) > 0

    def test_procurement_officer_fields(self):
        prompts = AGENT_PROMPTS["procurement_officer"]
        for key in ("role", "goal", "backstory"):
            assert key in prompts
            assert isinstance(prompts[key], str)
            assert len(prompts[key]) > 0


class TestTaskPrompts:
    def test_sourcing_description_renders(self):
        desc = TASK_PROMPTS["sourcing"]["description"]
        rendered = desc.format(item_description="Mugs", max_budget=50)
        assert "Mugs" in rendered
        assert "50" in rendered

    def test_procurement_description_renders(self):
        desc = TASK_PROMPTS["procurement"]["description"]
        rendered = desc.format(quantity=10)
        assert "10" in rendered

    def test_expected_outputs_non_empty(self):
        for task_key in ("sourcing", "procurement"):
            output = TASK_PROMPTS[task_key]["expected_output"]
            assert isinstance(output, str)
            assert len(output.strip()) > 0
