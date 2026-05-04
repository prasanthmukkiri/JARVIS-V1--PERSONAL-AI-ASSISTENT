# JARVISS Architecture Guide

## System Overview

JARVISS follows a modular, event-driven architecture designed for extensibility and reliability. The system is organized into distinct layers:

```
┌─────────────────────────────────────────────────────────┐
│                   User Interface (UI)                     │
│              (Terminal / Graphical Display)              │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│           Wake-Word Detection & Audio Input             │
│                  (wake_word.py, Vosk)                    │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│              Speech-to-Text (ASR)                        │
│           (Vosk Model / Local Processing)               │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│           Intent & Plan Generation                      │
│            (agent/planner.py, LLM Core)                 │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│            Task Execution Engine                        │
│           (agent/executor.py, Task Queue)               │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│         Action Modules (Capabilities)                   │
│   send_message | open_app | web_search | weather ...    │
└────────────────────┬────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────┐
│         System Interaction Layer                        │
│   (pyautogui, pywinauto, file I/O, APIs)               │
└─────────────────────────────────────────────────────────┘
```

---

## Core Components

### 1. Main Application (`main.py`)

**Purpose:** Application entry point and lifecycle management.

**Responsibilities:**
- Initialize subsystems (UI, wake-word detector, memory).
- Start the main event loop.
- Handle graceful shutdown and cleanup.

**Key Methods:**
```python
def main():
    # Initialize
    ui = UserInterface()
    memory = MemoryManager()
    detector = WakeWordDetector()
    
    # Main loop
    while running:
        if detector.detected_wake_word():
            text = speech_to_text()
            execute_command(text, memory)
```

---

### 2. Wake-Word Detection (`wake_word.py`)

**Purpose:** Listen for activation phrase and trigger the assistant.

**How It Works:**
1. Continuously monitors microphone input.
2. Applies keyword spotting algorithm (e.g., "Jarvis").
3. When detected, signals the main loop to start listening.
4. Reduces false positives using confidence thresholds.

**Configuration:**
- Wake-word phrase (in `memory/config_manager.py`)
- Sensitivity level (0.0 to 1.0)
- Microphone input device

---

### 3. Speech Recognition (`Vosk ASR`)

**Purpose:** Convert spoken audio to text locally.

**Advantages:**
- No cloud dependency (privacy-first).
- Fast processing (~200–400ms per phrase).
- Works offline.
- Lightweight model (~50 MB).

**Model Location:** `models/vosk-en/`

**Integration:**
```python
from vosk import Model, KaldiRecognizer

model = Model("models/vosk-en")
recognizer = KaldiRecognizer(model, 16000)
recognizer.AcceptWaveform(audio_data)
result = json.loads(recognizer.Result())
```

---

### 4. Planner (`agent/planner.py`)

**Purpose:** Understand user intent and decompose requests into executable tasks.

**Process:**
1. **Parse Input:** Analyze natural language command.
2. **Identify Intent:** Determine what the user wants (e.g., "send message", "search web").
3. **Decompose:** Break complex requests into atomic actions.
4. **Generate Plan:** Create ordered task list with parameters.

**Example:**
```
User: "Send a message to Prasanth saying I'm running late"

Parse:
  Action: send_message
  Recipient: Prasanth
  Message: I'm running late
  Platform: whatsapp (default)

Generate Plan:
  1. Verify recipient exists in WhatsApp
  2. Open WhatsApp Desktop
  3. Search for "Prasanth"
  4. Open chat
  5. Type message
  6. Send
```

**Core Logic:**
- Uses rule-based matching (for common patterns).
- Can integrate with LLM (e.g., Claude, GPT-4) for complex requests.
- Stores action history for context.

---

### 5. Executor (`agent/executor.py`)

**Purpose:** Execute generated plans and manage task flow.

**Responsibilities:**
- Run actions sequentially.
- Handle errors and retries.
- Collect feedback and context.
- Update memory with results.

**Execution Model:**
```python
class Executor:
    def execute_plan(self, plan: List[Task]):
        for task in plan:
            try:
                result = execute_action(task)
                if result.success:
                    continue
                else:
                    handle_failure(task, result)
            except Exception as e:
                error_handler.log_and_retry(task, e)
```

**Error Recovery:**
- Retry up to N times with exponential backoff.
- Display user-friendly error messages.
- Suggest alternatives (e.g., "Try again" or "Open app manually").

---

### 6. Task Queue (`agent/task_queue.py`)

**Purpose:** Queue and manage tasks for processing.

**Features:**
- Priority queue (high-priority tasks execute first).
- Task deduplication (avoid duplicate commands).
- Concurrency control (prevent race conditions).

---

### 7. Error Handler (`agent/error_handler.py`)

**Purpose:** Manage failures gracefully.

**Strategies:**
- **Retry:** If transient, retry with backoff.
- **Fallback:** Use alternative action if primary fails.
- **User Prompt:** Ask for clarification or confirmation.
- **Log:** Record error details for debugging.

**Error Categories:**
- **Transient** (network timeout, app not ready) → Retry
- **User Error** (wrong recipient, unclear command) → Prompt
- **System Error** (app crashed, permission denied) → Fallback/Log

---

### 8. Action Modules (`actions/`)

Each action is a standalone module implementing a specific capability.

#### `send_message.py`
Sends messages via WhatsApp Desktop.
- Desktop-first approach (preferred over Web).
- Multi-step flow: launch app → search contact → open chat → type message → send.
- Verification: confirms correct contact before sending.

#### `open_app.py`
Opens installed applications.
- Windows app search via Win key + name.
- pygetwindow to find and activate windows.
- Timeout handling (app may take time to launch).

#### `web_search.py`
Searches the web using Google or Bing.
- Queries search engine API.
- Returns top results with titles and URLs.
- Optional: open first result in browser.

#### `browser_control.py`
Automates web browser tasks.
- Playwright integration for browser automation.
- Navigate to URLs, click elements, fill forms.

#### `weather_report.py`
Fetches weather data.
- Calls OpenWeather API.
- Returns current conditions or forecast.
- Caches data to reduce API calls.

#### `file_controller.py`
File system operations.
- List files, navigate folders.
- Search by name, extension.
- Read/write small text files.

#### `reminder.py`
Time-based reminders.
- Stores reminders in `memory/long_term.json`.
- Background timer checks and triggers at scheduled time.
- Read back reminders using text-to-speech.

---

### 9. Memory Manager (`memory/`)

#### `memory_manager.py`
Centralized memory orchestration.
- Loads/saves user data.
- Provides query interface.

#### `config_manager.py`
User settings and preferences.
- API keys, wake-word, default apps.
- Persisted in JSON.

#### `long_term.json`
User history and data.
- Reminders, preferences.
- Interaction history (optional).

**Memory Structure:**
```json
{
  "reminders": [
    {
      "id": "rem_001",
      "text": "Call Mom",
      "time": "18:00",
      "created_at": "2026-05-04T10:30:00Z"
    }
  ],
  "preferences": {
    "default_browser": "chrome",
    "default_messaging": "whatsapp",
    "language": "en"
  }
}
```

---

### 10. User Interface (`ui.py`)

**Purpose:** Display status, logs, and prompts to the user.

**Displays:**
- Current command being processed.
- Action status (running, success, failed).
- Error messages.
- User prompts (confirmation, clarification).

**Modes:**
- Terminal (CLI) - default.
- GUI (optional, via tkinter or PyQt).

---

## Data Flow

### Typical Command Execution

```
1. User speaks: "Send a message to Prasanth saying hello"
   ↓
2. Wake-word detector triggers
   ↓
3. Vosk converts audio to text: "send a message to prasanth saying hello"
   ↓
4. Planner parses and creates tasks:
     - Task 1: Launch WhatsApp Desktop
     - Task 2: Search for "Prasanth"
     - Task 3: Open chat
     - Task 4: Type message "hello"
     - Task 5: Send
   ↓
5. Executor runs each task:
     - Task 1: pyautogui/subprocess launches app
     - Task 2: pyautogui types search query
     - Task 3: pyautogui clicks search result
     - Task 4: pyautogui/pyperclip pastes message
     - Task 5: pyautogui presses Enter
   ↓
6. Memory updates:
     - Logs action to `jarvis_log.txt`
     - Updates interaction history
   ↓
7. UI confirms: "Message sent to Prasanth"
```

---

## Extension Points

### Adding a New Action

1. **Create a new file** in `actions/`:
   ```python
   # actions/my_action.py
   def my_action_execute(param1, param2, **kwargs):
       """Execute my custom action."""
       result = do_something(param1, param2)
       return {"success": True, "data": result}
   ```

2. **Register in Planner** (`agent/planner.py`):
   ```python
   ACTIONS = {
       "my_action": {
           "module": "actions.my_action",
           "function": "my_action_execute",
           "params": ["param1", "param2"]
       }
   }
   ```

3. **Test**:
   ```python
   from actions.my_action import my_action_execute
   result = my_action_execute("value1", "value2")
   ```

### Adding a New Intent

In `agent/planner.py`, add a pattern:

```python
INTENT_PATTERNS = {
    "my_intent": {
        "keywords": ["trigger", "keyword"],
        "actions": [
            {"name": "my_action", "params": {...}}
        ]
    }
}
```

---

## Configuration & Customization

### API Keys (`config/api_keys.json`)

```json
{
  "openai_api_key": "sk-...",
  "google_search_api_key": "AIza...",
  "google_search_engine_id": "e1234567890",
  "openweather_api_key": "1234567890abcdef",
  "os_system": "windows"
}
```

### Settings (`memory/config_manager.py`)

```python
config = {
    "wake_word": "jarvis",
    "wake_word_sensitivity": 0.5,
    "default_browser": "chrome",
    "default_messaging_platform": "whatsapp",
    "max_retries": 3,
    "timeout_seconds": 30
}
```

---

## Performance Considerations

### Startup Time
- **Goal:** < 3 seconds
- **Optimization:** Lazy-load heavy modules (Vosk, Playwright).

### Command Latency
- **Target:** 300–800ms (includes speech processing)
- **Optimization:** Cache models, parallel task execution where possible.

### Memory Footprint
- **Idle:** ~150–200 MB
- **Running:** ~250–350 MB
- **Optimization:** Unload unused modules, limit history size.

---

## Logging & Debugging

### Log Levels

- **DEBUG:** Detailed flow information.
- **INFO:** Key events (command recognized, action started).
- **WARNING:** Potential issues (API rate limit, app not found).
- **ERROR:** Failures (send failed, network error).

### Log File

All logs are written to `jarvis_log.txt`:

```
2026-05-04 10:30:15 [INFO] Wake-word detected
2026-05-04 10:30:16 [INFO] Recognized: "send message to prasanth"
2026-05-04 10:30:16 [INFO] Launching WhatsApp Desktop
2026-05-04 10:30:18 [INFO] Searching for "prasanth"
2026-05-04 10:30:19 [INFO] Opening chat with Prasanth
2026-05-04 10:30:20 [INFO] Message sent successfully
```

### Debug Mode

Enable debug snapshots (WhatsApp):

```python
import sys
sys._send_debug = True
sys._send_debug_dir = "tools/send_debug"
```

Screenshots saved to `tools/send_debug/`:
- `*_before_paste.png` — Before typing message
- `*_after_click_input.png` — After focusing composer
- `*_after_paste.png` — After pasting message
- `*_after_send.png` — After clicking send

---

## Testing Strategy

### Unit Tests

Test individual actions:

```python
from actions.web_search import web_search_execute

result = web_search_execute("python tutorial")
assert result["success"] is True
assert len(result["data"]) > 0
```

### Integration Tests

Test end-to-end flows:

```python
def test_send_message_flow():
    # Setup
    # Execute
    result = send_message_flow("pk", "hii")
    # Assert
    assert result["success"] is True
```

### Regression Tests

```bash
python tools/test_send.py --receiver pk --message hii
```

---

## Security Considerations

1. **API Keys:** Store in `config/api_keys.json` (gitignored).
2. **Local Processing:** Vosk runs locally (no cloud dependencies).
3. **Credentials:** Avoid logging sensitive data.
4. **User Confirmation:** Prompt before sending messages or deleting files.

---

## Future Enhancements

- **Distributed Execution:** Run actions on remote machines.
- **Multi-Language:** Add Spanish, Hindi, French support.
- **Cloud Sync:** Sync memory across devices.
- **Plugins:** Community-contributed skills.
- **Analytics:** Track command usage and success rates.

---

**For questions or contributions, see [CONTRIBUTING.md](CONTRIBUTING.md) or open an issue on GitHub.**
