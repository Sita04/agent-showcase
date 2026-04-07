"""Tests for ExecutorTasks task creation."""

from unittest.mock import patch, MagicMock
from agents.config.prompts import EXECUTOR_TASK_PROMPTS


class TestExecutorTasks:
    def test_sourcing_task_has_correct_description(self):
        """Verify the sourcing task formats prompts correctly."""
        prompts = EXECUTOR_TASK_PROMPTS["sourcing"]
        rendered = prompts["description"].format(
            item_description="Vintage Sci-Fi Mugs",
            max_budget=50.0,
        )
        assert "Vintage Sci-Fi Mugs" in rendered
        assert "50" in rendered

    def test_procurement_task_has_correct_description(self):
        """Verify the procurement task formats prompts correctly."""
        prompts = EXECUTOR_TASK_PROMPTS["procurement"]
        rendered = prompts["description"].format(quantity=10)
        assert "10" in rendered

    @patch("agents.executor.src.tasks.Task")
    def test_sourcing_task_creates_task_object(self, MockTask):
        from agents.executor.src.tasks import ExecutorTasks

        mock_agent = MagicMock()
        tasks = ExecutorTasks()
        tasks.sourcing_task(
            agent=mock_agent,
            item_description="Mugs",
            max_budget=50.0,
        )
        MockTask.assert_called_once()
        call_kwargs = MockTask.call_args
        assert "Mugs" in call_kwargs.kwargs["description"]
        assert call_kwargs.kwargs["agent"] == mock_agent

    @patch("agents.executor.src.tasks.Task")
    def test_procurement_task_creates_task_object(self, MockTask):
        from agents.executor.src.tasks import ExecutorTasks

        mock_agent = MagicMock()
        tasks = ExecutorTasks()
        tasks.procurement_task(agent=mock_agent, quantity=10)
        MockTask.assert_called_once()
        call_kwargs = MockTask.call_args
        assert "10" in call_kwargs.kwargs["description"]
        assert call_kwargs.kwargs["context"] == []
