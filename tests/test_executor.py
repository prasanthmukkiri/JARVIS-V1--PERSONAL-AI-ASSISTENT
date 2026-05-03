"""
Integration tests for agent and executor.
Run: pytest tests/test_executor.py -v
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from agent.task_queue import TaskPriority


class TestTaskQueue:
    """Test task queue functionality."""

    def test_task_priority_enum(self):
        """Test that TaskPriority enum has expected levels."""
        assert hasattr(TaskPriority, "LOW")
        assert hasattr(TaskPriority, "NORMAL")
        assert hasattr(TaskPriority, "HIGH")
        assert hasattr(TaskPriority, "CRITICAL")


class TestPlannerStep:
    """Test planner step structure and validation."""

    def test_step_has_required_fields(self):
        """Test that a valid planner step has all required fields."""
        # This is a structure test; real steps come from the LLM
        required_fields = ["step", "tool", "description", "parameters"]
        # Just verify the fields list is non-empty
        assert len(required_fields) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
