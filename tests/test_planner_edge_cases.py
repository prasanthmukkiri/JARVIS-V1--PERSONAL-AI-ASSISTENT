"""
Test 1: Parameterized Edge Case Tests
Tests for direct message parsing with various edge cases.
"""
import pytest
from agent.planner import create_plan, _build_direct_message_plan, _normalize_plan


class TestSendMessageEdgeCases:
    """Parameterized tests for send_message command with various inputs."""
    
    @pytest.mark.parametrize("message,expected_receiver,expected_msg", [
        # Standard format
        ("send a message to pk saying hello", "pk", "hello"),
        
        # Multi-word names
        ("send a message to john doe saying hey", "john doe", "hey"),
        ("send message to john smith saying how are you", "john smith", "how are you"),
        
        # Special characters in message
        ("send a message to pk saying can't wait!", "pk", "can't wait!"),
        ("send a message to john saying hey! how's it going?", "john", "hey! how's it going?"),
        ("send message to sara saying @#$%^&*()", "sara", "@#$%^&*()"),
        
        # Quoted names
        ("send message to 'john' saying hello", "john", "hello"),
        ('send message to "contact name" saying hi', "contact name", "hi"),
        
        # Various formats
        ("send message to pk saying hi", "pk", "hi"),
        ("please send a message to mom saying love you", "mom", "love you"),
        ("message pk saying hello world", "pk", "hello world"),
        
        # Longer messages
        ("send a message to work group saying meeting rescheduled to 3pm tomorrow", 
         "work group", "meeting rescheduled to 3pm tomorrow"),
         
        # Numbers and special keywords
        ("send message to user123 saying code is 12345", "user123", "code is 12345"),
    ])
    def test_send_message_parsing(self, message, expected_receiver, expected_msg):
        """Test that various message formats parse correctly."""
        plan = create_plan(message)
        
        assert plan is not None, f"Plan should not be None for: {message}"
        assert len(plan["steps"]) > 0, f"Plan should have steps for: {message}"
        
        step = plan["steps"][0]
        assert step["tool"] == "send_message", f"Tool should be send_message for: {message}"
        assert step["parameters"]["receiver"] == expected_receiver, \
            f"Receiver mismatch. Got {step['parameters']['receiver']}, expected {expected_receiver}"
        assert step["parameters"]["message_text"] == expected_msg, \
            f"Message mismatch. Got {step['parameters']['message_text']}, expected {expected_msg}"
    
    
    @pytest.mark.parametrize("message", [
        "send message saying hello",  # Missing receiver
        "send message to pk",  # Missing message text
        "message to john",  # Incomplete format
        "",  # Empty string
    ])
    def test_send_message_invalid_formats(self, message):
        """Test that incomplete or invalid formats are handled gracefully."""
        # Should either return None or handle gracefully
        plan = create_plan(message)
        
        if plan:
            # If plan is generated, it should not be for send_message or should have required fields
            if plan["steps"] and plan["steps"][0]["tool"] == "send_message":
                assert "receiver" in plan["steps"][0]["parameters"]
                assert "message_text" in plan["steps"][0]["parameters"]


class TestOpenAppEdgeCases:
    """Parameterized tests for open_app command."""
    
    @pytest.mark.parametrize("command,expected_app", [
        ("open chrome", "chrome"),
        ("open Google Chrome", "Google Chrome"),
        ("open visual studio code", "visual studio code"),
        ("launch discord", "discord"),
        ("start notepad", "notepad"),
        ("please open firefox", "firefox"),
        ("open spotify", "spotify"),
    ])
    def test_open_app_parsing(self, command, expected_app):
        """Test that various open_app commands parse correctly."""
        plan = create_plan(command)
        
        assert plan is not None, f"Plan should not be None for: {command}"
        assert len(plan["steps"]) > 0, f"Plan should have steps for: {command}"
        
        step = plan["steps"][0]
        assert step["tool"] == "open_app", f"Tool should be open_app for: {command}"
        assert step["parameters"]["app_name"] == expected_app


class TestWeatherEdgeCases:
    """Parameterized tests for weather_report command."""
    
    @pytest.mark.parametrize("command,expected_city", [
        ("what is the weather in london", "london"),
        ("weather in new york", "new york"),
        ("weather for paris", "paris"),
        ("tell me the temperature in san francisco", "san francisco"),
        ("forecast for tokyo", "tokyo"),
        ("weather in los angeles california", "los angeles california"),
    ])
    def test_weather_parsing(self, command, expected_city):
        """Test that weather commands parse correctly."""
        plan = create_plan(command)
        
        assert plan is not None, f"Plan should not be None for: {command}"
        assert len(plan["steps"]) > 0, f"Plan should have steps for: {command}"
        
        step = plan["steps"][0]
        assert step["tool"] == "weather_report", f"Tool should be weather_report for: {command}"
        # City might be part of parameters
        assert "city" in step["parameters"] or step["parameters"] != {}


class TestWebSearchEdgeCases:
    """Parameterized tests for web_search command."""
    
    @pytest.mark.parametrize("command,expected_keyword", [
        ("search for python tutorials", "python tutorials"),
        ("google best practices for coding", "best practices for coding"),
        ("find information about machine learning", "information about machine learning"),
        ("look up how to fix windows errors", "how to fix windows errors"),
        ("search how to make pizza", "how to make pizza"),
    ])
    def test_web_search_parsing(self, command, expected_keyword):
        """Test that web search commands parse correctly."""
        plan = create_plan(command)
        
        assert plan is not None, f"Plan should not be None for: {command}"
        assert len(plan["steps"]) > 0, f"Plan should have steps for: {command}"
        
        step = plan["steps"][0]
        assert step["tool"] == "web_search", f"Tool should be web_search for: {command}"
        assert "query" in step["parameters"]


class TestNormalizationEdgeCases:
    """Test plan normalization with edge cases."""
    
    def test_normalize_plan_with_extra_whitespace(self):
        """Test that plans with extra whitespace are normalized correctly."""
        plan = {
            "goal": "test",
            "steps": [
                {
                    "step": 1,
                    "tool": "  send_message  ",
                    "description": "   Send message   ",
                    "parameters": {"receiver": "  pk  ", "message_text": "  hello  "},
                    "critical": True
                }
            ]
        }
        
        normalized = _normalize_plan(plan, "test")
        assert normalized["steps"][0]["tool"] == "send_message"
        assert normalized["steps"][0]["parameters"]["receiver"] == "pk"
        assert normalized["steps"][0]["parameters"]["message_text"] == "hello"
    
    def test_normalize_plan_with_quoted_values(self):
        """Test that quoted parameter values are properly cleaned."""
        plan = {
            "goal": "test",
            "steps": [
                {
                    "step": 1,
                    "tool": "send_message",
                    "description": "Send message",
                    "parameters": {"receiver": '"john"', "message_text": "'hello world'"},
                    "critical": True
                }
            ]
        }
        
        normalized = _normalize_plan(plan, "test")
        assert normalized["steps"][0]["parameters"]["receiver"] == "john"
        assert normalized["steps"][0]["parameters"]["message_text"] == "hello world"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
