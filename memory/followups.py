"""
Follow-up storage — tracks things the user said they'd do
so Jarvis can check in on them later.
"""

import json
import logging
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
import sys

logger = logging.getLogger("jarvis.followups")


def _base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


FOLLOWUPS_PATH = _base_dir() / "memory" / "followups.json"
MAX_FOLLOWUPS  = 20
MAX_ASKS       = 3       # auto-dismiss after asking this many times
MAX_AGE_DAYS   = 10      # auto-dismiss after this many days
_lock = threading.Lock()


def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def load_followups() -> list:
    if not FOLLOWUPS_PATH.exists():
        return []
    with _lock:
        try:
            data = json.loads(FOLLOWUPS_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []


def _write(followups: list) -> None:
    FOLLOWUPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(followups, indent=2, ensure_ascii=False)
    with _lock:
        tmp = FOLLOWUPS_PATH.with_suffix(".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, FOLLOWUPS_PATH)


def save_followup(intention: str, due_hint: str = "") -> None:
    if not intention or not intention.strip():
        return
    intention = intention.strip()

    followups = load_followups()

    # Deduplicate — skip if a very similar intention already exists
    for f in followups:
        if f.get("status") == "pending":
            existing = f.get("intention", "").lower()
            if intention.lower()[:40] in existing or existing[:40] in intention.lower():
                logger.debug("Duplicate skipped: %s", intention[:50])
                return

    followups.append({
        "id":           str(uuid.uuid4())[:8],
        "intention":    intention,
        "due_hint":     due_hint,
        "detected_on":  _today(),
        "status":       "pending",
        "asked_count":  0,
        "last_asked":   None,
        "snooze_until": None,
    })

    if len(followups) > MAX_FOLLOWUPS:
        followups = followups[-MAX_FOLLOWUPS:]

    _write(followups)
    logger.info("Saved: %s", intention[:60])


def get_pending(max_n: int = 3) -> list:
    """Return pending follow-ups, auto-cleaning expired/snoozed ones first."""
    followups = load_followups()
    today = _today()
    changed = False

    for f in followups:
        if f.get("status") != "pending":
            continue
        # Auto-dismiss if asked too many times or too old
        try:
            age = (datetime.strptime(today, "%Y-%m-%d") -
                   datetime.strptime(f.get("detected_on", today), "%Y-%m-%d")).days
        except ValueError:
            age = 0
        if f.get("asked_count", 0) >= MAX_ASKS or age > MAX_AGE_DAYS:
            f["status"] = "dismissed"
            changed = True

    if changed:
        _write(followups)

    # Exclude snoozed entries that haven't woken up yet
    pending = [
        f for f in followups
        if f.get("status") == "pending"
        and (not f.get("snooze_until") or f["snooze_until"] <= today)
    ]
    return pending[:max_n]


def snooze(followup_id: str, days: int = 1) -> None:
    """Snooze a follow-up so it won't surface until `days` days from now."""
    from datetime import timedelta
    followups = load_followups()
    today_dt  = datetime.strptime(_today(), "%Y-%m-%d")
    wake_date = (today_dt + timedelta(days=days)).strftime("%Y-%m-%d")
    for f in followups:
        if f.get("id") == followup_id:
            f["snooze_until"] = wake_date
            break
    _write(followups)
    logger.info("Snoozed %s until %s", followup_id, wake_date)


def mark_asked(followup_id: str) -> None:
    followups = load_followups()
    for f in followups:
        if f.get("id") == followup_id:
            f["asked_count"] = f.get("asked_count", 0) + 1
            f["last_asked"]  = _today()
            break
    _write(followups)


def mark_done(followup_id: str) -> None:
    followups = load_followups()
    for f in followups:
        if f.get("id") == followup_id:
            f["status"] = "done"
            break
    _write(followups)


def dismiss(followup_id: str) -> None:
    followups = load_followups()
    for f in followups:
        if f.get("id") == followup_id:
            f["status"] = "dismissed"
            break
    _write(followups)
