# JARVISS API Reference

## Creating Custom Actions

This guide shows you how to create, test, and integrate new actions into JARVISS.

---

## Action Architecture

### Action Module Structure

```python
# actions/my_action.py

def my_action_execute(param1: str, param2: str = "default", **kwargs) -> dict:
    """
    Execute my custom action.
    
    Args:
        param1 (str): Required parameter
        param2 (str): Optional parameter with default
        **kwargs: Flexible arguments (auto_confirm, debug, etc.)
    
    Returns:
        dict: Result object with structure:
            {
                "success": bool,
                "data": Any,
                "error": str (optional),
                "message": str (optional)
            }
    """
    try:
        # Perform action
        result_data = do_something(param1, param2)
        
        # Return success
        return {
            "success": True,
            "data": result_data,
            "message": f"Successfully did something with {param1}"
        }
    
    except Exception as e:
        # Return failure
        return {
            "success": False,
            "error": str(e),
            "message": f"Failed to do something: {e}"
        }
```

---

## Step-by-Step Guide

### 1. Create Action Module

Create file `actions/my_action.py`:

```python
import logging

logger = logging.getLogger(__name__)

def my_action_execute(target: str, **kwargs) -> dict:
    """Send greetings to a target."""
    try:
        greeting = f"Hello, {target}!"
        logger.info(f"Greeting: {greeting}")
        return {
            "success": True,
            "data": greeting,
            "message": greeting
        }
    except Exception as e:
        logger.error(f"Greeting failed: {e}")
        return {
            "success": False,
            "error": str(e)
        }
```

### 2. Register Action in Planner

Edit `agent/planner.py` and add to `ACTIONS` dict:

```python
ACTIONS = {
    # ... existing actions ...
    
    "my_action": {
        "module": "actions.my_action",
        "function": "my_action_execute",
        "params": ["target"],
        "optional_params": [],
        "description": "Send greetings to a target"
    }
}
```

### 3. Add Intent Pattern

In `agent/planner.py`, add to `INTENT_PATTERNS`:

```python
INTENT_PATTERNS = {
    # ... existing patterns ...
    
    "greet": {
        "keywords": ["greet", "hello", "hi"],
        "actions": [
            {
                "name": "my_action",
                "params": {
                    "target": "extract_name_from_command(text)"
                }
            }
        ]
    }
}
```

### 4. Test Locally

```python
# test_my_action.py
from actions.my_action import my_action_execute

# Direct call
result = my_action_execute("Prasanth")
print(result)
# Output: {'success': True, 'data': 'Hello, Prasanth!', 'message': 'Hello, Prasanth!'}

# Via executor
from agent.executor import Executor
executor = Executor()
task = {
    "name": "my_action",
    "params": {"target": "Prasanth"}
}
result = executor.execute_task(task)
print(result)
```

### 5. Integrate into Main Flow

JARVISS will automatically detect and use your action. Test:

```bash
python main.py
# Speak: "Jarvis, greet Prasanth"
# Expected: "Hello, Prasanth!"
```

---

## Return Value Specification

All actions must return a dictionary:

```python
{
    "success": bool,              # Required: success/failure flag
    "data": Any,                  # Optional: result data
    "error": str,                 # Optional: error message
    "message": str,               # Optional: user-friendly message
    "metadata": dict              # Optional: debug info
}
```

### Examples

**Success:**
```python
return {
    "success": True,
    "data": {"temperature": 15, "condition": "Cloudy"},
    "message": "Weather fetched successfully"
}
```

**Failure:**
```python
return {
    "success": False,
    "error": "API key invalid",
    "message": "Could not fetch weather due to API error"
}
```

---

## Parameter Handling

### Required vs Optional

```python
def my_action_execute(
    required_param: str,           # Must be provided
    optional_param: str = "default",  # Can be omitted
    **kwargs                       # Flexible extras
) -> dict:
    # kwargs may contain:
    # - "debug": bool
    # - "auto_confirm": bool
    # - "timeout": int
    pass
```

### Accessing Flexible Parameters

```python
def my_action_execute(param1: str, **kwargs) -> dict:
    debug = kwargs.get("debug", False)
    auto_confirm = kwargs.get("auto_confirm", False)
    timeout = kwargs.get("timeout", 30)
    
    if debug:
        print(f"DEBUG: Running with param1={param1}")
    
    # ... rest of logic ...
```

---

## Logging Best Practices

```python
import logging

logger = logging.getLogger(__name__)

def my_action_execute(param: str, **kwargs) -> dict:
    logger.info(f"Starting action with param: {param}")
    
    try:
        result = do_work(param)
        logger.info(f"Action succeeded: {result}")
        return {"success": True, "data": result}
    
    except ValueError as e:
        logger.warning(f"Invalid input: {e}")
        return {"success": False, "error": str(e)}
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {"success": False, "error": "Internal error"}
```

Logs are written to `jarvis_log.txt`.

---

## Error Handling

### Try-Catch Pattern

```python
def my_action_execute(param: str, **kwargs) -> dict:
    try:
        # Main logic
        result = risky_operation(param)
        return {"success": True, "data": result}
    
    except TimeoutError:
        # Transient error — can retry
        return {
            "success": False,
            "error": "Timeout",
            "retry": True
        }
    
    except ValueError:
        # User error — prompt for correction
        return {
            "success": False,
            "error": "Invalid input",
            "user_prompt": "Please provide a valid value"
        }
    
    except Exception as e:
        # Unexpected error
        logger.error(f"Unexpected error: {e}", exc_info=True)
        return {
            "success": False,
            "error": f"Unexpected error: {e}"
        }
```

---

## External API Integration

### Example: Weather API

```python
# actions/custom_weather.py
import requests
from config.api_keys import API_KEYS

def custom_weather_execute(location: str, **kwargs) -> dict:
    """Get weather from OpenWeather API."""
    api_key = API_KEYS.get("openweather_api_key")
    
    if not api_key:
        return {
            "success": False,
            "error": "API key not configured",
            "message": "Please add openweather_api_key to config/api_keys.json"
        }
    
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "q": location,
            "appid": api_key,
            "units": "metric"
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        
        data = response.json()
        
        return {
            "success": True,
            "data": {
                "temperature": data["main"]["temp"],
                "condition": data["weather"][0]["main"],
                "humidity": data["main"]["humidity"]
            },
            "message": f"Weather in {location}: {data['weather'][0]['main']}, {data['main']['temp']}°C"
        }
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "error": "API timeout",
            "retry": True
        }
    
    except requests.exceptions.HTTPError as e:
        return {
            "success": False,
            "error": f"API error: {e.response.status_code}",
            "message": "Could not fetch weather"
        }
```

---

## Desktop Automation

### Example: Click and Type

```python
# actions/custom_automation.py
import pyautogui
import time

def custom_automation_execute(text: str, **kwargs) -> dict:
    """Automate clicking and typing."""
    try:
        # Move mouse to position
        pyautogui.moveTo(100, 200)
        
        # Click
        pyautogui.click()
        time.sleep(0.5)
        
        # Type text
        pyautogui.write(text, interval=0.05)
        time.sleep(0.2)
        
        # Press Enter
        pyautogui.press("enter")
        
        return {
            "success": True,
            "message": f"Typed and sent: {text}"
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

---

## File Operations

### Example: Read/Write Files

```python
# actions/custom_file.py
from pathlib import Path
import json

def custom_file_execute(filename: str, content: str = None, **kwargs) -> dict:
    """Read or write files."""
    try:
        filepath = Path(filename)
        
        if content is not None:
            # Write
            filepath.write_text(content)
            return {
                "success": True,
                "message": f"Wrote to {filename}"
            }
        else:
            # Read
            if not filepath.exists():
                return {
                    "success": False,
                    "error": f"File not found: {filename}"
                }
            
            content = filepath.read_text()
            return {
                "success": True,
                "data": content,
                "message": f"Read {filename}"
            }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

---

## Testing Actions

### Unit Test Example

```python
# tests/test_my_action.py
import unittest
from actions.my_action import my_action_execute

class TestMyAction(unittest.TestCase):
    
    def test_success(self):
        """Test successful execution."""
        result = my_action_execute("test_param")
        self.assertTrue(result["success"])
        self.assertIn("data", result)
    
    def test_missing_param(self):
        """Test with missing required parameter."""
        result = my_action_execute("")
        self.assertFalse(result["success"])
        self.assertIn("error", result)
    
    def test_return_format(self):
        """Test return value format."""
        result = my_action_execute("test")
        self.assertIn("success", result)
        self.assertIsInstance(result["success"], bool)

if __name__ == "__main__":
    unittest.main()
```

Run tests:
```bash
python -m pytest tests/test_my_action.py -v
```

---

## Advanced: Async Actions

```python
import asyncio
from typing import Awaitable

async def my_async_operation(data: str) -> str:
    """Simulate async work."""
    await asyncio.sleep(1)
    return f"Processed: {data}"

def my_async_action_execute(data: str, **kwargs) -> dict:
    """Execute async operation."""
    try:
        # Run async code in sync context
        result = asyncio.run(my_async_operation(data))
        return {
            "success": True,
            "data": result
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
```

---

## Debugging Actions

### Enable Debug Output

```python
import sys

def my_action_execute(param: str, **kwargs) -> dict:
    debug = kwargs.get("debug", False)
    
    if debug:
        print(f"[DEBUG] Input: {param}")
        print(f"[DEBUG] Processing...")
        # ... capture screenshots, etc. ...
```

### Save Debug Artifacts

```python
from pathlib import Path

def my_action_execute(param: str, **kwargs) -> dict:
    debug_dir = kwargs.get("debug_dir")
    
    if debug_dir:
        debug_path = Path(debug_dir)
        debug_path.mkdir(parents=True, exist_ok=True)
        
        # Save debug info
        (debug_path / "debug_info.txt").write_text(f"Param: {param}")
    
    # ... action logic ...
```

---

## Configuration for Actions

### Read from Config

```python
from memory.config_manager import ConfigManager

def my_action_execute(param: str, **kwargs) -> dict:
    config = ConfigManager()
    
    timeout = config.get("action_timeout", 30)
    retry_count = config.get("max_retries", 3)
    
    # Use config values
    # ...
```

### Save to Config

```python
from memory.config_manager import ConfigManager

def my_action_execute(param: str, **kwargs) -> dict:
    config = ConfigManager()
    config.set("my_setting", param)
    config.save()
    
    return {
        "success": True,
        "message": f"Saved setting: {param}"
    }
```

---

## Documentation Template

Use this template for your action's docstring:

```python
def my_action_execute(param1: str, param2: int = 5, **kwargs) -> dict:
    """
    Short description of what the action does.
    
    Longer description explaining the behavior, expected inputs,
    and any side effects or requirements.
    
    Args:
        param1 (str): Description of param1.
        param2 (int): Description of param2. Default: 5.
        **kwargs: Optional keyword arguments:
            - debug (bool): Enable debug output.
            - auto_confirm (bool): Skip confirmation prompts.
            - timeout (int): Operation timeout in seconds.
    
    Returns:
        dict: Result object with keys:
            - success (bool): Whether action succeeded.
            - data (Any): Result data (on success).
            - error (str): Error message (on failure).
            - message (str): User-friendly message.
    
    Raises:
        None (all exceptions caught and returned in result dict).
    
    Example:
        >>> result = my_action_execute("input", param2=10)
        >>> if result["success"]:
        ...     print(result["data"])
    """
    pass
```

---

## Best Practices

1. **Always handle exceptions** — Return error dict, don't raise.
2. **Provide clear messages** — Users should understand what happened.
3. **Log important events** — Use logger for debugging.
4. **Validate inputs** — Check parameters early.
5. **Respect timeouts** — Don't block indefinitely.
6. **Clean up resources** — Close files, connections, etc.
7. **Write tests** — Unit test your action.
8. **Document thoroughly** — Clear docstrings and examples.

---

## Troubleshooting Action Development

### Action not recognized
- Check registration in `agent/planner.py`
- Verify module path is correct: `"actions.my_action"`
- Check function name matches: `my_action_execute`

### Import errors
- Ensure all dependencies are in `requirements.txt`
- Check file paths (relative to project root)

### Action fails silently
- Enable debug: `sys._send_debug = True`
- Check `jarvis_log.txt` for error messages
- Add print statements for debugging

### Parameter not passed
- Verify intent pattern in planner extracts parameter correctly
- Test with direct function call first

---

## Checklist for New Actions

- [ ] Action module created: `actions/my_action.py`
- [ ] Function signature: `my_action_execute(...) -> dict`
- [ ] Return format includes `success` key
- [ ] Error handling with try-catch
- [ ] Logging implemented
- [ ] Registered in `agent/planner.py`
- [ ] Intent pattern added (if needed)
- [ ] Unit tests written
- [ ] Manually tested
- [ ] Documentation added to [ACTIONS.md](ACTIONS.md)

---

**For questions, see [ARCHITECTURE.md](ARCHITECTURE.md) or open an issue on GitHub.**
