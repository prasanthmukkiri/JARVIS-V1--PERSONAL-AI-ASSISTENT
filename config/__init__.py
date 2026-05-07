# config/__init__.py
import json, os
from pathlib import Path

_CONFIG_PATH = Path(__file__).parent / "api_keys.json"

def get_config() -> dict:
    with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_os() -> str:
    """Returns: 'windows' | 'mac' | 'linux'"""
    return get_config().get("os_system", "windows").lower()

def is_windows() -> bool: return get_os() == "windows"
def is_mac()     -> bool: return get_os() == "mac"
def is_linux()   -> bool: return get_os() == "linux"


# ── Named constants (P4-17) ─────────────────────────────────────────────────
# Memory limits
MAX_MEMORY_CHARS   = 2200
MAX_VALUE_LENGTH   = 380
MAX_LOG_LINES      = 800
MAX_EPISODES       = 30
MAX_FOLLOWUPS      = 20

# Embedding / semantic store
EMBED_DIM          = 768
TOOL_PARAM_MAX_LEN = 2000
SEMANTIC_TTL_DAYS  = 90

# Connection / retry
RECONNECT_MAX_WAIT = 60

# Proactive / briefing
BRIEFING_HOUR_START = 7
BRIEFING_HOUR_END   = 10

# File indexing
FILE_CHUNK_WORDS   = 400
FILE_CHUNK_OVERLAP = 50
FILE_MAX_MB        = 15