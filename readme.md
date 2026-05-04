# JARVISS — Personal AI Assistant for Windows

**Official repository created and owned by Prasanth Mukkiri.**

JARVISS is a sophisticated personal AI assistant that turns natural language voice commands into automated desktop actions. Combining speech recognition, LLM-based planning, and multi-platform automation, JARVISS can control your computer, search the web, send messages, manage files, and more—all through simple spoken commands.

![Version](https://img.shields.io/badge/version-V1-blue)
![Platform](https://img.shields.io/badge/platform-Windows-important)
![Python](https://img.shields.io/badge/python-3.11%2B-brightgreen)
![License](https://img.shields.io/badge/license-Proprietary-red)

---

## 🚀 Key Features

### Voice & Speech Recognition
- **Wake-word detection** — responds to custom wake words (e.g., "Jarvis").
- **Vosk ASR** — local, privacy-first speech-to-text using offline models.
- **Natural language understanding** — understands complex requests and converts them to actionable tasks.

### Desktop Automation
- **App launching** — open any installed Windows application.
- **Window control** — focus, minimize, maximize windows; send keystrokes.
- **File operations** — navigate, search, and manipulate files and folders.
- **Browser automation** — open links, perform web searches, visit websites.

### Communication & Messaging
- **WhatsApp Desktop** — send messages to contacts reliably via desktop app.
- **Message platforms** — extensible support for multiple messaging services.
- **Contact management** — search and verify recipients before sending.

### Information & Utilities
- **Weather lookup** — get current conditions for any location.
- **Web search** — search Google and retrieve results.
- **YouTube** — find and play videos.
- **Reminders** — set and manage time-based reminders.

### Intelligence & Memory
- **Long-term memory** — store and recall user preferences and past interactions.
- **Smart planning** — decompose complex requests into steps.
- **Context-aware execution** — adapt behavior based on user history.
- **Error recovery** — graceful fallbacks and user prompts on failures.

### Developer-Friendly
- **Modular action architecture** — easily add new skills and commands.
- **Debug snapshots** — automated screenshot capture for troubleshooting.
- **Comprehensive logging** — full audit trail to `jarvis_log.txt`.
- **Extensible configuration** — API keys, behavior settings, and customization.

---

## 📋 Quick Start

### Requirements
- **Windows 10/11** (or later)
- **Python 3.11+**
- **Microphone** (for voice input)
- **Optional**: Tesseract OCR (for advanced verification)

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/prasanthmukkiri/JARVIS--PERSONAL-AI-ASSISTENT.git
   cd Jarvis-V1
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure API keys** (optional, for web/weather/LLM features):
   ```bash
   # Edit config/api_keys.json and add your keys
   ```

5. **Run the assistant:**
   ```bash
   python main.py
   ```

---

## 💬 Usage Examples

Once running, speak to JARVISS after the wake-word:

```
"Jarvis, open Chrome"
→ Launches Google Chrome

"Jarvis, send a message to Prasanth"
→ Opens WhatsApp, finds Prasanth, and prompts for message

"Jarvis, search for Python tutorials"
→ Performs a web search and displays results

"Jarvis, what's the weather in London?"
→ Fetches and reads current weather

"Jarvis, remind me to call Mom at 6 PM"
→ Sets a reminder and stores it locally
```

---

## 🏗️ Architecture

### Directory Structure

```
├── main.py                  # Entry point
├── ui.py                    # User interface
├── wake_word.py            # Wake-word detection
├── requirements.txt        # Dependencies
├── actions/                # Automation modules
│   ├── send_message.py     # WhatsApp, messaging
│   ├── browser_control.py  # Browser automation
│   ├── web_search.py       # Web search
│   ├── weather_report.py   # Weather API
│   ├── open_app.py         # App launching
│   └── ...
├── agent/                  # Planning & execution
│   ├── planner.py         # Task decomposition
│   ├── executor.py        # Command execution
│   └── error_handler.py
├── memory/                # Persistence
│   ├── memory_manager.py
│   └── long_term.json
├── config/                # Configuration
│   └── api_keys.json
├── core/                  # Core prompts
│   └── prompt.txt
├── models/               # Pre-trained models
│   └── vosk-en/
├── tools/               # Dev utilities
│   └── send_debug/      # Debug screenshots
└── docs/                # Documentation
    ├── ARCHITECTURE.md
    ├── SETUP.md
    └── ACTIONS.md
```

---

## 📦 Dependencies

- **pyautogui** — Desktop automation.
- **pywinauto** — Windows UI automation.
- **vosk** — Offline speech recognition.
- **pyperclip** — Clipboard management.
- **pytesseract** — OCR (optional).

See `requirements.txt` for full list.

---

## 📚 Documentation

- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** — System design and technical details.
- **[SETUP.md](docs/SETUP.md)** — Installation and troubleshooting.
- **[ACTIONS.md](docs/ACTIONS.md)** — Available commands and actions.
- **[TEST_CHECKLIST.md](docs/TEST_CHECKLIST.md)** — End-to-end test checklist for Jarvis.
- **[API_REFERENCE.md](docs/API_REFERENCE.md)** — How to add custom actions.

---

## 🧪 Testing

```bash
# Test WhatsApp send
python tools/test_send.py

# Enable debug mode
import sys
sys._send_debug = True
```

Debug artifacts: `tools/send_debug/`

---

## 🐛 Troubleshooting

### Microphone not detected
- Check Windows Sound Settings.
- Restart the application.

### Commands not recognized
- Speak clearly after wake-word.
- Verify microphone volume.

### WhatsApp send fails
- Ensure WhatsApp Desktop is installed.
- Check contact name exists.
- See `tools/send_debug/` screenshots.

---

## 🚀 Roadmap

- [ ] Multi-language support
- [ ] Cloud sync
- [ ] Community plugins
- [ ] Mobile app
- [ ] Email & calendar integration

---

## 🤝 Contributing

1. Fork the repository.
2. Create a feature branch: `git checkout -b feature/your-feature`.
3. Commit changes: `git commit -m "Add feature"`.
4. Push and open a pull request.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 👤 Author & Ownership

**Prasanth Mukkiri** — Sole creator, owner, and developer of JARVISS.

This project represents original work in personal AI assistant development, desktop automation, and voice command processing.

---

## 📄 License

**Proprietary** — All rights reserved by Prasanth Mukkiri. Unauthorized copying or distribution is prohibited.

---

**Made with ❤️ by Prasanth Mukkiri**
