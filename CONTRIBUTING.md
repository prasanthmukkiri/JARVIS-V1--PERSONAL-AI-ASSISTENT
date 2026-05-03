# Contributing to Jarvis-MK37

## Quick Setup

```bash
# Clone and setup
git clone https://github.com/prasanthmukkiri/JARVIS--PERSONAL-AI-ASSISTENT.git
cd Jarvis-MK37

# Create virtual environment
python -m venv venv
source venv/Scripts/activate  # Windows
# or: source venv/bin/activate  (macOS/Linux)

# Install dependencies
pip install -e .
pip install -e ".[dev]"  # includes pytest, black, pylint
```

## Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=actions --cov=agent --cov-report=html

# Run specific test
pytest tests/test_actions.py::TestBrowserControl::test_normalize_url_with_schema -v
```

## Code Quality

```bash
# Format code
black .

# Check formatting
black --check .

# Lint code
pylint actions/*.py agent/*.py --exit-zero

# Type checking (optional)
mypy actions/ agent/ --ignore-missing-imports
```

## Running Jarvis Locally

```bash
# Start the voice assistant
python main.py

# The system will:
# 1. Initialize VAD and speech recognition
# 2. Listen for wake word ("jarvis", "hey jarvis", etc.)
# 3. Activate and wait for commands
# 4. Log to stdout and jarvis_log.txt

# Say: "jarvis, open chrome"
# Expected: Activates existing taskbar Chrome or launches new instance with first profile

# Say: "jarvis, search for python tutorials"
# Expected: Performs Google search in existing Chrome window

# Say: "jarvis, go to sleep"
# Expected: Returns to sleep mode (won't process commands until re-awakened)
```

## Debugging

### Enable Detailed Logging

Edit `main.py` and set:
```python
DEBUG = True
```

### Test Browser Actions Directly

```python
from actions import browser_control

# Test native Chrome activation
result = browser_control._native_chrome_open("https://google.com")
print(result)

# Test URL normalization
from actions.browser_control import _normalize_url
print(_normalize_url("github"))  # → https://github.com
```

### Test Audio/VAD

```python
from wake_word import _detect_speech_activity, _list_input_devices

# List microphones
devices = _list_input_devices()
for d in devices:
    print(f"{d['index']}: {d['name']}")

# Test VAD on a chunk (requires webrtcvad)
import sounddevice as sd
import numpy as np

# Record 1 second of audio
audio = sd.rec(16000, samplerate=16000, channels=1, dtype='int16')
sd.wait()

is_speech = _detect_speech_activity(audio.tobytes())
print(f"Speech detected: {is_speech}")
```

## Making Changes

1. **Create a feature branch:**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes** and add tests in `tests/`

3. **Run tests locally:**
   ```bash
   pytest tests/ -v
   black . && pylint actions/ agent/ --exit-zero
   ```

4. **Commit with clear messages:**
   ```bash
   git commit -m "feat: add multi-device mic selection to wake word detector"
   ```

5. **Push and create a PR:**
   ```bash
   git push origin feature/your-feature-name
   ```

6. **GitHub Actions will automatically run CI/CD** — review the status in your PR

## Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| `ImportError: No module named 'vosk'` | `pip install vosk` + download model to `models/vosk-en/` |
| `Chrome opens profile picker` | Ensure `_chrome_profile_name()` returns valid profile. Check `~/.config/google-chrome/` on Linux or `%APPDATA%/.../Chrome/` on Windows |
| `Google STT fails (no internet)` | Use local Vosk backend instead. Or allow internet for Google Cloud Speech-to-Text |
| `Tests timeout on CI` | Increase `timeout` in `pytest.ini` or mark slow tests with `@pytest.mark.slow` |
| `pylint gives false positives` | Disable specific check in `.pylintrc` or add `# pylint: disable=...` inline |

## Architecture Overview

```
main.py                          # Entry point, orchestrates all systems
├── wake_word.py                 # Voice activity detection & wake word
├── ui.py                        # UI callbacks and logging
├── agent/
│   ├── planner.py               # Converts goals → step plans
│   ├── executor.py              # Executes plans step-by-step
│   ├── error_handler.py         # Analyzes errors & generates fixes
│   └── task_queue.py            # Background task management
├── actions/                     # Pluggable action modules
│   ├── browser_control.py       # Playwright browser automation
│   ├── open_app.py              # Native app launcher
│   ├── code_helper.py           # AI code generation & execution
│   ├── web_search.py
│   ├── file_controller.py
│   └── ...more actions
├── core/                        # Core utilities
│   └── prompt.txt               # System prompt for LLM
├── memory/                      # Persistent memory
│   ├── memory_manager.py
│   └── long_term.json
└── models/                      # ASR models
    └── vosk-en/                 # Local speech recognition model
```

## Code Style Guide

- **Line length:** 120 characters (black default)
- **Docstrings:** Use Google-style docstrings for public functions
- **Type hints:** Recommended for function signatures (Python 3.11+)
- **Error handling:** Try/except with specific exceptions; log errors
- **Logging:** Use `print()` for user-facing, `self._log()` for agent logging
- **Comments:** Explain "why", not "what" (code shows what)

## Performance Considerations

- **Wake word detection:** Runs continuously; optimize to < 100ms per chunk
- **Browser automation:** Use Playwright persistent contexts (reuse instead of new instances)
- **Speech recognition:** Local (Vosk) preferred over cloud (Google STT) for latency
- **Memory:** Long-term memory stored in JSON; consider SQLite for large datasets

## Security Notes

- API keys stored in `config/api_keys.json` — never commit to git
- Generated code executed in subprocess — validate before running
- Browser sessions inherit user profiles — be careful with credentials

---

For more details, see:
- [VISION.md](VISION.md) — Strategic goals and principles
- [ROADMAP.md](ROADMAP.md) — Multi-phase development plan
- [SESSION_IMPROVEMENTS.md](SESSION_IMPROVEMENTS.md) — Recent enhancements
