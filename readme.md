# Jarvis V1 — Personal AI Assistant for Windows

**Created and owned by Prasanth Mukkiri.**

Jarvis V1 is a production-grade personal AI assistant powered by the **Google Gemini Live API**. It listens to your voice in real time, understands natural language, remembers everything about you across sessions, monitors your PC health, and executes complex multi-step tasks on your Windows desktop — all through a single spoken command.

![Version](https://img.shields.io/badge/version-V1-blue)
![Platform](https://img.shields.io/badge/platform-Windows-important)
![Python](https://img.shields.io/badge/python-3.11%2B-brightgreen)
![Tests](https://img.shields.io/badge/tests-140%20passing-brightgreen)
![License](https://img.shields.io/badge/license-Proprietary-red)

---

## What Makes This V1

Jarvis V1 is not a chatbot with a microphone attached. It has a full cognitive architecture:

- **Talks back in real time** via Gemini Live bidirectional audio
- **Remembers who you are** across every session using layered memory
- **Retrieves the right memories** using semantic vector search, not just recency
- **Builds a knowledge graph** of every person, place, and project you mention
- **Detects your follow-up intentions** and checks in on them later
- **Monitors your mood** over time and adapts its tone
- **Greets you proactively** every morning with weather, unfinished tasks, and mood context
- **Watches your PC health** and warns you about CPU, RAM, disk, battery, and temperature
- **Executes multi-step tasks** with a Gemini-powered planner, circuit-breaker error recovery, and auto-replan
- **Serves a live web dashboard** with news, knowledge graph, semantic search, and system stats

---

## Feature Overview

### Real-Time Voice Conversation
- **Gemini Live API** — bidirectional audio stream, sub-second response latency
- **Wake-word detection** — say "Jarvis" to activate; auto-sleeps after 30s of silence
- **Emotion detection** — reads emotional tone from your voice and text
- **Mute toggle** — F4 key or on-screen button; mic stays off until unmuted

### Layered Memory System

| Layer | What it stores | Persistence |
|-------|---------------|-------------|
| Long-term memory | Identity, preferences, projects, relationships, wishes, notes | `memory/long_term.json` (atomic writes) |
| Episodic memory | Session summaries (2-3 sentences each, last 30 sessions) | `memory/conversation_history.json` |
| Semantic store | 768-dim Gemini embeddings of every episode and saved memory | `memory/embeddings/` |
| Knowledge graph | Entities (people, places, tools) + relationships | `memory/knowledge_graph.json` |
| Mood tracker | Mood log per session, dominant mood streak detection | `memory/mood_log.json` |
| Follow-up tracker | Intentions detected in speech, with snooze and auto-dismiss | `memory/followups.json` |
| File index | Semantic index of Desktop, Documents, Downloads | `memory/embeddings/` |

All memory files use **atomic writes** (temp file + `os.replace()`) — zero data loss on crash.

### Semantic Memory Search (RAG Brain)
- Uses `text-embedding-004` (768-dim) to embed every episode and saved memory
- On each turn, retrieves the **most relevant** past context instead of the last 7 episodes
- 90-day TTL filter — stale memories don't pollute results
- Batch embedding API (up to 20 texts per call) for efficient backfill
- Thread-safe: embedding API call happens **outside** the file lock

### Knowledge Graph
- Auto-extracts entities and relationships from every conversation turn
- Local regex extraction (zero API calls) for people, places, tech tools, projects
- Gemini-assisted extraction for complex episode summaries
- Levenshtein fuzzy matching — finds "python" even if you type "pythn"
- Injects entity context into the system prompt when you mention a known person or project
- Max 500 nodes, 2000 edges — oldest pruned when over limit

### Follow-Up Reminders
- Detects future intentions in speech ("I need to book flights", "I should call mom")
- Keyword pre-filter avoids API calls on most turns
- Snooze support — hide a reminder for N days
- Auto-dismiss after 3 asks or 10 days
- Surfaces in the proactive morning briefing

### Proactive Morning Briefing
- Speaks first on startup without being asked
- Greets by time of day, mentions weather for your city
- References what happened in the last session
- Checks in on one pending follow-up naturally
- Adapts tone to your mood pattern (gentler when stressed for 3+ days)

### PC Guardian
- Background thread, zero API calls, 100% local
- Monitors: CPU %, RAM %, disk free %, battery %, CPU temperature
- Identifies the top offending process when CPU or RAM spikes
- Per-alert cooldowns prevent spam (CPU: 5 min, disk: 30 min)
- CPU alert only fires after 2 consecutive high-CPU checks (avoids false positives)

### Agentic Task Execution
- **Planner** — Gemini decomposes any goal into up to 5 tool steps
- **Heuristic fast-path** — simple commands (open app, weather, YouTube) skip the API call
- **Executor** — runs steps sequentially, injects prior step results as context
- **Error recovery** — circuit breaker with exponential backoff (60s → 30 min)
- **Auto-replan** — up to 2 replan attempts on failure before abort
- **Generated code sandbox** — blocks `rm -rf`, System32 access, credential reads

### Tools (20+)

| Category | Tools |
|----------|-------|
| Web | `web_search`, `browser_control`, `flight_finder` |
| Media | `youtube_video`, `weather_report` |
| Desktop | `open_app`, `desktop_control`, `computer_control`, `computer_settings` |
| Files | `file_controller`, `screen_process` |
| Communication | `send_message` (WhatsApp, Telegram, and more) |
| Development | `code_helper`, `dev_agent`, `generated_code` |
| Reminders | `reminder`, `game_updater` |
| Memory | `save_memory`, `forget_memory`, `search_memory` |

### Web Dashboard
Available at `http://127.0.0.1:5555` while Jarvis is running. Localhost-only (access denied from other machines).

- **Live log feed** — every action, tool call, and response
- **Agent status** — awake/sleeping, listening, last command, uptime
- **System stats** — CPU, RAM, disk (via psutil)
- **News dashboard** — Google News RSS for South India, North India, International, Tech, Conflicts with YouTube news videos
- **Semantic search panel** — search all memories and episodes by meaning
- **Knowledge Graph panel** — browse entities and relationships, click a node to see its edges

### Security
- **Windows Credential Manager** — API key stored securely via `keyring`; `api_keys.json` is only used as a first-run fallback and auto-migrated
- **Localhost-only dashboard** — `403 Forbidden` for any request not from `127.0.0.1`
- **Generated code scanner** — blocks 6 dangerous patterns before any AI-generated code runs
- **Safe subprocess environment** — API keys stripped from env before subprocess execution
- **Prompt injection sanitizer** — user text is cleaned before being embedded in system prompts

---

## Architecture

```
Jarvis-V1/
├── main.py                        # Entry point, JarvisLive class, audio pipeline
├── ui.py                          # Tkinter UI — halo animation, log, mute button
├── wake_word.py                   # Wake-word detector (active/sleep toggling)
│
├── core/
│   ├── prompt.txt                 # System prompt for Gemini Live
│   ├── tool_declarations.py       # All 20+ tool schemas (Gemini function calling)
│   └── turn_manager.py            # Background turn workers (episode, KG, followup)
│
├── agent/
│   ├── planner.py                 # Gemini task planner + heuristic fast-path
│   ├── executor.py                # Step executor + code sandbox
│   ├── error_handler.py           # Gemini error analysis (retry/skip/replan/abort)
│   ├── error_recovery.py          # Circuit breaker + exponential backoff
│   ├── followup_detector.py       # Intention detection from user speech
│   ├── proactive.py               # Morning briefing builder
│   └── pc_guardian.py             # CPU/RAM/disk/battery/temp monitor
│
├── memory/
│   ├── memory_manager.py          # Long-term key-value memory (atomic writes)
│   ├── conversation_history.py    # Episodic memory (session summaries)
│   ├── semantic_store.py          # Vector embeddings + cosine search (RAG)
│   ├── knowledge_graph.py         # Entity/relationship graph + fuzzy lookup
│   ├── followups.py               # Follow-up intention storage + snooze
│   ├── mood_tracker.py            # Mood logging + pattern detection
│   └── file_store.py              # Semantic file index (Desktop/Docs/Downloads)
│
├── actions/                       # 20+ tool implementations
│   ├── browser_control.py
│   ├── code_helper.py
│   ├── computer_control.py
│   ├── computer_settings.py
│   ├── desktop.py
│   ├── dev_agent.py
│   ├── emotion_detector.py
│   ├── file_controller.py
│   ├── flight_finder.py
│   ├── game_updater.py
│   ├── open_app.py
│   ├── reminder.py
│   ├── screen_processor.py
│   ├── send_message.py
│   ├── weather_report.py
│   ├── web_search.py
│   └── youtube_video.py
│
├── gui/
│   ├── app.py                     # Flask dashboard server
│   ├── templates/
│   │   ├── dashboard.html         # Main dashboard
│   │   └── news.html              # News dashboard
│   └── static/
│       ├── app.js                 # Dashboard JS (semantic search, KG panel)
│       ├── style.css
│       ├── news.js
│       └── news.css
│
├── config/
│   ├── __init__.py                # Named constants (MAX_MEMORY_CHARS, EMBED_DIM, etc.)
│   └── api_keys.json              # API key fallback (use keyring in production)
│
├── tests/
│   ├── test_memory.py             # 35 unit tests — memory modules
│   ├── test_integration.py        # 11 integration tests — end-to-end data flow
│   ├── test_actions.py            # 11 action import + smoke tests
│   ├── test_executor.py           # 2 executor tests
│   ├── test_executor_recovery_corrected.py  # 23 recovery tests
│   ├── test_planner.py            # 3 planner tests
│   ├── test_planner_edge_cases.py # 31 edge case tests
│   └── test_planner_multi_step.py # 18 multi-step tests
│
└── logs/
    └── jarvis.log                 # Full audit log (rotating, absolute path)
```

---

## Quick Start

### Requirements
- **Windows 10/11**
- **Python 3.11+**
- **Microphone**
- **Google Gemini API key** (free tier works)

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

4. **Set your Gemini API key (secure — recommended):**
   ```bash
   python -c "import keyring; keyring.set_password('JarvisAI', 'gemini_api_key', 'YOUR_KEY_HERE')"
   ```
   Or put it in `config/api_keys.json` as a fallback:
   ```json
   { "gemini_api_key": "YOUR_KEY_HERE" }
   ```

5. **Run Jarvis:**
   ```bash
   python main.py
   ```

6. **Open the dashboard** (while Jarvis is running):
   ```
   http://127.0.0.1:5555
   ```

---

## Usage Examples

Say "Jarvis" to activate, then speak your command:

```
"Jarvis, what's the weather in Bangalore?"
→ Fetches and reads current weather aloud

"Jarvis, search for latest AI news and save it to a file"
→ Plans: web_search → file_controller; saves results to Desktop

"Jarvis, send a message to Arjun on WhatsApp saying I'll be late"
→ Opens WhatsApp Desktop, finds Arjun, sends the message

"Jarvis, remember that my favourite language is Python"
→ Saves to long-term memory + semantic index

"Jarvis, play lofi hip hop on YouTube"
→ Finds and plays the video

"Jarvis, what do you know about Python?"
→ Searches knowledge graph + semantic memory; responds with context

"Jarvis, take a screenshot and tell me what's on screen"
→ Captures and analyzes the screen with Gemini Vision

"Jarvis, write a Python script to rename all files in Downloads"
→ Generates, safety-checks, and runs the code
```

---

## Running Tests

```bash
# Run all 140 tests
python -m pytest tests/ -v

# Run only memory tests
python -m pytest tests/test_memory.py -v

# Run only integration tests
python -m pytest tests/test_integration.py -v
```

---

## Troubleshooting

**Microphone not detected**
- Check Windows Sound Settings → Input devices
- Ensure Python has microphone permission (Settings → Privacy → Microphone)

**"No API key found" error**
- Set the key via keyring (see Quick Start step 4)
- Or verify `config/api_keys.json` exists and contains `"gemini_api_key"`

**Dashboard not loading**
- Jarvis must be running first (Flask starts with Jarvis)
- Only accessible from `http://127.0.0.1:5555` (localhost only by design)

**Knowledge graph / semantic search empty**
- Have a few conversations first — the graph and index build from real sessions
- Run `python bulk_import.py` to seed initial personal data

**Logs**
- All logs are written to `logs/jarvis.log` (absolute path, created automatically)

---

## Roadmap (Post V1)

- [ ] Shared `core/api_key.py` — single secure key loader for all modules
- [ ] Multi-language voice support
- [ ] Email and calendar integration
- [ ] Mobile companion app
- [ ] Community plugin system
- [ ] Cloud memory sync (optional, opt-in)

---

## Author

**Prasanth Mukkiri** — sole creator, owner, and developer of Jarvis V1.

---

## License

**Proprietary** — All rights reserved by Prasanth Mukkiri. Unauthorized copying, distribution, or use is prohibited.

---

*Built from scratch. No frameworks. No shortcuts.*
