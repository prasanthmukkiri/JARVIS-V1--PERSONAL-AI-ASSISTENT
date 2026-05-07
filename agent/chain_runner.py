"""
Chain Runner — executes an explicit sequence of tool steps in order.
Each step uses _call_tool() from agent.executor so no action dispatch
logic is duplicated. Chain state is mutated in-place so callers (e.g.
the Flask app) that hold a reference automatically see live updates.
"""
from __future__ import annotations

import json
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional


# ── API key helper (mirrors the one in executor.py) ───────────────────────────

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_api_key() -> str:
    cfg = _get_base_dir() / "config" / "api_keys.json"
    with open(cfg, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class ChainStep:
    id: str
    tool: str
    parameters: dict
    description: str
    status: str = "pending"        # pending | running | done | failed
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[float] = None
    ended_at: Optional[float] = None


@dataclass
class ChainRun:
    id: str
    goal: str
    steps: list                    # list[ChainStep]
    status: str = "pending"        # pending | running | done | failed | cancelled
    created_at: float = field(default_factory=time.time)


# ── Gemini prompt for parsing natural-language chains ─────────────────────────

_CHAIN_PARSER_SYSTEM = """
You are the chain parser for JARVIS. Parse a multi-step user command into an
ordered list of tool steps. Return ONLY valid JSON — no markdown, no explanation.

Format:
{
  "steps": [
    {
      "tool": "tool_name",
      "parameters": {},
      "description": "what this step does in plain English"
    }
  ]
}

AVAILABLE TOOLS (use exact names):
  open_app          — open any desktop application  (params: app_name)
  web_search        — search the web               (params: query)
  browser_control   — control a browser            (params: action, url, query, text, description, browser)
  file_controller   — manage files/folders         (params: action, path, name, content, destination)
  computer_settings — system controls              (params: action, value)
  computer_control  — keyboard/mouse/clicks        (params: action, text, x, y, keys, key)
  screen_process    — analyse the screen/camera    (params: text, angle)
  send_message      — send a message               (params: receiver, message_text, platform)
  reminder          — set a reminder               (params: date, time, message)
  desktop_control   — control the desktop          (params: action, path, url, mode)
  youtube_video     — play or search YouTube       (params: action, query, url)
  weather_report    — get weather                  (params: city)
  code_helper       — write / run code             (params: action, description, language)
  dev_agent         — build a project from scratch (params: description, language, project_name)

RULES:
- Split the command on: "then", "and then", "after that", "next", "finally", "also"
- Max 8 steps per chain
- Preserve receiver names verbatim in send_message steps
- Return [] steps ONLY if the input is truly a single-step command
"""


# Known valid tool names — used to validate parser output
_VALID_TOOLS = {
    "open_app", "web_search", "browser_control", "file_controller",
    "computer_settings", "computer_control", "screen_process", "send_message",
    "reminder", "desktop_control", "youtube_video", "weather_report",
    "code_helper", "dev_agent", "search_memory", "search_files",
    "save_memory", "forget_memory", "log_mood_voice",
}

# Simple parse cache: identical commands always produce the same steps
_parse_cache: dict[str, list[dict]] = {}


def parse_chain_goal(text: str) -> list[dict]:
    """
    Parse a natural-language multi-step command into a list of step dicts.
    - temperature=0 for fully deterministic output
    - Schema-validates every step (tool must be in known set)
    - Caches results so identical commands are instant
    - Falls back to a single web_search step on any failure
    """
    cache_key = text.strip().lower()
    if cache_key in _parse_cache:
        return _parse_cache[cache_key]

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_get_api_key())
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite-preview-06-17",
            contents=f"Command: {text}",
            config=types.GenerateContentConfig(
                system_instruction=_CHAIN_PARSER_SYSTEM,
                temperature=0,          # fully deterministic
                max_output_tokens=1024,
            ),
        )
        raw = response.text.strip()
        raw = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
        parsed = json.loads(raw)
        steps  = parsed.get("steps") or []

        result = []
        for s in steps[:8]:   # hard-cap at 8 steps
            if not isinstance(s, dict):
                continue
            tool = str(s.get("tool", "")).strip().lower()
            if tool not in _VALID_TOOLS:
                print(f"[ChainRunner] Unknown tool '{tool}' — skipping step")
                continue
            params = s.get("parameters") or {}
            if not isinstance(params, dict):
                params = {}
            result.append({
                "tool":        tool,
                "parameters":  params,
                "description": str(s.get("description", "Execute step"))[:200].strip(),
            })

        result = result if result else _fallback_steps(text)
        # Cache up to 100 entries
        if len(_parse_cache) < 100:
            _parse_cache[cache_key] = result
        return result

    except Exception as e:
        print(f"[ChainRunner] parse_chain_goal failed: {e}")
        return _fallback_steps(text)


def _fallback_steps(text: str) -> list[dict]:
    return [{
        "tool": "web_search",
        "parameters": {"query": text},
        "description": f"Search: {text[:80]}",
    }]


# ── Execution ─────────────────────────────────────────────────────────────────

def run_chain(
    chain_run: ChainRun,
    on_update: Callable | None = None,
    speak: Callable | None = None,
) -> None:
    """
    Execute chain_run's steps sequentially using _call_tool from agent.executor.
    Mutates chain_run and each ChainStep in-place.
    Designed to run in a background thread; never raises.
    Continues past failed steps (best-effort) so partial results are visible.
    """
    from agent.executor import _call_tool

    chain_run.status = "running"
    _notify(on_update, chain_run)

    for step in chain_run.steps:
        step.status = "running"
        step.started_at = time.time()
        _notify(on_update, chain_run)

        try:
            result = _call_tool(step.tool, step.parameters, speak)
            step.result = str(result)[:600]
            step.status = "done"
        except Exception as exc:
            step.error = str(exc)[:400]
            step.status = "failed"
        finally:
            step.ended_at = time.time()
            _notify(on_update, chain_run)

    # Final chain status
    if any(s.status == "failed" for s in chain_run.steps):
        chain_run.status = "failed"
    else:
        chain_run.status = "done"
    _notify(on_update, chain_run)


def _notify(callback: Callable | None, chain_run: ChainRun) -> None:
    if callback:
        try:
            callback(chain_run)
        except Exception:
            pass


# ── Factory helper ────────────────────────────────────────────────────────────

def make_chain_run(goal: str, raw_steps: list[dict]) -> ChainRun:
    """Build a ChainRun from a goal string and a list of parsed step dicts."""
    steps = [
        ChainStep(
            id=str(uuid.uuid4())[:8],
            tool=s["tool"],
            parameters=s.get("parameters") or {},
            description=s.get("description", "Execute step"),
        )
        for s in raw_steps
    ]
    return ChainRun(id=str(uuid.uuid4())[:8], goal=goal, steps=steps)
