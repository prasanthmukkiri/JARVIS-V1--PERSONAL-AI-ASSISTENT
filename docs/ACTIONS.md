# JARVISS Actions Reference

## Overview

This document lists all available actions (commands) JARVISS can execute. Each action responds to natural language variations of the same command.

---

## App & Window Control

### Open Application

**Command variants:**
- "Open Chrome"
- "Launch Notepad"
- "Start Visual Studio Code"
- "Open Discord"

**Implementation:** `actions/open_app.py`

**How it works:**
1. Searches for app by name (Windows Search).
2. Launches application.
3. Waits for window to appear and activates it.

**Example:**
```
"Jarvis, open Chrome"
→ [Launches Chrome]
"Jarvis, open Notepad"
→ [Opens Notepad]
```

---

### Close Application

**Command variants:**
- "Close Chrome"
- "Quit Notepad"
- "Stop Discord"

**Implementation:** `actions/open_app.py`

**How it works:**
1. Finds window by app name.
2. Sends close signal (Alt+F4 or window.close()).

**Example:**
```
"Jarvis, close Chrome"
→ [Closes all Chrome windows]
```

---

## Web & Search

### Web Search

**Command variants:**
- "Search for Python tutorials"
- "Find information on machine learning"
- "Search: latest news"
- "Google: weather today"

**Implementation:** `actions/web_search.py`

**How it works:**
1. Queries Google Search API.
2. Returns top 5–10 results with titles, snippets, URLs.
3. Optional: opens first result in default browser.

**Example:**
```
"Jarvis, search for Python tutorials"
→ [Returns results]
→ [Optionally opens first result]

Output:
  1. Real Python — Learn Python Programming
  2. W3Schools — Python Tutorial
  3. Khan Academy — Python for Everyone
  ...
```

**Required API keys:**
- `google_search_api_key`
- `google_search_engine_id`

---

### Open URL

**Command variants:**
- "Open google.com"
- "Go to GitHub"
- "Visit amazon.com"
- "Navigate to youtube.com"

**Implementation:** `actions/browser_control.py`

**How it works:**
1. Launches default browser.
2. Navigates to URL.

**Example:**
```
"Jarvis, open github.com"
→ [Opens browser and navigates to github.com]
```

---

## Messaging

### Send WhatsApp Message

**Command variants:**
- "Send a message to Prasanth"
- "Tell Prasanth hello"
- "Message Prasanth saying I'm running late"
- "Send WhatsApp to Mom"

**Implementation:** `actions/send_message.py`

**How it works:**
1. Launches WhatsApp Desktop.
2. Opens search and finds contact by name.
3. Verifies correct contact (optional OCR).
4. Enters message text.
5. Clicks Send button or presses Enter.

**Parameters:**
- `receiver` (string) — Contact name
- `message_text` (string) — Message to send
- `platform` (string) — "whatsapp" (default)

**Example:**
```
"Jarvis, send a message to Prasanth saying hello"
→ [Opens WhatsApp]
→ [Searches for Prasanth]
→ [Opens chat]
→ [Types "hello"]
→ [Sends]
→ "Message sent to Prasanth"
```

**Requirements:**
- WhatsApp Desktop installed (not Web)
- Contact must exist in WhatsApp
- Valid contact name (not phonetic spelling)

**Troubleshooting:** See [SETUP.md#whatsapp-send-fails](SETUP.md#whatsapp-send-fails)

---

## Weather & Time

### Get Weather

**Command variants:**
- "What's the weather in London?"
- "Weather in New York"
- "Is it raining tomorrow?"
- "Tell me the forecast for Paris"

**Implementation:** `actions/weather_report.py`

**How it works:**
1. Calls OpenWeather API.
2. Returns current conditions (temp, humidity, wind).
3. Optional: reads aloud using text-to-speech.

**Parameters:**
- `location` (string) — City or coordinates
- `forecast` (bool) — Include forecast (default: current only)

**Example:**
```
"Jarvis, what's the weather in London?"
→ "Current weather in London: 15°C, Cloudy, Humidity 72%"

"Jarvis, 5-day forecast for Paris"
→ [Returns 5-day forecast]
```

**Required API key:**
- `openweather_api_key`

---

### Set Reminder

**Command variants:**
- "Remind me to call Mom at 6 PM"
- "Set a reminder for lunch at noon"
- "Remind me to take medicine in 30 minutes"
- "Alert me at 5 PM"

**Implementation:** `actions/reminder.py`

**How it works:**
1. Parses time and reminder text.
2. Stores in `memory/long_term.json`.
3. Background timer triggers reminder at scheduled time.
4. Notification displayed or read aloud.

**Parameters:**
- `reminder_text` (string) — What to remind about
- `time` (string or datetime) — When to remind

**Example:**
```
"Jarvis, remind me to call Mom at 6 PM"
→ "Reminder set for 6 PM: Call Mom"

[At 6 PM]
→ 🔔 Reminder: Call Mom
```

---

### List Reminders

**Command variants:**
- "Show my reminders"
- "What reminders do I have?"
- "List all reminders"

**Implementation:** `actions/reminder.py`

**Example:**
```
"Jarvis, show my reminders"
→ "You have 2 reminders:
   1. Call Mom at 6 PM
   2. Take medicine at 8 AM"
```

---

## File & System Control

### Open File

**Command variants:**
- "Open file my-document.txt"
- "Open PDF report"
- "Show files in Downloads"

**Implementation:** `actions/file_controller.py`

**How it works:**
1. Finds file by name in common locations (Desktop, Documents, Downloads).
2. Opens with default application.

**Example:**
```
"Jarvis, open file report.pdf"
→ [Opens report.pdf in PDF reader]
```

---

### List Files

**Command variants:**
- "List files in Desktop"
- "Show files in Documents"
- "What's in Downloads?"

**Implementation:** `actions/file_controller.py`

**Example:**
```
"Jarvis, list files in Documents"
→ "Documents contains:
   - report.docx
   - budget.xlsx
   - notes.txt"
```

---

### Search Files

**Command variants:**
- "Find all PDF files"
- "Search for invoices"
- "Look for presentations"

**Implementation:** `actions/file_controller.py`

**Example:**
```
"Jarvis, find all PDF files"
→ "Found 5 PDFs:
   - invoice_2024.pdf
   - contract.pdf
   - ..."
```

---

## Media & Entertainment

### Search YouTube

**Command variants:**
- "Play a video about Python"
- "Search YouTube for gaming"
- "Find a tutorial on machine learning"

**Implementation:** `actions/youtube_video.py`

**How it works:**
1. Searches YouTube for query.
2. Returns top results.
3. Optional: opens first result in browser or YoutTube app.

**Example:**
```
"Jarvis, play a video about Python"
→ "Opening YouTube search for 'Python'..."
→ [Opens browser with results]
```

---

## Development & Coding

### Code Helper

**Command variants:**
- "Help me with Python syntax"
- "Explain this error"
- "Debug my code"
- "What's a lambda function?"

**Implementation:** `actions/code_helper.py`

**How it works:**
1. Accepts code snippet or error.
2. Calls LLM (Claude/GPT-4) for explanation.
3. Returns structured answer.

**Example:**
```
"Jarvis, what's a lambda function?"
→ "A lambda function is a small anonymous function in Python...
   Example: square = lambda x: x ** 2"
```

**Required API key:**
- `openai_api_key` or `anthropic_api_key`

---

### Command Execution

**Command variants:**
- "Run this command: `ls`"
- "Execute: `dir C:\`"

**Implementation:** `dev_agent.py`

**⚠️ Warning:** Limited to safe commands. Destructive commands are blocked.

**Example:**
```
"Jarvis, execute: dir Desktop"
→ [Lists Desktop files]
```

---

## Utilities & Helpers

### Emotion Detection

**Command:** "Analyze image emotion" or "Detect sentiment"

**Implementation:** `actions/emotion_detector.py`

**How it works:**
1. Takes screenshot or image input.
2. Analyzes facial expressions.
3. Returns emotion estimate (happy, sad, neutral, etc.).

---

### Face Recognition

**Command:** "Recognize person in image"

**Implementation:** `actions/face_recognition.py`

**How it works:**
1. Takes screenshot or image.
2. Detects and identifies faces.
3. Matches against known database (if available).

---

### System Settings

**Command variants:**
- "Set volume to 50"
- "Increase brightness"
- "Mute speakers"

**Implementation:** `actions/computer_settings.py`

**Example:**
```
"Jarvis, set volume to 50"
→ "Volume set to 50%"
```

---

### Game Management

**Command variants:**
- "Update Steam games"
- "Check for game updates"

**Implementation:** `actions/game_updater.py`

**Example:**
```
"Jarvis, update Steam games"
→ "Checking for updates...
   1 update available: Cyberpunk 2077
   Downloading..."
```

---

## Context & Memory

### Remember Information

**Command variants:**
- "Remember that I like coffee"
- "Note: Prasanth's birthday is May 4"

**Implementation:** `memory/memory_manager.py`

**How it works:**
1. Parses statement and extracts key information.
2. Stores in `memory/long_term.json`.
3. Recalled in future interactions.

**Example:**
```
"Jarvis, remember that my favorite coffee is espresso"
→ "Got it! I'll remember your coffee preference"

[Later]
"Jarvis, what's my favorite coffee?"
→ "Your favorite coffee is espresso"
```

---

### Show History

**Command variants:**
- "What did I ask you earlier?"
- "Show my command history"
- "What was my last reminder?"

**Implementation:** `memory/memory_manager.py`

**Example:**
```
"Jarvis, show my history"
→ "Recent commands:
   1. Send message to Prasanth
   2. Check weather in London
   3. Open Chrome"
```

---

## Configuration & Management

### View Settings

**Command:** "Show my settings" or "What are my preferences?"

**Example:**
```
"Jarvis, show settings"
→ "Current settings:
   - Wake-word: jarvis
   - Default browser: Chrome
   - Messaging app: WhatsApp"
```

---

### Change Settings

**Command:** "Change [setting] to [value]"

**Example:**
```
"Jarvis, change default browser to Firefox"
→ "Default browser updated to Firefox"
```

---

## Status & Help

### Status Check

**Command variants:**
- "Are you ready?"
- "What's your status?"
- "Check system status"

**Example:**
```
"Jarvis, are you ready?"
→ "Ready to assist! Memory loaded. All systems operational."
```

---

### Help Menu

**Command variants:**
- "Help me"
- "What can you do?"
- "Show available commands"

**Example:**
```
"Jarvis, help"
→ "I can help with:
   - Open apps (Chrome, Notepad, ...)
   - Search the web
   - Send messages (WhatsApp)
   - Check weather
   - Set reminders
   - Manage files
   - And more!"
```

---

## Command Structure

### Full Command Format

```
"Jarvis, [action] [parameters]"
```

**Examples:**
```
"Jarvis, open Chrome"
"Jarvis, search for Python tutorials"
"Jarvis, send a message to Prasanth saying hello"
"Jarvis, what's the weather in London?"
"Jarvis, remind me to take medicine at 8 AM"
```

---

## Tips for Best Results

1. **Speak clearly** — Pause briefly after "Jarvis".
2. **Be specific** — Use full names and exact app titles.
3. **One command at a time** — Wait for response before next command.
4. **Natural phrasing** — JARVISS understands conversational language.
5. **Use memory** — Remember context from earlier commands.

---

## Adding Custom Actions

See [API_REFERENCE.md](API_REFERENCE.md) for how to create new actions.

---

## Troubleshooting

**Command not recognized?**
- Check logs: `tail jarvis_log.txt`
- Verify API keys in `config/api_keys.json`
- Try rephrasing (e.g., "search" instead of "google")

**Action fails silently?**
- Enable debug mode: `sys._send_debug = True`
- Check for error logs
- See [SETUP.md](SETUP.md) for troubleshooting

---

**For detailed system architecture, see [ARCHITECTURE.md](ARCHITECTURE.md).**
