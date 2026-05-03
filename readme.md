# JARVISS / Jarvis-MK37

JARVISS is a personal AI assistant for Windows built to turn natural language and voice commands into real desktop actions.

## Quick Demo

Example command:

```text
send message to chinni on whatsapp saying hiii
```

What happens:

- JARVISS opens WhatsApp Desktop
- It searches the contact name
- It opens the chat
- It sends the message

## Screenshots

These workflow snapshots were captured during development:

![Before typing](tools/send_debug/20260503T100913583280_before_paste.png)

![After focusing the input](tools/send_debug/20260503T100914689841_after_click_input.png)

![After sending the message](tools/send_debug/20260503T100915930001_after_send.png)

## Ownership

This project is fully owned, authored, and created by FatihMakes.

No other personal authorship, ownership, or contributor credits are included in this README. If the project is reused, shared, or referenced elsewhere, FatihMakes should remain clearly credited as the sole owner and maker.

## Features

- Voice wake-word detection and assistant conversation flow
- Desktop app launching and control
- Browser automation and web search
- Messaging support for supported platforms
- Weather lookup and reminders
- Screen processing and visual task support
- YouTube video search and playback
- Memory handling and prompt-based assistant logic
- Helper tools for code, files, games, and device actions

## Project Layout

- `main.py` - application entry point
- `ui.py` - assistant UI
- `wake_word.py` - wake-word detector
- `actions/` - task-specific automation modules
- `agent/` - planning, execution, and error handling
- `memory/` - local memory management
- `config/` - configuration and API key files
- `core/` - prompt and assistant core text
- `models/` - bundled speech and AI model assets

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Optional setup script:

```bash
python setup.py
```

## Run

Start the assistant:

```bash
python main.py
```

## Notes

- Designed primarily for Windows desktop automation.
- Some features depend on installed apps, browser access, and valid API keys.
- Logs are written to `jarvis_log.txt`.
- Development snapshots used for debugging are stored under `tools/send_debug/`.

## License

No license is declared yet. All rights are reserved by FatihMakes unless a separate license is added later.
