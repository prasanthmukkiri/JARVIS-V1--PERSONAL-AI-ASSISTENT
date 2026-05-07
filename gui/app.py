"""
Jarvis GUI Dashboard Server
============================
Provides a web-based interface for monitoring and controlling Jarvis.

Features:
  - Real-time action logs and execution history
  - Agent status (awake/sleeping, listening)
  - Voice command recognition display
  - Settings panel (wake words, timeouts)
  - System stats (CPU, memory, uptime)
  - WebSocket support for live updates

Run: python -m gui.app
     Then open http://localhost:5555
"""

from __future__ import annotations

import json
import logging
import os
import html
import re
import concurrent.futures
import threading
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from queue import Queue
from urllib.parse import quote_plus

import functools

import requests
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

from actions.browser_control import browser_control

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


# ── constants ──────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
_GUI_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _BASE_DIR / "config" / "api_keys.json"
_LOG_FILE = _BASE_DIR / "logs" / "jarvis.log"

_LOCALHOST = {"127.0.0.1", "::1", "localhost"}


def _localhost_only(fn):
    """Reject API requests that don't come from the local machine."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        if request.remote_addr not in _LOCALHOST:
            return jsonify({"error": "Access denied — localhost only"}), 403
        return fn(*args, **kwargs)
    return wrapper

_NEWS_FEEDS = {
    "south_india": "https://news.google.com/rss/search?q=Telangana+Tamil+Nadu+Karnataka+Kerala+Andhra+Pradesh+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
    "north_india": "https://news.google.com/rss/search?q=Delhi+Uttar+Pradesh+Punjab+Rajasthan+Haryana+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
    "international": "https://news.google.com/rss/search?q=world+news+international+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
    "tech": "https://news.google.com/rss/search?q=technology+artificial+intelligence+AI+startup+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
    "conflicts": "https://news.google.com/rss/search?q=war+conflict+military+attack+missile+ceasefire+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
}

# Multiple video queries per region for variety
_NEWS_VIDEO_QUERIES = {
    "south_india": [
        "Tamil Nadu news latest",
        "Telangana latest news",
        "Kerala news today",
        "Bangalore news",
        "Hyderabad breaking news",
        "South India news live",
        "Chennai news today",
    ],
    "india": [
        "India news latest",
        "Delhi breaking news",
        "Mumbai news today",
        "India headlines",
        "Indian government news",
        "India economy news",
        "India politics news",
    ],
    "international": [
        "World news latest",
        "International breaking news",
        "Global headlines",
        "USA news today",
        "Europe news latest",
        "World business news",
        "International politics",
    ],
}

# Shared log queue (injected from main.py)
_log_queue: Queue = Queue(maxsize=1000)
_agent_state = {
    "awake": False,
    "listening": False,
    "last_command": "",
    "last_command_time": 0,
    "uptime_seconds": 0,
    "cpu_percent": 0,
    "memory_percent": 0,
}

# ── Chain store — persisted to disk, survives restarts ────────────────────────
_chain_store: dict = {}
_chain_store_lock = threading.Lock()
_CHAIN_DB = _GUI_DIR.parent / "memory" / "chains.json"


def _chain_to_dict(run) -> dict:
    """Serialize a ChainRun dataclass to a plain dict."""
    return {
        "id":         run.id,
        "goal":       run.goal,
        "status":     run.status,
        "created_at": run.created_at,
        "steps": [{
            "id":          s.id,
            "tool":        s.tool,
            "parameters":  s.parameters,
            "description": s.description,
            "status":      s.status,
            "result":      s.result,
            "error":       s.error,
            "started_at":  s.started_at,
            "ended_at":    s.ended_at,
        } for s in run.steps],
    }


def _save_chain_store() -> None:
    """Persist current chain store to disk (max 50 entries)."""
    try:
        with _chain_store_lock:
            data = [_chain_to_dict(r) for r in list(_chain_store.values())[-50:]]
        _CHAIN_DB.write_text(
            __import__("json").dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"[ChainDB] save error: {e}")


def _load_chain_store() -> None:
    """Load persisted chain runs back into memory on startup."""
    global _chain_store
    if not _CHAIN_DB.exists():
        return
    try:
        import json as _json
        from agent.chain_runner import ChainRun, ChainStep
        data = _json.loads(_CHAIN_DB.read_text(encoding="utf-8"))
        loaded = {}
        for r in data:
            steps = [ChainStep(**{k: v for k, v in s.items()}) for s in r.get("steps", [])]
            run = ChainRun(id=r["id"], goal=r["goal"], steps=steps,
                           status=r["status"], created_at=r["created_at"])
            loaded[run.id] = run
        with _chain_store_lock:
            _chain_store.update(loaded)
        print(f"[ChainDB] Loaded {len(loaded)} chain runs from disk")
    except Exception as e:
        print(f"[ChainDB] load error: {e}")


# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder=_GUI_DIR / "templates", static_folder=_GUI_DIR / "static")
CORS(app)


@app.before_request
def _enforce_localhost():
    """Block all /api/ requests that don't originate from this machine."""
    if request.path.startswith("/api/"):
        if request.remote_addr not in _LOCALHOST:
            return jsonify({"error": "Access denied — localhost only"}), 403


# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── API Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main dashboard HTML."""
    return render_template("dashboard.html")


@app.route("/news")
def news_dashboard():
    """Serve the dedicated news dashboard."""
    return render_template("news.html")


def _parse_news_feed(feed_url: str, limit: int = 8) -> list[dict]:
    """Fetch and parse a Google News RSS feed."""
    response = requests.get(feed_url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()

    root = ET.fromstring(response.text)
    articles: list[dict] = []

    for item in root.findall(".//item")[:limit]:
        title = html.unescape((item.findtext("title") or "").strip())
        description = html.unescape((item.findtext("description") or "").strip())
        link = (item.findtext("link") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        source_element = item.find("source")
        source = html.unescape((source_element.text or "").strip()) if source_element is not None else "Google News"

        articles.append({
            "title": title,
            "description": re.sub(r"<[^>]+>", "", description),
            "link": link,
            "source": source,
            "pubDate": pub_date,
        })

    return articles


def _safe_parse_news_feed(feed_name: str, feed_url: str) -> list[dict]:
    """Parse one news feed and fail closed to an empty list."""
    try:
        return _parse_news_feed(feed_url)
    except Exception as e:
        logger.warning(f"News feed failed for {feed_name}: {e}")
        return []


def _scrape_youtube_video(query: str) -> dict | None:
    """Find the first playable YouTube video for a news query."""
    try:
        search_url = f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp=EgIQAQ%3D%3D"
        response = requests.get(
            search_url,
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
        )
        response.raise_for_status()
        page = response.text

        video_id_match = re.search(r'"videoId":"([A-Za-z0-9_-]{11})"', page)
        title_match = re.search(r'"title":\{"runs":\[\{"text":"([^"]+)"', page)
        channel_match = re.search(r'"ownerText":\{"runs":\[\{"text":"([^"]+)"', page)

        if not video_id_match:
            return None

        video_id = video_id_match.group(1)
        title = html.unescape(title_match.group(1)) if title_match else query
        channel = html.unescape(channel_match.group(1)) if channel_match else "YouTube"

        return {
            "title": title,
            "channel": channel,
            "video_id": video_id,
            "watch_url": f"https://www.youtube.com/watch?v={video_id}",
            "embed_url": f"https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1",
            "query": query,
        }
    except Exception as e:
        logger.warning(f"YouTube news video scrape failed for {query}: {e}")
        return None


def _youtube_api_search(query: str) -> dict | None:
    """Use YouTube Data API v3 to find the first video for a query when an API key is configured."""
    try:
        if not _CONFIG_PATH.exists():
            return None
        cfg = json.load(open(_CONFIG_PATH, "r"))
        key = cfg.get("youtube_api_key")
        if not key:
            return None

        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 1,
            "videoEmbeddable": "true",
            "key": key,
        }
        resp = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            return None

        item = items[0]
        video_id = item.get("id", {}).get("videoId")
        snippet = item.get("snippet", {})
        title = snippet.get("title", query)
        channel = snippet.get("channelTitle", "YouTube")

        if not video_id:
            return None

        return {
            "title": html.unescape(title),
            "channel": html.unescape(channel),
            "video_id": video_id,
            "watch_url": f"https://www.youtube.com/watch?v={video_id}",
            "embed_url": f"https://www.youtube.com/embed/{video_id}?rel=0&modestbranding=1",
            "query": query,
        }
    except Exception as e:
        logger.warning(f"YouTube Data API search failed for {query}: {e}")
        return None


def _is_video_embeddable(video_id: str) -> bool:
    """Best-effort check to reduce unavailable/private embeds."""
    if not video_id:
        return False

    try:
        oembed_url = "https://www.youtube.com/oembed"
        params = {"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"}
        resp = requests.get(oembed_url, params=params, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return False

        # Secondary check: verify embed page playability marker when available.
        embed_resp = requests.get(
            f"https://www.youtube.com/embed/{video_id}",
            timeout=6,
            headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en;q=0.9"},
        )
        if embed_resp.status_code != 200:
            return False

        page = embed_resp.text
        if '"playabilityStatus":{"status":"OK"' in page:
            return True
        if '"UNPLAYABLE"' in page or '"ERROR"' in page or 'Video unavailable' in page:
            return False

        # Fall back to oEmbed success when explicit markers are absent.
        return True
    except Exception:
        return False


@app.route("/api/news", methods=["GET"])
def get_news():
    """Get current trending news for all five categories."""
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                name: executor.submit(_safe_parse_news_feed, name, url)
                for name, url in _NEWS_FEEDS.items()
            }
            results = {name: fut.result() for name, fut in futures.items()}

        return jsonify({
            "success": True,
            **results,
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Error getting news: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "south_india": [],
            "north_india": [],
            "international": [],
            "tech": [],
            "conflicts": [],
            "timestamp": datetime.now().isoformat(),
        }), 500


@app.route("/api/news/videos", methods=["GET"])
def get_news_videos():
    """Get a resilient pool of hot news videos with regional fallback candidates."""
    import random
    
    try:
        # Check if YouTube API key is configured
        use_api = False
        try:
            if _CONFIG_PATH.exists():
                cfg = json.load(open(_CONFIG_PATH, "r"))
                if cfg.get("youtube_api_key"):
                    use_api = True
        except Exception:
            use_api = False

        def fetch_videos_for_region(region_name: str, max_candidates: int = 4) -> list[dict]:
            """Collect several embeddable videos for a region."""
            queries = list(_NEWS_VIDEO_QUERIES.get(region_name, []))
            if not queries:
                return []
            
            # Shuffle queries for variety
            random.shuffle(queries)

            candidates: list[dict] = []
            fallback_candidates: list[dict] = []
            seen_ids: set[str] = set()

            # Try randomized queries and collect multiple embeddable candidates.
            for query in queries:
                try:
                    video = None
                    if use_api:
                        video = _youtube_api_search(query)

                    # Fallback to scraping when API is unavailable or returns nothing.
                    if not video:
                        video = _scrape_youtube_video(query)
                    
                    if not video:
                        continue

                    video_id = video.get("video_id", "")
                    if not video_id or video_id in seen_ids:
                        continue

                    # Keep a fallback pool in case strict validation yields nothing.
                    video["region"] = region_name
                    fallback_candidates.append(video)

                    if _is_video_embeddable(video_id):
                        candidates.append(video)
                        seen_ids.add(video_id)

                    if len(candidates) >= max_candidates:
                        break
                except Exception as e:
                    logger.debug(f"Video fetch failed for {region_name}/{query}: {e}")
                    continue

            # If strict checks filtered everything, fall back to best-effort candidates.
            if not candidates:
                for video in fallback_candidates:
                    video_id = video.get("video_id", "")
                    if not video_id or video_id in seen_ids:
                        continue
                    candidates.append(video)
                    seen_ids.add(video_id)
                    if len(candidates) >= max_candidates:
                        break

            return candidates

        # Fetch videos in parallel for all regions
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                name: executor.submit(fetch_videos_for_region, name)
                for name in ("south_india", "india", "international")
            }

            videos_by_region = {
                "south_india": futures["south_india"].result(),
                "india": futures["india"].result(),
                "international": futures["international"].result(),
            }

        # Build a mixed pool using round-robin selection from each region list.
        videos: list[dict] = []
        seen_ids: set[str] = set()
        max_rounds = max((len(videos_by_region[r]) for r in videos_by_region), default=0)

        for idx in range(max_rounds):
            for region_name in ("south_india", "india", "international"):
                region_list = videos_by_region.get(region_name, [])
                if idx >= len(region_list):
                    continue

                video = region_list[idx]
                video_id = video.get("video_id", "")
                if not video_id or video_id in seen_ids:
                    continue

                videos.append(video)
                seen_ids.add(video_id)

                # Keep payload size controlled while still providing fallback pool.
                if len(videos) >= 12:
                    break
            if len(videos) >= 12:
                break

        return jsonify({
            "success": True,
            "videos": videos,
            "videos_by_region": videos_by_region,
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Error getting news videos: {e}")
        # Static curated fallback — always-embeddable BBC/Reuters/NDTV live streams
        fallback_videos = [
            {"title": "BBC News Live", "video_id": "w_Ma8oQLmSM",
             "embed_url": "https://www.youtube.com/embed/w_Ma8oQLmSM?rel=0",
             "watch_url": "https://www.youtube.com/watch?v=w_Ma8oQLmSM",
             "region": "international", "source": "fallback"},
            {"title": "NDTV Live", "video_id": "H6ucoNCWEzA",
             "embed_url": "https://www.youtube.com/embed/H6ucoNCWEzA?rel=0",
             "watch_url": "https://www.youtube.com/watch?v=H6ucoNCWEzA",
             "region": "india", "source": "fallback"},
            {"title": "Republic World Live", "video_id": "D4bb_OBrSW0",
             "embed_url": "https://www.youtube.com/embed/D4bb_OBrSW0?rel=0",
             "watch_url": "https://www.youtube.com/watch?v=D4bb_OBrSW0",
             "region": "india", "source": "fallback"},
        ]
        return jsonify({
            "success": True,
            "videos": fallback_videos,
            "fallback": True,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        })


@app.route("/api/status", methods=["GET"])
def get_status():
    """Get current agent status."""
    try:
        if _PSUTIL:
            process = psutil.Process()
            cpu_percent = process.cpu_percent(interval=0.1)
            memory_info = process.memory_info()
            memory_percent = process.memory_percent()
        else:
            cpu_percent = 0.0
            memory_percent = 0.0

        return jsonify({
            "success": True,
            "awake": _agent_state.get("awake", False),
            "listening": _agent_state.get("listening", False),
            "last_command": _agent_state.get("last_command", ""),
            "last_command_time": _agent_state.get("last_command_time", 0),
            "uptime_seconds": _agent_state.get("uptime_seconds", 0),
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "timestamp": time.time(),
        })
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/metrics", methods=["GET"])
def get_metrics():
    """Get the latest metrics report."""
    try:
        from agent.metrics import get_metrics as _get_metrics

        return jsonify({"success": True, "metrics": _get_metrics().get_report()})
    except Exception as e:
        logger.error(f"Error getting metrics: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/logs", methods=["GET"])
def get_logs():
    """Get recent logs from file."""
    try:
        if not _LOG_FILE.exists():
            return jsonify({"success": True, "logs": []})

        # Read last 100 lines
        with open(_LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()[-100:]
        
        logs = [
            {
                "timestamp": datetime.now().isoformat(),
                "level": "INFO",
                "message": line.strip()
            }
            for line in lines if line.strip()
        ]
        
        return jsonify({"success": True, "logs": logs})
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/logs/live", methods=["GET"])
def get_live_logs():
    """Get logs from the queue (real-time)."""
    try:
        logs = []
        while not _log_queue.empty():
            try:
                log_entry = _log_queue.get_nowait()
                logs.append(log_entry)
            except Exception:
                break
        
        return jsonify({"success": True, "logs": logs})
    except Exception as e:
        logger.error(f"Error getting live logs: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/config", methods=["GET"])
def get_config():
    """Get current configuration (non-sensitive)."""
    try:
        return jsonify({
            "success": True,
            "config": {
                "version": "0.2.0",
                "models_path": str(_BASE_DIR / "models"),
                "log_file": str(_LOG_FILE),
                "default_browser": "chrome",
                "vad_enabled": True,
                "voice_timeout_seconds": 30,
            }
        })
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/settings", methods=["GET", "POST"])
def settings():
    """Get or update settings."""
    if request.method == "GET":
        try:
            return jsonify({
                "success": True,
                "settings": {
                    "wake_words": ["jarvis", "hey jarvis", "ok jarvis"],
                    "sleep_words": ["go to sleep", "sleep mode", "goodbye jarvis"],
                    "active_timeout_s": 30.0,
                    "energy_threshold": 300,
                    "vad_aggressiveness": 1,
                }
            })
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    elif request.method == "POST":
        try:
            data = request.get_json()
            # TODO: Persist settings to config file
            logger.info(f"Settings updated: {data}")
            return jsonify({"success": True, "message": "Settings updated"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500


def _chain_run_to_dict(chain_run) -> dict:
    """Serialize a ChainRun to a JSON-safe dict."""
    return {
        "id": chain_run.id,
        "goal": chain_run.goal,
        "status": chain_run.status,
        "created_at": chain_run.created_at,
        "steps": [
            {
                "id": s.id,
                "tool": s.tool,
                "parameters": s.parameters,
                "description": s.description,
                "status": s.status,
                "result": s.result,
                "error": s.error,
                "started_at": s.started_at,
                "ended_at": s.ended_at,
            }
            for s in chain_run.steps
        ],
    }


def _create_chain_internal(goal: str) -> dict:
    """Parse goal into steps, build a ChainRun, start it in a background thread. Returns chain metadata."""
    from agent.chain_runner import parse_chain_goal, run_chain, make_chain_run

    raw_steps = parse_chain_goal(goal)
    chain_run = make_chain_run(goal, raw_steps)

    with _chain_store_lock:
        _chain_store[chain_run.id] = chain_run
        if len(_chain_store) > 50:
            oldest = next(iter(_chain_store))
            del _chain_store[oldest]

    def _run_and_persist():
        run_chain(chain_run=chain_run, on_update=None, speak=None)
        _save_chain_store()

    threading.Thread(target=_run_and_persist, daemon=True, name=f"Chain-{chain_run.id}").start()

    logger.info(f"[Chain] Started {chain_run.id} ({len(chain_run.steps)} steps): {goal[:60]}")
    return {"chain_id": chain_run.id, "steps_count": len(chain_run.steps)}


@app.route("/api/command", methods=["POST"])
def send_command():
    """Route a dashboard command through the chain executor."""
    try:
        data = request.get_json()
        command = data.get("command", "").strip()

        if not command:
            return jsonify({"success": False, "error": "No command provided"}), 400

        if re.search(r"\b(current\s+news|latest\s+news|today'?s\s+news|news)\b", command, re.IGNORECASE):
            result = browser_control(
                parameters={"action": "go_to", "url": "http://127.0.0.1:5555/news", "browser": "chrome"},
                player=None,
            )
            logger.info(f"[Dashboard] News command: {command} -> {result}")
            return jsonify({"success": True, "message": "Opened news dashboard"})

        meta = _create_chain_internal(command)
        return jsonify({"success": True, "message": f"Chain started", **meta})

    except Exception as e:
        logger.error(f"Error sending command: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/chain", methods=["POST"])
def create_chain():
    """Parse a natural-language goal into a chain and start execution."""
    try:
        data = request.get_json()
        goal = (data or {}).get("goal", "").strip()
        if not goal:
            return jsonify({"success": False, "error": "No goal provided"}), 400
        meta = _create_chain_internal(goal)
        return jsonify({"success": True, **meta})
    except Exception as e:
        logger.error(f"Error creating chain: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/chain/<chain_id>", methods=["GET"])
def get_chain(chain_id: str):
    """Get a single chain run by ID."""
    with _chain_store_lock:
        chain_run = _chain_store.get(chain_id)
    if not chain_run:
        return jsonify({"success": False, "error": "Chain not found"}), 404
    return jsonify({"success": True, "chain": _chain_run_to_dict(chain_run)})


@app.route("/api/chains", methods=["GET"])
def get_chains():
    """Return the last 20 chain runs, newest first."""
    with _chain_store_lock:
        chains = list(_chain_store.values())
    chains.sort(key=lambda c: c.created_at, reverse=True)
    return jsonify({"success": True, "chains": [_chain_run_to_dict(c) for c in chains[:20]]})


@app.route("/api/action-history", methods=["GET"])
def get_action_history():
    """Get recent action execution history."""
    try:
        # TODO: Load from persistent store
        return jsonify({
            "success": True,
            "actions": [
                {
                    "id": 1,
                    "timestamp": time.time() - 300,
                    "command": "open chrome",
                    "tool": "open_app",
                    "status": "success",
                    "duration_ms": 1250,
                    "result": "Opened chrome."
                },
                {
                    "id": 2,
                    "timestamp": time.time() - 120,
                    "command": "search for python tutorials",
                    "tool": "browser_control",
                    "status": "success",
                    "duration_ms": 890,
                    "result": "Search completed in existing Chrome window."
                }
            ]
        })
    except Exception as e:
        logger.error(f"Error getting action history: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    try:
        from agent.error_recovery import get_recovery_manager

        recovery = get_recovery_manager()
        return jsonify({
            "status": "healthy",
            "timestamp": time.time(),
            "circuits": recovery.get_all_states(),
            "summary": recovery.get_health_summary(),
        }), 200
    except Exception as e:
        logger.error(f"Error getting health: {e}")
        return jsonify({"status": "degraded", "timestamp": time.time(), "error": str(e)}), 200


@app.route("/api/circuits", methods=["GET"])
def get_circuits():
    """Get circuit breaker states."""
    try:
        from agent.error_recovery import get_recovery_manager

        recovery = get_recovery_manager()
        return jsonify({"success": True, "circuits": recovery.get_all_states(), "summary": recovery.get_health_summary()})
    except Exception as e:
        logger.error(f"Error getting circuits: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/analytics", methods=["GET"])
def get_analytics():
    """Get advanced metrics analytics."""
    try:
        from agent.metrics import get_metrics
        from agent.metrics_analytics import MetricsAnalytics

        metrics_mgr = get_metrics()
        analytics = MetricsAnalytics(metrics_mgr)

        return jsonify({
            "success": True,
            "summary": analytics.get_dashboard_summary(),
            "tool_stats": analytics.get_tool_stats(),
            "success_rates": analytics.get_success_rates(),
            "failures": analytics.get_failure_summary(),
        })
    except Exception as e:
        logger.error(f"Error getting analytics: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/chart/<chart_type>", methods=["GET"])
def get_chart(chart_type):
    """Get chart data for visualization."""
    try:
        from agent.metrics import get_metrics
        from agent.metrics_analytics import MetricsAnalytics

        valid_types = ["success_rates", "execution_times", "tool_usage", "failures", "time_series"]
        if chart_type not in valid_types:
            return jsonify({"success": False, "error": f"Unknown chart type: {chart_type}"}), 400

        metrics_mgr = get_metrics()
        analytics = MetricsAnalytics(metrics_mgr)
        chart_data = analytics.get_chart_data(chart_type)

        return jsonify({"success": True, "type": chart_type, "data": chart_data})
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/insights", methods=["GET"])
def get_insights():
    """Get performance insights and recommendations."""
    try:
        from agent.metrics import get_metrics
        from agent.metrics_analytics import MetricsAnalytics

        metrics_mgr = get_metrics()
        analytics = MetricsAnalytics(metrics_mgr)

        slowest = analytics.get_slowest_tools(3)
        top_tools = analytics.get_top_tools(3)
        failures = analytics.get_failure_summary()

        insights = []

        if slowest:
            insights.append({
                "type": "warning",
                "title": "Slow Tools Detected",
                "message": f"{slowest[0][0]} is taking {slowest[0][1]:.2f}s on average",
            })

        if failures["total"] > 0:
            failure_rate = (failures["total"] / sum(len(d) for d in metrics_mgr.tool_durations.values())) * 100 if metrics_mgr.tool_durations else 0
            insights.append({
                "type": "error",
                "title": "Tool Failures",
                "message": f"{failures['total']} failures recorded ({failure_rate:.1f}% failure rate)",
            })

        if failures["circuit_broken"] > 0:
            insights.append({
                "type": "critical",
                "title": "Circuits Broken",
                "message": f"{failures['circuit_broken']} tools have circuit breakers active",
            })

        health = analytics.get_system_health_score()
        if health < 80:
            insights.append({
                "type": "warning",
                "title": "System Health Degraded",
                "message": f"Overall health score: {health:.1f}%",
            })

        return jsonify({"success": True, "insights": insights})
    except Exception as e:
        logger.error(f"Error generating insights: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _check_emotion_deps() -> dict:
    """Return which emotion detection dependencies are present/missing."""
    deps = {}
    for pkg, import_name in [("fer", "fer"), ("opencv-python", "cv2"),
                              ("tensorflow", "tensorflow"), ("numpy", "numpy")]:
        try:
            __import__(import_name)
            deps[pkg] = True
        except ImportError:
            deps[pkg] = False
    return deps


@app.route("/api/emotion/stats", methods=["GET"])
def get_emotion_stats():
    """Get emotion detection statistics including dependency status."""
    try:
        from core.emotion_detector import get_emotion_detector
        detector = get_emotion_detector()

        dep_status = _check_emotion_deps()
        missing    = [k for k, v in dep_status.items() if not v]

        if not detector.enabled:
            return jsonify({
                "success":     True,
                "enabled":     False,
                "missing_deps": missing,
                "install_cmd":  f"pip install {' '.join(missing)}" if missing else None,
                "reason":       f"Missing: {', '.join(missing)}" if missing else "Disabled in config",
                "deps":         dep_status,
            })

        stats = detector.get_emotion_stats()
        return jsonify({
            "success": True,
            "enabled": True,
            "deps":    dep_status,
            "stats":   stats,
        })
    except Exception as e:
        logger.error(f"Error getting emotion stats: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/emotion/start", methods=["POST"])
def start_emotion_detection():
    """Start emotion recording."""
    try:
        from core.emotion_detector import get_emotion_detector

        detector = get_emotion_detector()
        if not detector.enabled:
            return jsonify({"success": False, "error": "Emotion detection not available"}), 400

        duration = request.get_json().get("duration", 5.0) if request.is_json else 5.0
        detector.start_recording(duration)
        
        return jsonify({
            "success": True,
            "message": f"Emotion recording started for {duration}s"
        })
    except Exception as e:
        logger.error(f"Error starting emotion detection: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/emotion/stop", methods=["POST"])
def stop_emotion_detection():
    """Stop emotion recording."""
    try:
        from core.emotion_detector import get_emotion_detector

        detector = get_emotion_detector()
        detector.stop_recording()
        
        return jsonify({
            "success": True,
            "stats": detector.get_emotion_stats()
        })
    except Exception as e:
        logger.error(f"Error stopping emotion detection: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/memory", methods=["GET"])
def get_memory():
    """Return all stored memories."""
    try:
        from memory.memory_manager import load_memory
        return jsonify({"success": True, "memory": load_memory()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/memory/save", methods=["POST"])
def save_memory_entry():
    """Add or update a memory entry."""
    try:
        from memory.memory_manager import update_memory
        data = request.get_json(force=True) or {}
        category = data.get("category", "notes")
        key = data.get("key", "").strip()
        value = data.get("value", "").strip()
        if not key or not value:
            return jsonify({"success": False, "error": "key and value required"}), 400
        update_memory({category: {key: {"value": value}}})
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/guardian", methods=["GET"])
def get_guardian_snapshot():
    try:
        from agent.pc_guardian import get_guardian
        guardian = get_guardian()
        snap = guardian.snapshot if guardian else {}
        if not snap and _PSUTIL:
            import psutil
            mem = psutil.virtual_memory()
            snap = {
                "cpu":       psutil.cpu_percent(interval=0.2),
                "ram":       mem.percent,
                "disk_free": 100 - psutil.disk_usage("C:\\").percent,
            }
            bat = psutil.sensors_battery()
            if bat:
                snap["battery"] = bat.percent
                snap["plugged"]  = bat.power_plugged
        return jsonify({"success": True, "snapshot": snap})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/mood", methods=["GET"])
def get_mood():
    try:
        from memory.mood_tracker import _load, get_pattern
        log     = list(reversed(_load()))   # newest first
        pattern = get_pattern(days=7)
        return jsonify({"success": True, "log": log, "pattern": pattern})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/followups", methods=["GET"])
def get_followups():
    try:
        from memory.followups import load_followups
        return jsonify({"success": True, "followups": load_followups()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/followups/done", methods=["POST"])
def followup_done():
    try:
        from memory.followups import mark_done
        fid = (request.get_json(force=True) or {}).get("id", "")
        if fid:
            mark_done(fid)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/followups/dismiss", methods=["POST"])
def followup_dismiss():
    try:
        from memory.followups import dismiss
        fid = (request.get_json(force=True) or {}).get("id", "")
        if fid:
            dismiss(fid)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/memory/history", methods=["GET"])
def get_conversation_history():
    """Return episodic conversation history."""
    try:
        from memory.conversation_history import load_episodes
        episodes = load_episodes()
        return jsonify({"success": True, "episodes": list(reversed(episodes))})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/memory/forget", methods=["POST"])
def forget_memory_entry():
    """Delete a memory entry."""
    try:
        from memory.memory_manager import forget_memory
        data = request.get_json(force=True) or {}
        category = data.get("category", "notes")
        key = data.get("key", "").strip()
        if not key:
            return jsonify({"success": False, "error": "key required"}), 400
        result = forget_memory(key, category)
        return jsonify({"success": True, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def _get_gemini_api_key() -> str:
    """Load Gemini API key: keyring → api_keys.json fallback."""
    try:
        import keyring
        key = keyring.get_password("JarvisAI", "gemini_api_key")
        if key:
            return key
    except Exception:
        pass
    try:
        cfg = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
        return cfg.get("gemini_api_key", "")
    except Exception:
        return ""


@app.route("/api/semantic/search", methods=["GET"])
def semantic_search():
    """Semantic memory search via Gemini embeddings."""
    try:
        query = request.args.get("q", "").strip()
        top_k = min(int(request.args.get("top_k", 8)), 15)
        if not query:
            return jsonify({"success": False, "error": "q param required"}), 400
        api_key = _get_gemini_api_key()
        if not api_key:
            return jsonify({"success": False, "error": "API key not configured"}), 500
        from memory.semantic_store import search
        hits = search(query, api_key, top_k=top_k)
        return jsonify({"success": True, "results": hits})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/knowledge-graph", methods=["GET"])
def get_knowledge_graph():
    """Return the full knowledge graph."""
    try:
        from memory.knowledge_graph import load_graph
        graph = load_graph()
        return jsonify({"success": True, "graph": graph})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── File RAG routes ───────────────────────────────────────────────────────────

@app.route("/api/files/stats", methods=["GET"])
def get_file_stats():
    """Return file index statistics."""
    try:
        from memory.file_store import get_stats
        return jsonify({"success": True, "stats": get_stats()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/files/search", methods=["GET"])
def search_files_api():
    """Semantic search over indexed files."""
    from memory.file_store import _safe_query, search_files
    query = _safe_query(request.args.get("q", "").strip())
    try:
        top_k = max(1, min(int(request.args.get("top_k", 6)), 12))
    except (ValueError, TypeError):
        top_k = 6
    if not query:
        return jsonify({"success": False, "error": "q parameter required"}), 400
    try:
        hits = search_files(query, _get_gemini_api_key(), top_k=top_k)
        return jsonify({"success": True, "results": hits, "query": query})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/files/index", methods=["POST"])
def trigger_file_index():
    """Trigger a background re-index of default folders."""
    import threading
    try:
        folders = request.json.get("folders", []) if request.is_json else []
        from memory.file_store import scan_and_index, scan_default_folders
        def _bg():
            if folders:
                scan_and_index(folders, _get_gemini_api_key())
            else:
                scan_default_folders(_get_gemini_api_key())
        threading.Thread(target=_bg, daemon=True, name="FileIndexAPI").start()
        return jsonify({"success": True, "message": "Indexing started in background"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/files/remove", methods=["POST"])
def remove_file_api():
    """Remove a file from the index."""
    try:
        file_path = str((request.json or {}).get("file_path", "")).strip()
        if not file_path or len(file_path) > 1024:
            return jsonify({"success": False, "error": "file_path required"}), 400
        # Only allow removing paths that are already in the index
        from memory.file_store import _load_index, _lock
        with _lock:
            indexed_paths = {e.get("file_path") for e in _load_index()}
        if file_path not in indexed_paths:
            return jsonify({"success": False, "error": "Path not in index"}), 400
        from memory.file_store import remove_file
        ok = remove_file(file_path)
        return jsonify({"success": ok})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/files/index-folder", methods=["POST"])
def index_folder_api():
    """Index a custom folder path provided by the user."""
    try:
        folder = (request.json or {}).get("folder", "").strip()
        if not folder:
            return jsonify({"success": False, "error": "folder required"}), 400
        api_key = _get_api_key()
        if not api_key:
            return jsonify({"success": False, "error": "No API key"}), 400

        def _run():
            try:
                from memory.file_store import index_custom_folder
                n = index_custom_folder(folder, api_key)
                print(f"[FileStore] Custom folder done: {n} chunks ← {folder}")
            except Exception as e:
                print(f"[FileStore] Custom folder error: {e}")

        import threading
        threading.Thread(target=_run, daemon=True, name="FileCustom").start()
        return jsonify({"success": True, "message": f"Indexing started for: {folder}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ── Utility functions ──────────────────────────────────────────────────────────

def update_agent_state(state_dict: dict) -> None:
    """Update agent state from main.py."""
    global _agent_state
    _agent_state.update(state_dict)


def add_log(message: str, level: str = "INFO") -> None:
    """Add a log entry to the queue."""
    try:
        _log_queue.put({
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message
        }, block=False)
    except Exception:
        pass  # Queue full, skip


def start_server(host: str = "127.0.0.1", port: int = 5555, debug: bool = False) -> None:
    """Start the Flask server in a background thread."""
    _load_chain_store()   # restore persisted chains before serving

    def _run():
        try:
            logger.info(f"[GUI] Starting server at http://{host}:{port}")
            app.run(host=host, port=port, debug=debug, use_reloader=False)
        except Exception as e:
            logger.error(f"[GUI] Server error: {e}")

    thread = threading.Thread(target=_run, daemon=True, name="GUIServer")
    thread.start()
    return thread


if __name__ == "__main__":
    # Debug mode
    app.run(host="127.0.0.1", port=5555, debug=True)
