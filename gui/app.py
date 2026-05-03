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
import threading
import time
from datetime import datetime
from pathlib import Path
from queue import Queue

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

try:
    import psutil
    _PSUTIL = True
except ImportError:
    _PSUTIL = False


# ── constants ──────────────────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent.parent
_GUI_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _BASE_DIR / "config" / "api_keys.json"
_LOG_FILE = _BASE_DIR / "jarvis_log.txt"

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


# ── Flask app ──────────────────────────────────────────────────────────────────
app = Flask(__name__, template_folder=_GUI_DIR / "templates", static_folder=_GUI_DIR / "static")
CORS(app)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── API Routes ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main dashboard HTML."""
    return render_template("dashboard.html")


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


@app.route("/api/command", methods=["POST"])
def send_command():
    """Send a voice command directly."""
    try:
        data = request.get_json()
        command = data.get("command", "").strip()
        
        if not command:
            return jsonify({"success": False, "error": "No command provided"}), 400
        
        # TODO: Inject command into executor
        logger.info(f"[Dashboard] Manual command: {command}")
        
        return jsonify({
            "success": True,
            "message": f"Command queued: {command}"
        })
    except Exception as e:
        logger.error(f"Error sending command: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


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


@app.route("/api/emotion/stats", methods=["GET"])
def get_emotion_stats():
    """Get emotion detection statistics."""
    try:
        from core.emotion_detector import get_emotion_detector

        detector = get_emotion_detector()
        if not detector.enabled:
            return jsonify({
                "success": True,
                "enabled": False,
                "reason": "Emotion detection not available (install fer and opencv-python)"
            })

        stats = detector.get_emotion_stats()
        return jsonify({
            "success": True,
            "enabled": True,
            "stats": stats
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
