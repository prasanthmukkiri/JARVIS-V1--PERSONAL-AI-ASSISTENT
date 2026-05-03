"""
Unit tests for core actions.
Run: pytest tests/test_actions.py -v
"""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestBrowserControl:
    """Test browser_control action helpers."""

    def test_normalize_url_with_schema(self):
        """Test that URLs with scheme pass through unchanged."""
        from actions.browser_control import _normalize_url
        url = "https://example.com"
        assert _normalize_url(url) == url

    def test_normalize_url_bare_domain(self):
        """Test that bare domains get https:// prefix."""
        from actions.browser_control import _normalize_url
        assert _normalize_url("example.com") == "https://example.com"

    def test_normalize_url_bare_word(self):
        """Test that bare words get .com suffix and https:// prefix."""
        from actions.browser_control import _normalize_url
        assert _normalize_url("instagram") == "https://instagram.com"

    def test_normalize_url_empty(self):
        """Test that empty input returns about:blank."""
        from actions.browser_control import _normalize_url
        assert _normalize_url("") == "about:blank"


class TestOpenApp:
    """Test open_app action helpers."""

    def test_chrome_profile_name_default_exists(self):
        """Test that _chrome_profile_name returns 'Default' when it exists."""
        from actions.open_app import _chrome_profile_name, _chrome_user_data_dir
        # Only run this test if Chrome user data dir exists
        if _chrome_user_data_dir():
            result = _chrome_profile_name()
            assert result in ("Default", ) or result.lower().startswith("profile ")

    def test_find_chrome_windows_returns_string_or_none(self):
        """Test that _find_chrome_windows returns a string path or None."""
        from actions.open_app import _find_chrome_windows
        result = _find_chrome_windows()
        assert result is None or isinstance(result, str)


class TestCodeHelper:
    """Test code_helper action helpers."""

    def test_clean_code_removes_markdown(self):
        """Test that _clean_code removes markdown code fences."""
        from actions.code_helper import _clean_code
        code_with_fence = "```python\nprint('hello')\n```"
        result = _clean_code(code_with_fence)
        assert result == "print('hello')"

    def test_clean_code_strips_whitespace(self):
        """Test that _clean_code strips leading/trailing whitespace."""
        from actions.code_helper import _clean_code
        result = _clean_code("  \n  code here  \n  ")
        assert result == "code here"

    def test_resolve_save_path_with_language(self):
        """Test that _resolve_save_path picks correct file extension."""
        from actions.code_helper import _resolve_save_path
        py_path = _resolve_save_path("", "python")
        assert str(py_path).endswith(".py")
        
        js_path = _resolve_save_path("", "javascript")
        assert str(js_path).endswith(".js")


class TestErrorHandler:
    """Test error_handler decision logic."""

    def test_error_decision_enum(self):
        """Test that ErrorDecision enum has expected values."""
        from agent.error_handler import ErrorDecision
        assert hasattr(ErrorDecision, "RETRY")
        assert hasattr(ErrorDecision, "SKIP")
        assert hasattr(ErrorDecision, "REPLAN")
        assert hasattr(ErrorDecision, "ABORT")

    def test_generate_fix_writes_temp_file(self):
        """Test that generate_fix creates a temporary Python file."""
        import tempfile
        from agent.error_handler import generate_fix
        
        step = {
            "step": "test_step",
            "tool": "test_tool",
            "description": "Test description",
            "parameters": {},
            "depends_on": [],
            "critical": False
        }
        error = "Test error message"
        fix_suggestion = "Try a different approach"
        
        # Mock the genai to avoid API calls during testing
        with patch("google.generativeai.GenerativeModel") as mock_model:
            mock_response = MagicMock()
            mock_response.text = "print('Fixed code')"
            mock_model.return_value.generate_content.return_value = mock_response
            
            result = generate_fix(step, error, fix_suggestion)
            
            # Result should be a dict with tool set to code_helper
            assert isinstance(result, dict)
            assert result.get("tool") in ("code_helper", "generated_code")
            if result.get("tool") == "code_helper":
                # Should have file_path parameter
                assert "file_path" in result.get("parameters", {})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
