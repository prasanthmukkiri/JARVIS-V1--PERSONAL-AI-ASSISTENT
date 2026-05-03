# JARVISS / Jarvis-MK37

**Official repository of JARVISS, created and owned by Prasanth Mukkiri.**

JARVISS is a personal AI assistant for Windows built to turn natural language and voice commands into real desktop actions.

## Advanced Capabilities

JARVISS can handle a wide range of assistant tasks beyond messaging:

- Open and control desktop applications
- Launch browsers and perform web searches
- Send messages on supported platforms
- Check weather and create reminders
- Process screen content and visual tasks
- Search and play YouTube videos
- Handle files, code, and helper workflows
- Use memory and prompt-based assistant logic

Example commands:

```text
open chrome
search for python tutorials
set a reminder for 7 pm
what is the weather in london
play a youtube video about machine learning
```

## Screenshots

These workflow snapshots were captured during development:

![Before typing](tools/send_debug/20260503T100913583280_before_paste.png)

![After focusing the input](tools/send_debug/20260503T100914689841_after_click_input.png)

![After sending the message](tools/send_debug/20260503T100915930001_after_send.png)

## Ownership

This project is fully owned, authored, and created by Prasanth Mukkiri.

Prasanth Mukkiri is the sole maker, sole owner, and original author of this project. No other personal authorship, ownership, or contributor credits are included in this README.

If the project is reused, shared, or referenced elsewhere, Prasanth Mukkiri must remain clearly credited as the official owner and maker.

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

## Official Status

This repository is the official JARVISS project maintained by Prasanth Mukkiri.

## License

No license is declared yet. All rights are reserved by Prasanth Mukkiri unless a separate license is added later.
