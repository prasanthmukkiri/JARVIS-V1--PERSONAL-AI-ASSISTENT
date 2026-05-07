"""
Episodic memory — stores per-session conversation summaries so Jarvis
remembers what was talked about across sessions.
"""

import json
import logging
import os
import re
import threading
from datetime import datetime
from pathlib import Path
import sys
from google import genai

logger = logging.getLogger("jarvis.history")


def _sanitize_for_prompt(text: str, max_len: int = 500) -> str:
    """Strip prompt-injection attempts before embedding user text in prompts."""
    text = text[:max_len]
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(
        r"(?i)(ignore\s+(all\s+)?(previous|prior|above)\s+instructions?[:\s])",
        "[...]", text,
    )
    return text.strip()

def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

HISTORY_PATH = _base_dir() / "memory" / "conversation_history.json"
MAX_EPISODES = 30
_lock = threading.Lock()


def load_episodes() -> list:
    if not HISTORY_PATH.exists():
        return []
    with _lock:
        try:
            data = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []


def save_episode(summary: str) -> str:
    """Save episode and return its source_id for semantic indexing."""
    if not summary or not summary.strip():
        return ""
    episodes = load_episodes()
    date_str = datetime.now().strftime("%Y-%m-%d")
    episode_id = f"ep_{date_str}_{len(episodes)}"
    episodes.append({
        "id": episode_id,
        "date": date_str,
        "time": datetime.now().strftime("%H:%M"),
        "summary": summary.strip(),
    })
    if len(episodes) > MAX_EPISODES:
        episodes = episodes[-MAX_EPISODES:]
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(episodes, indent=2, ensure_ascii=False)
    with _lock:
        tmp = HISTORY_PATH.with_suffix(".tmp")
        tmp.write_text(payload, encoding="utf-8")
        import os as _os
        _os.replace(tmp, HISTORY_PATH)
    logger.info("Episode saved (%s): %s", datetime.now().strftime('%H:%M'), summary[:70])
    return episode_id


def load_recent_episodes(n: int = 7) -> list:
    episodes = load_episodes()
    return episodes[-n:] if episodes else []


def format_episodes_for_prompt(episodes: list) -> str:
    if not episodes:
        return ""
    lines = ["[WHAT HAPPENED IN RECENT PAST SESSIONS — use naturally to feel continuity]"]
    for ep in reversed(episodes):
        date = ep.get("date", "")
        summary = ep.get("summary", "")
        if summary:
            lines.append(f"{date}: {summary}")
    if len(lines) <= 1:
        return ""
    result = "\n".join(lines) + "\n\n"
    if len(result) > 1500:
        result = result[:1497] + "...\n\n"
    return result


def summarize_conversation(turns: list, api_key: str) -> str:
    """
    turns: list of (user_text, jarvis_text) tuples
    Returns a 2-3 sentence episodic summary, or "" if nothing worth saving.
    """
    if not turns:
        return ""
    try:
        client = genai.Client(api_key=api_key)

        convo = ""
        for user, jarvis in turns[-20:]:
            if user:
                convo += f"User: {_sanitize_for_prompt(user)}\n"
            if jarvis:
                convo += f"Jarvis: {_sanitize_for_prompt(jarvis, max_len=300)}\n"

        prompt = (
            "Summarize this AI assistant conversation in 2-3 concise sentences. "
            "Focus on: what the user wanted, what was done, any personal details revealed "
            "(emotions, people mentioned, plans, projects, preferences). "
            "Write in past tense. Be specific — include names, places, topics. "
            "Skip greetings, small talk, and tool errors. "
            "If nothing meaningful happened, reply with exactly: SKIP\n\n"
            f"Conversation:\n{convo[:3500]}"
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash", contents=prompt
        )
        result = response.text.strip()
        if result.upper() == "SKIP" or len(result) < 15:
            return ""
        return result
    except Exception as e:
        logger.error("Summarize error: %s", e)
        return ""
