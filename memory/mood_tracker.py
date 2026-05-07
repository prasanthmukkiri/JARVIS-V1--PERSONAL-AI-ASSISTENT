"""
Mood tracker — logs daily emotional state and detects patterns across days
so Jarvis can adapt his tone and behaviour accordingly.

Two sources feed it:
  1. Text mood  — keyword analysis of what the user says each turn
  2. Camera mood — parsed from the webcam emotion detector string
"""

import json
import re
import threading
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
import sys


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


MOOD_PATH = _base_dir() / "memory" / "mood_log.json"
MAX_DAYS  = 30
_lock     = threading.Lock()

# ── Keyword maps ───────────────────────────────────────────────────────────────
_MOOD_KEYWORDS: dict[str, list[str]] = {
    "stressed": [
        "stressed", "stress", "overwhelmed", "anxious", "anxiety", "worried",
        "nervous", "pressure", "deadline", "exhausted", "burnout", "panic",
        "hectic", "chaotic", "too much", "can't handle",
    ],
    "tired": [
        "tired", "sleepy", "exhausted", "drowsy", "fatigued", "no energy",
        "drained", "didn't sleep", "can't sleep", "insomnia", "yawning",
    ],
    "sad": [
        "sad", "upset", "depressed", "unhappy", "miserable", "disappointed",
        "heartbroken", "lonely", "miss", "grief", "cry", "crying", "tears",
    ],
    "frustrated": [
        "frustrated", "annoyed", "irritated", "angry", "furious", "pissed",
        "fed up", "sick of", "hate this", "nothing works", "keeps failing",
    ],
    "happy": [
        "happy", "great", "awesome", "amazing", "excited", "wonderful",
        "fantastic", "love it", "perfect", "brilliant", "good mood",
        "feeling good", "feeling great", "enjoying", "fun", "joy",
    ],
    "bored": [
        "bored", "boring", "nothing to do", "dull", "tedious", "monotonous",
    ],
}

_VALENCE: dict[str, int] = {
    "happy": 2, "bored": -1, "tired": -1,
    "sad": -2, "stressed": -2, "frustrated": -2,
}

_TONE_GUIDANCE: dict[str, str] = {
    "stressed": (
        "User has been under stress. Be calm, concise, and reassuring. "
        "Avoid being overly cheerful. If natural, briefly acknowledge the pressure."
    ),
    "tired": (
        "User has been tired lately. Keep responses short. "
        "Don't overwhelm with information. Offer to handle things proactively."
    ),
    "sad": (
        "User has seemed sad recently. Be warm and empathetic. "
        "Avoid cold or transactional tone. A brief check-in is welcome."
    ),
    "frustrated": (
        "User has been frustrated. Be extra efficient — no filler, no errors. "
        "Stay calm and solution-focused."
    ),
    "happy": (
        "User has been in a great mood. Match their energy — be upbeat, "
        "slightly playful, and enthusiastic."
    ),
    "bored": (
        "User seems bored. Be engaging and proactive — suggest something interesting."
    ),
}


# ── Text mood analysis ─────────────────────────────────────────────────────────

def analyze_text_mood(text: str) -> str | None:
    """Keyword scan of user speech — returns emotion label or None."""
    if not text:
        return None
    lower = text.lower()
    scores: Counter = Counter()
    for emotion, keywords in _MOOD_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                scores[emotion] += 1
    if not scores:
        return None
    return scores.most_common(1)[0][0]


def parse_camera_mood(emotion_str: str) -> str | None:
    """
    Parse strings like 'You appear stressed, sir.' → 'stressed'.
    Returns None if no known emotion found.
    """
    if not emotion_str:
        return None
    lower = emotion_str.lower()
    for emotion in _MOOD_KEYWORDS:
        if emotion in lower:
            return emotion
    # FER also returns: happy, sad, angry, fear, disgust, surprise, neutral
    fer_map = {
        "angry": "frustrated", "fear": "stressed", "disgust": "frustrated",
        "surprise": "happy", "neutral": None,
    }
    for fer_label, mapped in fer_map.items():
        if fer_label in lower:
            return mapped
    return None


# ── Storage ────────────────────────────────────────────────────────────────────

def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _load() -> list:
    if not MOOD_PATH.exists():
        return []
    with _lock:
        try:
            data = json.loads(MOOD_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []


def _save(log: list) -> None:
    MOOD_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        MOOD_PATH.write_text(
            json.dumps(log, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )


def log_mood(emotion: str) -> None:
    """Add an emotion reading to today's log entry."""
    if not emotion:
        return
    log = _load()
    today = _today()

    # Find or create today's entry
    entry = next((e for e in log if e.get("date") == today), None)
    if entry is None:
        entry = {"date": today, "emotions": [], "dominant": None}
        log.append(entry)

    entry["emotions"].append(emotion)

    # Recalculate dominant
    counts = Counter(entry["emotions"])
    entry["dominant"] = counts.most_common(1)[0][0]

    # Trim to MAX_DAYS
    if len(log) > MAX_DAYS:
        log = log[-MAX_DAYS:]

    _save(log)


# ── Pattern analysis ───────────────────────────────────────────────────────────

def get_pattern(days: int = 7) -> dict:
    """
    Analyse the last N days of mood data.
    Returns:
      dominant   — most frequent emotion across period
      trend      — 'improving' | 'declining' | 'stable' | 'insufficient_data'
      streak     — consecutive days with dominant emotion (if ≥2)
      today      — today's dominant (or None)
      guidance   — tone instruction string for the system prompt
    """
    log   = _load()
    today = _today()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    recent = [e for e in log if e.get("date", "") >= cutoff]

    result = {
        "dominant": None, "trend": "insufficient_data",
        "streak": 0, "today": None, "guidance": "",
    }

    if not recent:
        return result

    # Today's mood
    today_entry = next((e for e in recent if e.get("date") == today), None)
    result["today"] = today_entry.get("dominant") if today_entry else None

    # Overall dominant
    all_emotions = [e.get("dominant") for e in recent if e.get("dominant")]
    if not all_emotions:
        return result
    counts = Counter(all_emotions)
    result["dominant"] = counts.most_common(1)[0][0]

    # Streak — consecutive recent days with dominant emotion
    dominant = result["dominant"]
    streak = 0
    for entry in reversed(recent):
        if entry.get("dominant") == dominant:
            streak += 1
        else:
            break
    result["streak"] = streak

    # Trend — compare first half vs second half by valence
    if len(recent) >= 4:
        mid   = len(recent) // 2
        early = sum(_VALENCE.get(e.get("dominant", ""), 0) for e in recent[:mid])
        late  = sum(_VALENCE.get(e.get("dominant", ""), 0) for e in recent[mid:])
        if late > early + 1:
            result["trend"] = "improving"
        elif early > late + 1:
            result["trend"] = "declining"
        else:
            result["trend"] = "stable"

    # Guidance — only if streak ≥ 2 or today has a non-neutral emotion
    trigger = result["today"] or (dominant if streak >= 2 else None)
    if trigger and trigger in _TONE_GUIDANCE:
        result["guidance"] = _TONE_GUIDANCE[trigger]

    return result


def format_mood_for_prompt(pattern: dict) -> str:
    """Format mood pattern as a system prompt injection."""
    if not pattern or not pattern.get("guidance"):
        return ""

    dominant = pattern.get("dominant", "")
    streak   = pattern.get("streak", 0)
    trend    = pattern.get("trend", "")
    today    = pattern.get("today", "")
    guidance = pattern.get("guidance", "")

    lines = ["[USER MOOD CONTEXT — adapt your tone accordingly]"]

    if today:
        lines.append(f"Today's mood: {today}")
    if dominant and streak >= 2:
        lines.append(f"Recent pattern: {dominant} for {streak} consecutive days")
    if trend in ("improving", "declining"):
        lines.append(f"Trend: mood is {trend}")

    lines.append(f"Tone guidance: {guidance}")

    return "\n".join(lines) + "\n\n"
