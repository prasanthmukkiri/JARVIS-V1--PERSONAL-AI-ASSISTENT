import asyncio
import re
import threading
import json
import sys
import traceback
import socket
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
# ── Logging setup ─────────────────────────────────────────────────────────────
_BASE = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
_LOG_DIR = _BASE / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    filename=str(_LOG_DIR / "jarvis.log"),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    encoding="utf-8",
)
logger = logging.getLogger("jarvis")

from agent.error_recovery import get_recovery_manager
from agent.metrics import get_metrics
from wake_word import create_wake_word_detector
import wake_word as wake_word_module

from actions.emotion_detector  import detect_emotion


import sounddevice as sd
from google import genai
from google.genai import types
from ui import JarvisUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
)
from memory.conversation_history import (
    load_recent_episodes, format_episodes_for_prompt,
    summarize_conversation, save_episode,
)
from memory.mood_tracker import (
    analyze_text_mood, parse_camera_mood, log_mood,
    get_pattern, format_mood_for_prompt,
)

from actions.flight_finder     import flight_finder
from actions.open_app          import open_app
from actions.weather_report    import weather_action
from actions.send_message      import send_message
from actions.reminder          import reminder
from actions.computer_settings import computer_settings
from actions.screen_processor  import screen_process
from actions.youtube_video     import youtube_video
from actions.desktop           import desktop_control
from actions.browser_control   import browser_control
from actions.file_controller   import file_controller
from actions.code_helper       import code_helper
from actions.dev_agent         import dev_agent
from actions.web_search        import web_search as web_search_action
from actions.computer_control  import computer_control
from actions.game_updater      import game_updater


NEWS_DASHBOARD_URL = "http://127.0.0.1:5555/news"
BRAIN_DASHBOARD_URL = "http://127.0.0.1:5555/brain"
MAP_DASHBOARD_URL = "http://127.0.0.1:5555/map"

from core.turn_manager import save_episode_bg as _save_episode_bg
from core.turn_manager import kg_turn_bg as _kg_turn_bg
from core.turn_manager import detect_followup_bg as _detect_followup_bg


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024


_DIRECT_MESSAGE_PATTERNS = [
    re.compile(
        r"^\s*(?:please\s+)?send\s+message\s+to\s+(?P<receiver>.+?)\s+on\s+(?P<platform>whatsapp|telegram|signal|discord|instagram|messenger)\s+saying\s+(?P<message>.+?)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:please\s+)?send\s+message\s+to\s+(?P<receiver>.+?)\s+saying\s+(?P<message>.+?)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:please\s+)?send\s+(?P<message>.+?)\s+to\s+(?P<receiver>.+?)\s+on\s+(?P<platform>whatsapp|telegram|signal|discord|instagram|messenger)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:please\s+)?send\s+(?P<message>.+?)\s+to\s+(?P<receiver>.+?)\s*$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:please\s+)?message\s+(?P<receiver>.+?)\s+saying\s+(?P<message>.+?)\s*$",
        re.IGNORECASE,
    ),
]


def _clean_direct_command_value(value: str) -> str:
    return value.strip().strip('"').strip("'").strip()


def _parse_direct_message_command(text: str) -> dict | None:
    normalized = re.sub(r"\s+", " ", (text or "")).strip()
    if not normalized:
        return None

    for pattern in _DIRECT_MESSAGE_PATTERNS:
        match = pattern.match(normalized)
        if not match:
            continue

        receiver = _clean_direct_command_value(match.group("receiver"))
        message = _clean_direct_command_value(match.group("message"))
        platform = _clean_direct_command_value(match.groupdict().get("platform") or "WhatsApp")

        if receiver and message:
            return {
                "receiver": receiver,
                "message_text": message,
                "platform": platform or "WhatsApp",
            }

    return None


def _is_news_request(text: str) -> bool:
    # Only treat a request as an "open news" command when the user speaks
    # one of the explicit phrases. This avoids accidental navigation when
    # the user mentions the word "news" in normal conversation.
    if not text:
        return False
    s = text.lower()
    # remove punctuation (e.g. what's -> whats) and normalize whitespace
    s = re.sub(r"[^\w\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()

    allowed = {
        "whats the current news",
        "what is the current news",
        "open news",
        "whats happening around the world",
        "what is happening around the world",
        "whats happening around the world",
    }

    return s in allowed


def _is_brain_request(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", (text or "")).strip().lower()
    if not normalized:
        return False
    return bool(re.search(r"\b(open\s+your\s+brain|open\s+brain|your\s+brain|brain)\b", normalized))


def _parse_map_request(text: str) -> tuple[bool, str]:
    """Parse map request and extract location if provided.
    Returns (is_map_request, location_or_empty).
    E.g. 'open map for paris' -> (True, 'paris')
    E.g. 'show me london on map' -> (True, 'london')
    E.g. 'open maps' -> (True, '')
    """
    normalized = re.sub(r"\s+", " ", (text or "")).strip().lower()
    if not normalized:
        return False, ""
    
    # Check if it's a map request
    if not re.search(r"\b(open|show)\s+(map|maps|the\s+map)\b", normalized):
        return False, ""
    
    # Try to extract location using various patterns
    patterns = [
        r"(?:open|show)\s+(?:map|maps|the\s+map)\s+(?:for|of|to)\s+(.+?)(?:\s+(?:on\s+)?map)?$",  # "open map for paris"
        r"(?:open|show)\s+(.+?)\s+(?:on|in)\s+(?:map|maps)$",  # "show paris on map"
        r"show\s+me\s+(.+?)\s+(?:on|in)\s+(?:the\s+)?map$",  # "show me london on map"
    ]
    
    for pattern in patterns:
        match = re.search(pattern, normalized)
        if match:
            location = match.group(1).strip()
            # Clean up common words
            location = re.sub(r"\b(the|in|on)\b", "", location).strip()
            return True, location
    
    # Just a plain "open map" with no location
    return True, ""


def _open_news_dashboard(player: JarvisUI, loop: asyncio.AbstractEventLoop):
    return loop.run_in_executor(
        None,
        lambda: browser_control(
            parameters={"action": "go_to", "url": NEWS_DASHBOARD_URL, "browser": "chrome"},
            player=player,
        ),
    )


def _open_brain_dashboard(player: JarvisUI, loop: asyncio.AbstractEventLoop):
    return loop.run_in_executor(
        None,
        lambda: browser_control(
            parameters={"action": "go_to", "url": BRAIN_DASHBOARD_URL, "browser": "chrome"},
            player=player,
        ),
    )


def _open_map_dashboard(player: JarvisUI, loop: asyncio.AbstractEventLoop):
    return loop.run_in_executor(
        None,
        lambda: browser_control(
            parameters={"action": "go_to", "url": MAP_DASHBOARD_URL, "browser": "chrome"},
            player=player,
        ),
    )


_api_key_cache: str | None = None


def _get_api_key() -> str:
    """
    Loads the Gemini API key securely — cached after first load.
    Priority: Windows Credential Manager → api_keys.json (legacy fallback)
    On first run with a JSON key, automatically migrates it to Credential Manager.
    """
    global _api_key_cache
    if _api_key_cache:
        return _api_key_cache

    # 1. Try Windows Credential Manager first (most secure)
    try:
        import keyring
        key = keyring.get_password("JarvisAI", "gemini_api_key")
        if key:
            _api_key_cache = key
            return _api_key_cache
    except Exception:
        pass  # keyring not available — fall through to JSON

    # 2. Fall back to JSON file
    try:
        with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
            key = json.load(f)["gemini_api_key"]
        if key:
            # Auto-migrate to Credential Manager for future runs
            try:
                import keyring
                keyring.set_password("JarvisAI", "gemini_api_key", key)
                logger.info("API key migrated to Windows Credential Manager")
            except Exception as e:
                logger.warning("Could not migrate to Credential Manager: %s", e)
            _api_key_cache = key
            return _api_key_cache
    except FileNotFoundError:
        raise RuntimeError(
            "No API key found!\n"
            "Either:\n"
            "  1. Run: python -c \"import keyring; keyring.set_password('JarvisAI', 'gemini_api_key', 'YOUR_KEY')\"\n"
            "  2. Or put your key in config/api_keys.json as: {\"gemini_api_key\": \"YOUR_KEY\"}"
        )
    except (KeyError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Invalid api_keys.json: {e}")


def _load_system_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        return (
            "You are JARVIS, Tony Stark's AI assistant. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )


# ── Transkripsiyon temizleyici ─────────────────────────────────────────────────
_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

def _clean_transcript(text: str) -> str:
    """Gemini'nin ürettiği <ctrlXX> artefaktlarını ve kontrol karakterlerini temizler."""
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()


from core.tool_declarations import TOOL_DECLARATIONS


def _is_online() -> bool:
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=2)
        return True
    except OSError:
        return False


class JarvisLive:

    def __init__(self, ui: JarvisUI, add_log=None, update_state=None):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self.ui.on_text_command = self._on_text_command
        self._turn_done_event: asyncio.Event | None = None
        self._add_log = add_log
        self._update_state = update_state
        self._metrics = get_metrics()
        self._recovery = get_recovery_manager()
        self._started_at = time.time()
        self._conversation_buffer: list[tuple[str, str]] = []
        self._turn_count = 0
        self._briefing_done = False
        self._last_user_text: str = ""
        self._user_text_lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="JarvisWorker")

        # mtime-based cache for _build_config() — {path_str: (mtime, formatted_str)}
        self._config_cache: dict[str, tuple[float, str]] = {}

        # Start background file indexing (Desktop, Documents, Downloads)
        def _index_files_bg():
            try:
                from memory.file_store import scan_default_folders
                def _progress(done, total):
                    self.ui.write_log(f"SYS: Indexing... ({done}/{total} files scanned)")
                scan_default_folders(_get_api_key(), progress_callback=_progress)
                self.ui.write_log("SYS: File indexing complete.")
            except Exception as e:
                logger.error("FileStore startup index error: %s", e)
        threading.Thread(target=_index_files_bg, daemon=True, name="FileIndex").start()

    def _on_text_command(self, text: str):
        if not self._loop:
            return

        if _is_news_request(text):
            async def _run_news_dashboard() -> None:
                result = await _open_news_dashboard(self.ui, self._loop)
                logger.info(f"NEWS_DASHBOARD: {result}")
                if self._add_log:
                    self._add_log(f"[NEWS] {result}", "INFO")

            asyncio.run_coroutine_threadsafe(_run_news_dashboard(), self._loop)
            return

        if _is_brain_request(text):
            async def _run_brain_dashboard() -> None:
                result = await _open_brain_dashboard(self.ui, self._loop)
                logger.info(f"BRAIN_DASHBOARD: {result}")
                if self._add_log:
                    self._add_log(f"[BRAIN] {result}", "INFO")

            asyncio.run_coroutine_threadsafe(_run_brain_dashboard(), self._loop)
            return

        is_map_req, location = _parse_map_request(text)
        if is_map_req:
            async def _run_map_dashboard() -> None:
                try:
                    from actions.maps import maps_action
                    if location:
                        # If a location was specified, use show_location to geocode and open
                        result = await self._loop.run_in_executor(
                            None,
                            lambda: maps_action(
                                parameters={"action": "show_location", "location": location},
                                player=self.ui
                            )
                        )
                    else:
                        # No location, just open the base map
                        result = await _open_map_dashboard(self.ui, self._loop)
                    logger.info(f"MAP_DASHBOARD: {result}")
                    if self._add_log:
                        self._add_log(f"[MAP] {result}", "INFO")
                except Exception as e:
                    logger.error(f"MAP_DASHBOARD error: {e}")
                    if self._add_log:
                        self._add_log(f"[MAP] Error: {e}", "ERROR")

            asyncio.run_coroutine_threadsafe(_run_map_dashboard(), self._loop)
            return

        direct_message = _parse_direct_message_command(text)
        if direct_message:
            async def _run_direct_message() -> None:
                result = await self._loop.run_in_executor(
                    None,
                    lambda: send_message(
                        parameters=direct_message,
                        response=None,
                        player=self.ui,
                        session_memory=None,
                    ),
                )
                logger.info(f"DIRECT_SEND: {result}")
                if self._add_log:
                    self._add_log(f"[DIRECT] {result}", "INFO")

            asyncio.run_coroutine_threadsafe(_run_direct_message(), self._loop)
            return

        # Explicit multi-step chain: "do X then Y then Z" from the dashboard text box
        if re.search(r'\bthen\b', text, re.IGNORECASE):
            def _run_text_chain():
                try:
                    from agent.chain_runner import parse_chain_goal, run_chain, make_chain_run
                    raw_steps = parse_chain_goal(text)
                    chain_run = make_chain_run(text, raw_steps)
                    if self._add_log:
                        self._add_log(f"[CHAIN] {chain_run.id} — {len(chain_run.steps)} steps", "INFO")
                    run_chain(chain_run, speak=self.speak)
                    if self._add_log:
                        self._add_log(f"[CHAIN] {chain_run.id} {chain_run.status.upper()}", "INFO")
                except Exception as exc:
                    logger.error(f"[Chain] text chain failed: {exc}")
            self._pool.submit(_run_text_chain)
            return

        if not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        try:
            wake_word_module.set_jarvis_speaking(value)
        except Exception:
            pass
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _cached_read(self, path: Path, loader) -> str:
        """Return cached formatted string for `path`, re-reading only if mtime changed."""
        key = str(path)
        try:
            mtime = path.stat().st_mtime if path.exists() else 0.0
        except Exception:
            mtime = 0.0
        cached = self._config_cache.get(key)
        if cached and cached[0] == mtime:
            return cached[1]
        result = loader()
        self._config_cache[key] = (mtime, result)
        return result

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime

        mem_path    = BASE_DIR / "memory" / "long_term.json"
        mood_path   = BASE_DIR / "memory" / "mood_log.json"

        mem_str    = self._cached_read(mem_path,   lambda: format_memory_for_prompt(load_memory()))
        sys_prompt = self._cached_read(PROMPT_PATH, _load_system_prompt)

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        hour     = now.hour
        if 22 <= hour or hour < 6:
            time_mode = "It is late night. Keep all responses very short and quiet. Speak softly."
        elif 6 <= hour < 9:
            time_mode = "It is morning. Be brief, energetic, and upbeat."
        elif 9 <= hour < 18:
            time_mode = "Normal daytime — full responses as needed."
        else:
            time_mode = "It is evening. Slightly more relaxed tone."
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Time guidance: {time_mode}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        emotion_ctx = ""
        try:
            from core.emotion_detector import get_emotion_detector

            detector = get_emotion_detector()
            if detector.enabled:
                emotion_note = detector.get_emotion_for_response()
                if emotion_note and emotion_note != "neutral":
                    emotion_ctx = (
                        f"[USER EMOTION CONTEXT]\n"
                        f"{emotion_note}\n"
                        f"Adapt tone, empathy, and pacing to this emotion.\n\n"
                    )
        except Exception as e:
            logger.debug(f"Emotion context unavailable: {e}")

        mood_str = self._cached_read(
            mood_path,
            lambda: format_mood_for_prompt(get_pattern(days=7))
        )

        # Snapshot last user text once under lock — used for all context lookups below
        with self._user_text_lock:
            _last_user = self._last_user_text

        # Semantic episode retrieval — fall back to recent if store is empty
        episodes_str = ""
        try:
            from memory.semantic_store import search, format_results_for_prompt
            if _last_user:
                hits = search(_last_user, _get_api_key(), top_k=5)
                if hits:
                    episodes_str = format_results_for_prompt(hits)
        except Exception:
            pass
        if not episodes_str:
            episodes = load_recent_episodes(7)
            episodes_str = format_episodes_for_prompt(episodes)

        # Knowledge graph injection — if last user message mentions a known entity
        kg_str = ""
        try:
            from memory.knowledge_graph import get_known_entities, format_kg_for_prompt
            if _last_user:
                known = get_known_entities()
                lc = _last_user.lower()
                for entity in known:
                    if entity in lc:
                        kg_str = format_kg_for_prompt(entity)
                        break
        except Exception:
            pass

        # File RAG — inject relevant file excerpts if user query matches
        file_ctx = ""
        try:
            from memory.file_store import search_files as _sf, format_for_prompt as _ffp
            if _last_user and len(_last_user) > 10:
                file_hits = _sf(_last_user, _get_api_key(), top_k=3)
                file_ctx  = _ffp(file_hits, min_score=0.65)
        except Exception:
            pass

        parts = [time_ctx]
        if emotion_ctx:
            parts.append(emotion_ctx)
        if mood_str:
            parts.append(mood_str)
        if kg_str:
            parts.append(kg_str)
        if episodes_str:
            parts.append(episodes_str)
        if file_ctx:
            parts.append(file_ctx)
        if mem_str:
            parts.append(mem_str)
        parts.append(sys_prompt)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Charon"
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        raw_args = fc.args or {}
        args = {}
        for k, v in raw_args.items():
            if isinstance(v, str) and len(v) > 2000:
                logger.warning("TOOL %s: arg '%s' truncated from %d chars", name, k, len(v))
                args[k] = v[:2000]
            else:
                args[k] = v
        started_at = time.perf_counter()
        success = True

        logger.info("TOOL: %s | ARGS: %s", name, args)
        if self._add_log:
            self._add_log(f"[TOOL] Executing {name}...", "INFO")
        self.ui.set_state("THINKING")

        # ── save_memory: silent and fast ──────────────────────────────────────
        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                logger.debug("save_memory: %s/%s", category, key)
                # Embed memory entry for semantic search in background
                def _embed_mem(cat=category, k=key, v=value):
                    try:
                        from memory.semantic_store import add_entry
                        from datetime import datetime as _dt
                        add_entry(
                            text=f"{cat} — {k}: {v}",
                            source="memory",
                            source_id=f"mem_{cat}_{k}",
                            date=_dt.now().strftime("%Y-%m-%d"),
                            api_key=_get_api_key(),
                            category=cat,
                        )
                    except Exception as e:
                        logger.error("SemanticStore mem embed error: %s", e)
                self._pool.submit(_embed_mem)
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            self._metrics.record_tool_execution(name, (time.perf_counter() - started_at) * 1000.0, success=True)
            self._recovery.record_success(name)
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        # ── forget_memory: silent and fast ───────────────────────────────────────
        if name == "forget_memory":
            from memory.memory_manager import forget_memory as _forget
            category = args.get("category", "notes")
            key      = args.get("key", "")
            if key:
                result_msg = _forget(key, category)
                logger.info("FORGET: %s/%s — %s", category, key, result_msg)
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            self._metrics.record_tool_execution(name, (time.perf_counter() - started_at) * 1000.0, success=True)
            self._recovery.record_success(name)
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        # ── search_memory: semantic recall on demand ──────────────────────────
        if name == "search_memory":
            query = args.get("query", "").strip()
            top_k = min(int(args.get("top_k", 5)), 10)
            result_text = "No relevant memories found."
            if query:
                try:
                    from memory.semantic_store import search
                    hits = search(query, _get_api_key(), top_k=top_k)
                    if hits:
                        lines = [f"Found {len(hits)} relevant memory entries:"]
                        for h in hits:
                            lines.append(f"- [{h.get('date','')} {h.get('source','')}] {h.get('text','')}")
                        result_text = "\n".join(lines)
                    # Also check knowledge graph
                    from memory.knowledge_graph import query_entity
                    kg = query_entity(query, fuzzy=True)
                    if kg:
                        name_key, node_data = next(iter(kg["node"].items()))
                        kg_lines = [f"KG: '{name_key}' ({node_data.get('type','?')}, {node_data.get('mentions',1)} mentions)"]
                        for edge in kg["edges"][:5]:
                            kg_lines.append(f"  {edge['from']} -[{edge['relation']}]-> {edge['to']}")
                        result_text += "\n" + "\n".join(kg_lines)
                except Exception as e:
                    result_text = f"Memory search error: {e}"
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            self._metrics.record_tool_execution(name, (time.perf_counter() - started_at) * 1000.0, success=True)
            self._recovery.record_success(name)
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": result_text}
            )

        # ── search_files: RAG over local PC files ────────────────────────────
        if name == "search_files":
            query  = args.get("query", "").strip()
            top_k  = min(int(args.get("top_k", 4)), 8)
            result_text = "No relevant files found. The file index may be empty — files are indexed from Desktop, Documents and Downloads."
            if query:
                try:
                    from memory.file_store import search_files as _sf
                    hits = _sf(query, _get_api_key(), top_k=top_k)
                    if hits:
                        lines = [f"Found {len(hits)} relevant file(s) for '{query}':"]
                        for h in hits:
                            score = int(h.get("score", 0) * 100)
                            name_ = h.get("file_name", "unknown")
                            text  = h.get("text", "").strip()[:400]
                            chunk = h.get("chunk_idx", 0)
                            total = h.get("total_chunks", 1)
                            lines.append(f"\n📄 {name_} (chunk {chunk+1}/{total}, {score}% match):\n{text}")
                        result_text = "\n".join(lines)
                except Exception as e:
                    result_text = f"File search error: {e}"
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            self._metrics.record_tool_execution(name, (time.perf_counter() - started_at) * 1000.0, success=True)
            self._recovery.record_success(name)
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": result_text}
            )

        # ── log_mood_voice: silent voice-tone mood logging ────────────────────
        if name == "log_mood_voice":
            mood       = args.get("mood", "").strip().lower()
            confidence = args.get("confidence", "medium")
            valid_moods = {"happy", "stressed", "tired", "sad", "frustrated", "bored"}
            if mood in valid_moods:
                self._pool.submit(log_mood, mood)
                logger.info("MOOD_VOICE: %s | confidence: %s", mood, confidence)
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            self._metrics.record_tool_execution(name, (time.perf_counter() - started_at) * 1000.0, success=True)
            self._recovery.record_success(name)
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop   = asyncio.get_event_loop()
        result = "Done."

        def _check_result(r, default="Done."):
            """Return result string, flag errors for speak_error if needed."""
            if r is None:
                return default
            s = str(r).strip()
            return s if s else default

        try:
            if not self._recovery.is_available(name):
                self.ui.write_log(f"SYS: {name} temporarily unavailable.")
                if self._add_log:
                    self._add_log(f"[RECOVERY] {name} unavailable", "WARNING")
                result = f"Tool '{name}' is temporarily unavailable."
                success = False
                self._metrics.record_tool_execution(name, (time.perf_counter() - started_at) * 1000.0, success=False)
                self._recovery.record_failure(name, result)
                return types.FunctionResponse(id=fc.id, name=name, response={"result": result})

            if name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.ui))
                result = r or f"Opened {args.get('app_name')}."

            elif name == "weather_report":
                r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.ui))
                result = r or "Weather delivered."

            elif name == "browser_control":
                r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "news_dashboard":
                r = await _open_news_dashboard(self.ui, loop)
                result = r or "Opened news dashboard."

            elif name == "maps":
                from actions.maps import maps_action
                r = await loop.run_in_executor(None, lambda: maps_action(parameters=args, player=self.ui))
                result = r or "Map opened."

            elif name == "file_controller":
                r = await loop.run_in_executor(None, lambda: file_controller(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "send_message":
                r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                result = r or f"Message sent to {args.get('receiver')}."

            elif name == "reminder":
                r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.ui))
                result = r or "Reminder set."

            elif name == "youtube_video":
                r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "screen_process":
                # Capture speak reference NOW — avoids stale session after reconnect
                _speak_now = self.speak
                _ui_now    = self.ui
                self._pool.submit(
                    screen_process,
                    parameters=args,
                    response=None,
                    player=_ui_now,
                    session_memory=None,
                    speak=_speak_now,
                )
                result = "Vision module activated. Stay completely silent — vision module will speak directly."

            elif name == "computer_settings":
                r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "desktop_control":
                r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "code_helper":
                r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "dev_agent":
                r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "agent_task":
                from agent.task_queue import get_queue, TaskPriority
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                result   = f"Task started (ID: {task_id})."

            elif name == "web_search":
                r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "computer_control":
                r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "game_updater":
                r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "flight_finder":
                r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "shutdown_jarvis":
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Goodbye, sir.")
                def _shutdown():
                    import time, os
                    time.sleep(1)
                    os._exit(0)
                threading.Thread(target=_shutdown, daemon=True).start()

            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            success = False
            traceback.print_exc()
            self.ui.write_log(f"ERR: {name} failed — {str(e)[:80]}")
            self.speak_error(name, e)

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        logger.info("RESULT: %s → %s", name, str(result)[:200])
        duration_ms = (time.perf_counter() - started_at) * 1000.0
        self._metrics.record_tool_execution(name, duration_ms, success=success)
        if success:
            self._recovery.record_success(name)
        else:
            self._recovery.record_failure(name, result)
        if self._add_log:
            self._add_log(f"[TOOL] {name} completed", "INFO")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        while True:
            msg = await self.out_queue.get()
            await self.session.send_realtime_input(media=msg)

    async def _listen_audio(self):
        logger.info("Mic started")
        loop = asyncio.get_event_loop()

        def callback(indata, frames, time_info, status):
            with self._speaking_lock:
                jarvis_speaking = self._is_speaking
            if not jarvis_speaking and not self.ui.muted:
                data = indata.tobytes()
                try:
                    loop.call_soon_threadsafe(
                        self.out_queue.put_nowait,
                        {"data": data, "mime_type": "audio/pcm"}
                    )
                except Exception:
                    logger.debug("Audio chunk dropped (queue full — backpressure)")

        try:
            with sd.InputStream(
                samplerate=SEND_SAMPLE_RATE,
                channels=CHANNELS,
                dtype="int16",
                blocksize=CHUNK_SIZE,
                callback=callback,
            ):
                logger.info("Mic stream open")
                while True:
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.error("Mic error: %s", e)
            raise

    async def _receive_audio(self):
        logger.info("Recv started")
        out_buf, in_buf = [], []

        try:
            while True:
                _recv_iter = self.session.receive().__aiter__()
                while True:
                    try:
                        response = await asyncio.wait_for(
                            _recv_iter.__anext__(), timeout=60.0
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Stream silent for 60s — reconnecting")
                        raise RuntimeError("Receive stream timeout")
                    except StopAsyncIteration:
                        break

                    if response.data:
                        if self._turn_done_event and self._turn_done_event.is_set():
                            self._turn_done_event.clear()
                        self.audio_in_queue.put_nowait(response.data)

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)

                        if sc.turn_complete:
                            if self._turn_done_event:
                                self._turn_done_event.set()

                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                with self._user_text_lock:
                                    self._last_user_text = full_in
                                self.ui.write_log(f"You: {full_in}")
                                if self._add_log:
                                    self._add_log(f"You: {full_in}", "USER")
                                try:
                                    emotion = detect_emotion(full_in)
                                    if emotion and emotion not in ("neutral", "unknown", ""):
                                        self.ui.write_log(f"[Emotion] {emotion}")
                                        logger.info(f"EMOTION: {emotion} | text: {full_in[:80]}")
                                        # Log camera mood to tracker
                                        cam_mood = parse_camera_mood(emotion)
                                        if cam_mood:
                                            self._pool.submit(log_mood, cam_mood)
                                except Exception:
                                    pass
                                # Log text-based mood in background
                                txt_mood = analyze_text_mood(full_in)
                                if txt_mood:
                                    self._pool.submit(log_mood, txt_mood)
                                # Detect follow-up intentions in background
                                self._pool.submit(_detect_followup_bg, full_in, _get_api_key())
                            in_buf = []

                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"Jarvis: {full_out}")
                                if self._add_log:
                                    self._add_log(f"Jarvis: {full_out}", "SYSTEM")
                            out_buf = []

                            # Feed every turn into the knowledge graph in real-time
                            if full_in or full_out:
                                self._pool.submit(_kg_turn_bg, full_in, full_out, _get_api_key())

                            # Accumulate turn for episodic memory
                            if full_in or full_out:
                                self._conversation_buffer.append((full_in, full_out))
                                self._turn_count += 1
                                # Hard cap — never keep more than 20 turns in RAM
                                if len(self._conversation_buffer) > 20:
                                    self._conversation_buffer = self._conversation_buffer[-20:]
                                # Auto-save episode every 5 turns in background
                                if self._turn_count % 5 == 0:
                                    buf_snapshot = list(self._conversation_buffer)
                                    # Clear buffer after snapshot so RAM is freed
                                    self._conversation_buffer.clear()
                                    self._pool.submit(_save_episode_bg, buf_snapshot, _get_api_key())

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            logger.debug("Tool call: %s", fc.name)
                            try:
                                fr = await asyncio.wait_for(
                                    self._execute_tool(fc), timeout=90.0
                                )
                            except asyncio.TimeoutError:
                                logger.warning("Tool timeout: %s", fc.name)
                                fr = types.FunctionResponse(
                                    id=fc.id,
                                    name=fc.name,
                                    response={"error": f"Tool '{fc.name}' timed out after 90s — try again"},
                                )
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )

        except Exception as e:
            logger.error("Recv error: %s", e, exc_info=True)
            raise

    async def _play_audio(self):
        logger.info("Play started")

        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue

                self.set_speaking(True)
                await asyncio.to_thread(stream.write, chunk)

        except Exception as e:
            logger.error("Play error: %s", e)
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def _deliver_briefing(self):
        """Wait for the session to stabilise, then speak a proactive greeting."""
        await asyncio.sleep(3)  # let audio pipeline settle
        try:
            from agent.proactive import build_briefing
            from memory.conversation_history import load_recent_episodes
            memory   = load_memory()
            episodes = load_recent_episodes(5)
            api_key  = _get_api_key()
            text = await asyncio.get_event_loop().run_in_executor(
                None, lambda: build_briefing(memory, episodes, api_key)
            )
            if text:
                logger.info("Proactive briefing: %s...", text[:80])
                self.speak(text)
        except Exception as e:
            logger.error("Proactive delivery error: %s", e)

    async def run(self):
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        _reconnect_attempt = 0
        while True:
            try:
                logger.info("Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue()
                    self.out_queue      = asyncio.Queue(maxsize=10)
                    self._turn_done_event = asyncio.Event()
                    _reconnect_attempt  = 0  # reset on successful connection

                    logger.info("Connected.")
                    self.ui.set_state("LISTENING")
                    if self._update_state:
                        self._update_state({"awake": True, "listening": True, "last_command": "", "uptime_seconds": int(time.time() - self._started_at)})
                    self.ui.write_log("SYS: JARVIS online.")
                    if self._add_log:
                        self._add_log("SYS: JARVIS online.", "SYSTEM")

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())

                    # Proactive briefing — only once per launch, not on reconnects
                    if not self._briefing_done:
                        self._briefing_done = True
                        tg.create_task(self._deliver_briefing())

            except Exception as e:
                logger.warning("Session error: %s", e, exc_info=True)

            self.set_speaking(False)
            self.ui.set_state("THINKING")

            # Save episode on disconnect if there are unsaved turns
            if self._conversation_buffer:
                buf_snapshot = list(self._conversation_buffer)
                self._conversation_buffer.clear()
                self._turn_count = 0
                self._pool.submit(_save_episode_bg, buf_snapshot, _get_api_key())

            _reconnect_attempt += 1
            if not _is_online():
                delay = 10
                logger.warning("No internet — waiting %ds", delay)
                self.ui.write_log("SYS: No internet. Waiting...")
            else:
                delay = min(3 * (2 ** (_reconnect_attempt - 1)), 60)
                logger.info("Reconnecting in %ds (attempt %d)", delay, _reconnect_attempt)
                if _reconnect_attempt == 5:
                    self.ui.write_log("ERR: 5 failed reconnects — check your API key")
                elif _reconnect_attempt == 10:
                    self.ui.write_log("ERR: 10 failed reconnects — Jarvis may need a restart")
            await asyncio.sleep(delay)


def main():
    ui = JarvisUI("face.png")

    # ── Start GUI Dashboard Server ─────────────────────────────
    try:
        from gui.app import start_server, add_log, update_agent_state
        gui_thread = start_server(host="127.0.0.1", port=5555, debug=False)
        ui.write_log("SYS: GUI Dashboard started at http://127.0.0.1:5555")
        logger.info("Dashboard at http://127.0.0.1:5555")
    except Exception as e:
        logger.error("Dashboard failed to start: %s", e)
        add_log = None
        update_agent_state = None
 
    def runner():
        ui.wait_for_api_key()
 
        # ── Wake word callbacks ────────────────────────────────
        def _on_wake(word: str):
            ui.write_log(f"SYS: Wake word detected — '{word}'")
            if update_agent_state:
                update_agent_state({"awake": True, "last_command": word, "last_command_time": time.time()})
            # If muted (sleeping), unmute automatically
            if ui.muted:
                ui._toggle_mute()
 
        def _on_sleep():
            ui.write_log("SYS: JARVIS entering sleep mode...")
            if update_agent_state:
                update_agent_state({"awake": False})
            # Mute mic when sleeping to save resources
            if not ui.muted:
                ui._toggle_mute()
 
        # ── Start wake word detector ───────────────────────────
        detector = create_wake_word_detector(
            on_wake          = _on_wake,
            on_sleep         = _on_sleep,
            player           = ui,
            active_timeout_s = 30.0,   # sleep after 30s of silence
        )
        detector.start()
        ui.write_log("SYS: Wake word detector active. Say 'JARVIS' to activate.")
 
        # ── Start JARVIS as normal ─────────────────────────────
        jarvis = JarvisLive(ui, add_log=add_log, update_state=update_agent_state)

        # ── Start PC Guardian ──────────────────────────────────
        try:
            from agent.pc_guardian import start_guardian
            start_guardian(speak=jarvis.speak)
        except Exception as e:
            logger.error("PC Guardian failed to start: %s", e)

        try:
            asyncio.run(jarvis.run())
        except KeyboardInterrupt:
            detector.stop()
            logger.info("Shutting down...")
 
    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()
 
 
if __name__ == "__main__":
    main()