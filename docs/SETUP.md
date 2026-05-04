# JARVISS Setup & Troubleshooting Guide

## Prerequisites

- **Windows 10/11** or later (64-bit recommended)
- **Python 3.11+**
- **Git** (for cloning the repo)
- **Microphone** (for voice input)
- **Speaker** (for feedback audio)
- **4 GB RAM** minimum (8 GB recommended)
- **Stable internet connection** (for weather, web search, APIs)

---

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/prasanthmukkiri/JARVIS--PERSONAL-AI-ASSISTENT.git
cd Jarvis-MK37
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv
```

### 3. Activate the Virtual Environment

**On PowerShell:**
```powershell
.venv\Scripts\Activate.ps1
```

**On Command Prompt:**
```cmd
.venv\Scripts\activate.bat
```

### 4. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

This installs:
- `pyautogui` — Desktop automation
- `pywinauto` — Windows UI automation
- `vosk` — Offline speech recognition
- `pyperclip` — Clipboard management
- `pygetwindow` — Window management
- And more (see `requirements.txt`)

### 5. Download Vosk Model

The Vosk speech recognition model is included in `models/vosk-en/`. If missing:

```bash
# Inside .venv
python
>>> from vosk import Model
>>> model = Model("models/vosk-en")
# If error, download from: https://alphacephei.com/vosk/models
```

### 6. Configure API Keys (Optional)

If you want to use weather, web search, or LLM features:

1. Edit `config/api_keys.json`:

```json
{
  "openweather_api_key": "your_key_here",
  "google_search_api_key": "your_key_here",
  "google_search_engine_id": "your_engine_id",
  "openai_api_key": "your_key_here",
  "os_system": "windows"
}
```

2. Obtain keys:
   - **OpenWeather:** https://openweathermap.org/api
   - **Google Search:** https://developers.google.com/custom-search
   - **OpenAI:** https://platform.openai.com/api-keys

### 7. Configure Microphone

**Windows 10/11:**
1. Right-click the speaker icon (bottom-right).
2. Select **Sound settings**.
3. Scroll to **Advanced** → **App volume and device preferences**.
4. Set your microphone as the default input device.
5. Test by running: `python -c "import sounddevice; print(sounddevice.query_devices())"`

### 8. Optional: Install Tesseract OCR

For advanced WhatsApp verification:

1. Download installer: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default location: `C:\Program Files\Tesseract-OCR`
3. Install pytesseract:
   ```bash
   pip install pytesseract
   ```

---

## Running JARVISS

### Start the Assistant

```bash
python main.py
```

**Expected output:**
```
[INFO] JARVISS initialized
[INFO] Listening for wake-word...
```

### Basic Commands

Speak after the wake-word ("Jarvis"):

```
"Jarvis, open Chrome"
"Jarvis, what's the weather?"
"Jarvis, send a message to Prasanth"
```

### Exit

- Say "Jarvis, goodbye" or
- Press `Ctrl+C` in the terminal

---

## Configuration

### Wake-Word Settings

Edit `memory/config_manager.py`:

```python
config = {
    "wake_word": "jarvis",  # Change to your preference
    "wake_word_sensitivity": 0.5,  # 0.0 (easy) to 1.0 (strict)
    "timeout_seconds": 30,  # Max command duration
    "max_retries": 3,  # Retry failed actions
}
```

### Default Apps

```python
config = {
    "default_browser": "chrome",  # or "firefox", "edge"
    "default_messaging_platform": "whatsapp",
    "default_search_engine": "google",
}
```

### Logging

```python
config = {
    "log_level": "INFO",  # DEBUG, INFO, WARNING, ERROR
    "log_file": "jarvis_log.txt",
    "save_debug_snapshots": True,  # WhatsApp screenshots
}
```

---

## Troubleshooting

### Microphone Not Detected

**Symptom:** "No microphone found" or audio not captured.

**Solutions:**
1. Check Windows Sound settings (see step 7 above).
2. Test microphone independently:
   ```bash
   python -c "import sounddevice; import numpy as np; print(np.sum(sounddevice.rec(44100, channels=1, samplerate=44100)))"
   ```
3. Restart JARVISS.
4. Try a different USB microphone.

---

### Wake-Word Not Detected

**Symptom:** JARVISS doesn't respond to "Jarvis".

**Solutions:**
1. **Speak louder and clearer** after the wake-word.
2. **Lower sensitivity** if too many false positives:
   ```python
   config["wake_word_sensitivity"] = 0.3  # More relaxed
   ```
3. **Use a different wake-word** (less likely to conflict):
   ```python
   config["wake_word"] = "computer"  # Or "hey", "ok", etc.
   ```
4. **Check microphone input:**
   ```bash
   python tools/test_microphone.py
   ```

---

### Commands Not Recognized

**Symptom:** JARVISS hears you but doesn't understand.

**Solutions:**
1. **Be specific:** Instead of "open browser", say "open Chrome".
2. **Pause before speaking:** Wait 0.5 seconds after "Jarvis" before your command.
3. **Enunciate clearly:** Avoid mumbling or background noise.
4. **Check logs:**
   ```bash
   tail -f jarvis_log.txt
   ```

---

### WhatsApp Send Fails

**Symptom:** "Message sent to X via WhatsApp" but message never appears.

**Solutions:**

#### 1. Verify WhatsApp Desktop is Installed
- JARVISS requires **WhatsApp Desktop**, not WhatsApp Web.
- Download: https://www.whatsapp.com/download

#### 2. Check Contact Exists
```
"Jarvis, send a message to Prasanth"
→ WhatsApp must have a contact named "Prasanth"
```

#### 3. Enable Debug Mode
```bash
# Edit tools/test_send.py
import sys
sys._send_debug = True

# Run
python tools/test_send.py
```

This saves screenshots to `tools/send_debug/`:
- `*_before_paste.png` — App state before typing
- `*_after_click_input.png` — After focusing composer
- `*_after_paste.png` — After typing message
- `*_after_send.png` — After sending

#### 4. Inspect Screenshots
Compare the screenshots to WhatsApp's actual layout. The click coordinates may need tuning if your screen resolution differs.

#### 5. Manual Test
```bash
python -c "
from actions.send_message import send_message
result = send_message({
    'receiver': 'Prasanth',
    'message_text': 'test',
    'platform': 'whatsapp',
    'debug': True,
    'auto_confirm': True
})
print(result)
"
```

#### 6. Check Focus
Ensure WhatsApp window gets focus after launch:
```bash
# Quick test
python -c "
from actions.send_message import _launch_whatsapp_desktop
_launch_whatsapp_desktop()
# WhatsApp window should appear within 2-3 seconds
"
```

---

### API Keys Not Working

**Symptom:** Weather/search commands fail silently.

**Solutions:**
1. **Verify keys in `config/api_keys.json`:**
   ```bash
   cat config/api_keys.json
   ```
   Keys should look like:
   ```json
   {
     "openweather_api_key": "1234567890abcdef...",
     "google_search_api_key": "AIza...",
     "google_search_engine_id": "e123..."
   }
   ```

2. **Test key validity:**
   ```bash
   python tools/test_api_keys.py
   ```

3. **Check API limits:**
   - OpenWeather: https://openweathermap.org/api-usage
   - Google: https://console.cloud.google.com

4. **Regenerate keys:**
   - Delete old keys from web console.
   - Create new keys and copy to `config/api_keys.json`.

---

### App Launch Fails

**Symptom:** "Could not open Chrome" or app doesn't appear.

**Solutions:**
1. **Verify app is installed:**
   ```bash
   # Check if app exists
   where chrome
   # or
   dir "C:\Program Files\Google\Chrome\Application\chrome.exe"
   ```

2. **Use full app name:**
   - Instead of "browser", say "Chrome" or "Google Chrome".
   - Instead of "editor", say "Notepad" or "Visual Studio Code".

3. **Add app to PATH** (if not found):
   - Windows Settings → System → Advanced system settings.
   - Environment Variables → PATH → Add app folder.

---

### Performance Issues

**Symptom:** Slow startup or laggy response.

**Solutions:**
1. **Check disk space:** Ensure at least 1 GB free.
2. **Close background apps:** Free up RAM.
3. **Disable debug mode:**
   ```python
   sys._send_debug = False
   ```
4. **Reduce history size:**
   ```bash
   # Trim jarvis_log.txt
   echo "" > jarvis_log.txt
   ```

---

### Logs Show Errors

**Check logs:**
```bash
# View last 20 lines
tail -n 20 jarvis_log.txt

# View all errors
grep ERROR jarvis_log.txt

# Tail in real-time
tail -f jarvis_log.txt
```

**Common errors:**
- `Could not find window for [app]` → App didn't launch
- `PyAutoGUI fail-safe triggered` → Mouse moved to corner (disable failsafe)
- `API rate limit exceeded` → Wait or upgrade API plan

---

## Testing

### Run Test Suite

```bash
# Test WhatsApp send
python tools/test_send.py

# Test weather API
python -c "
from actions.weather_report import weather_execute
result = weather_execute('london')
print(result)
"

# Test web search
python -c "
from actions.web_search import web_search_execute
result = web_search_execute('python tutorial')
print(result['data'][:2])
"
```

---

## Advanced Configuration

### Custom Wake-Word + Sensitivity

```python
# memory/config_manager.py
config = {
    "wake_word": "computer",
    "wake_word_sensitivity": 0.7,  # Higher = stricter
}
```

### Disable PyAutoGUI Fail-Safe

**Warning:** Only for testing. Re-enable in production.

```python
import pyautogui
pyautogui.FAILSAFE = False  # Default True
```

### Custom Timeout

```python
# agent/executor.py
COMMAND_TIMEOUT = 60  # seconds
```

---

## Uninstall

```bash
# Deactivate venv
deactivate

# Delete venv
rmdir /s .venv

# Delete logs
del jarvis_log.txt

# Keep config/api_keys.json if re-installing
```

---

## Getting Help

1. **Check logs:**
   ```bash
   tail -f jarvis_log.txt
   ```

2. **Enable debug:**
   ```python
   import sys
   sys._send_debug = True
   ```

3. **Review [ARCHITECTURE.md](ARCHITECTURE.md)** for system details.

4. **Open an issue** on GitHub with logs and screenshots.

---

## Performance Benchmarks

| Metric | Target | Typical |
|--------|--------|---------|
| Startup time | < 3s | 2–3s |
| Command latency | 300–800ms | 400–700ms |
| Idle memory | < 200 MB | 150–200 MB |
| CPU (idle) | < 5% | 1–3% |
| CPU (running) | < 50% | 20–40% |

---

**For more details, see [ARCHITECTURE.md](ARCHITECTURE.md) or [README.md](../README.md).**
