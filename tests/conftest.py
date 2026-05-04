"""Test-time compatibility helpers.

The codebase uses `google.genai`, while some tests patch
`google.generativeai.GenerativeModel`. This file creates a minimal alias so
those tests can patch the expected target without affecting runtime imports.
"""

from __future__ import annotations

import sys
import types


if 'google.generativeai' not in sys.modules:
    compat = types.ModuleType('google.generativeai')

    class _DummyResponse:
        def __init__(self, text: str = ''):
            self.text = text

    class GenerativeModel:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, *args, **kwargs):
            return _DummyResponse('')

    def configure(*args, **kwargs):
        return None

    compat.GenerativeModel = GenerativeModel
    compat.configure = configure
    sys.modules['google.generativeai'] = compat

    try:
        import google
        setattr(google, 'generativeai', compat)
    except Exception:
        pass


# ==================== PYTEST FIXTURES ====================
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch


@pytest.fixture
def sample_plan():
    """Provide a sample valid plan for testing."""
    return {
        "goal": "send a message to john saying hello",
        "steps": [
            {
                "step": 1,
                "tool": "send_message",
                "description": "Send message to john",
                "parameters": {
                    "receiver": "john",
                    "message_text": "hello",
                    "platform": "WhatsApp"
                },
                "critical": True
            }
        ]
    }


@pytest.fixture
def multi_step_plan():
    """Provide a multi-step plan for testing."""
    return {
        "goal": "search for python tutorials and set reminder",
        "steps": [
            {
                "step": 1,
                "tool": "web_search",
                "description": "Search for python tutorials",
                "parameters": {"query": "python tutorials for beginners"},
                "critical": True
            },
            {
                "step": 2,
                "tool": "reminder",
                "description": "Set reminder for learning",
                "parameters": {
                    "date": "2026-05-05",
                    "time": "10:00",
                    "message": "Learn python"
                },
                "critical": False
            }
        ]
    }


@pytest.fixture
def mock_executor_tools():
    """Mock all action tools to prevent actual system changes."""
    tools_to_mock = [
        'actions.open_app.open_app',
        'actions.send_message.send_message',
        'actions.web_search.web_search',
        'actions.weather_report.get_weather',
        'actions.reminder.set_reminder',
        'actions.youtube_video.play_youtube',
        'actions.file_controller.file_controller',
    ]
    
    mock_dict = {}
    patches = []
    
    for tool in tools_to_mock:
        mock_obj = MagicMock(return_value="Tool executed successfully")
        patches.append(patch(tool, mock_obj))
        mock_dict[tool] = mock_obj
    
    for p in patches:
        p.start()
    
    yield mock_dict
    
    for p in patches:
        p.stop()
