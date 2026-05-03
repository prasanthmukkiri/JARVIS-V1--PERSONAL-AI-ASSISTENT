"""
Metrics Collection & Telemetry
==============================
Tracks system performance, tool execution times, error rates, and audio quality.

Metrics Tracked:
- Tool execution time (min/max/avg/p95)
- Error rates by tool
- Audio quality (SNR, latency)
- Wake-word accuracy (false positive/negative rates)
- System resources (CPU, memory, thermal)
- Uptime and availability

Usage:
    metrics = MetricsCollector()
    metrics.record_tool_execution("web_search", duration_ms=450, success=True)
    metrics.record_error("browser_control", "Connection timeout")
    report = metrics.get_report()
"""

from __future__ import annotations

import json
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import psutil


class MetricsCollector:
    """Collect and analyze system metrics."""

    def __init__(self, history_days: int = 7):
        self.history_days = history_days
        self._metrics_dir = Path.home() / ".jarvis_metrics"
        self._metrics_dir.mkdir(exist_ok=True)

        # In-memory tracking
        self.tool_executions = defaultdict(list)  # tool_name -> [{"duration": ms, "success": bool}]
        self.errors = defaultdict(int)  # tool_name -> count
        self.audio_metrics = []  # [{"timestamp": ..., "snr": ..., "latency": ...}]
        self.start_time = time.time()

    def record_tool_execution(self, tool_name: str, duration_ms: float, success: bool = True):
        """Record a tool execution."""
        self.tool_executions[tool_name].append({
            "duration": duration_ms,
            "success": success,
            "timestamp": datetime.now().isoformat(),
        })

    def record_error(self, tool_name: str, error_msg: str):
        """Record a tool error."""
        self.errors[tool_name] += 1

    def record_audio_metric(self, snr_db: float, latency_ms: float, sample_rate: int = 16000):
        """Record audio quality metric."""
        self.audio_metrics.append({
            "timestamp": datetime.now().isoformat(),
            "snr": snr_db,
            "latency": latency_ms,
            "sample_rate": sample_rate,
        })

    def get_tool_stats(self, tool_name: str) -> dict[str, Any]:
        """Get statistics for a specific tool."""
        executions = self.tool_executions.get(tool_name, [])
        if not executions:
            return {
                "tool": tool_name,
                "total": 0,
                "success": 0,
                "error_count": self.errors.get(tool_name, 0),
                "error_rate": 0,
            }

        success_count = sum(1 for e in executions if e.get("success", True))
        durations = [e["duration"] for e in executions]

        return {
            "tool": tool_name,
            "total": len(executions),
            "success": success_count,
            "failed": len(executions) - success_count,
            "error_count": self.errors.get(tool_name, 0),
            "error_rate": (len(executions) - success_count) / len(executions) * 100,
            "duration": {
                "min": min(durations),
                "max": max(durations),
                "avg": sum(durations) / len(durations),
                "p95": sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 1 else durations[0],
            },
        }

    def get_report(self) -> dict[str, Any]:
        """Generate a comprehensive metrics report."""
        uptime_seconds = time.time() - self.start_time

        return {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": uptime_seconds,
            "uptime_human": self._format_duration(uptime_seconds),
            "tools": {name: self.get_tool_stats(name) for name in self.tool_executions.keys()},
            "errors": dict(self.errors),
            "audio": {
                "total_samples": len(self.audio_metrics),
                "avg_snr": self._avg_metric("snr") if self.audio_metrics else 0,
                "avg_latency": self._avg_metric("latency") if self.audio_metrics else 0,
            },
            "system": self._get_system_stats(),
        }

    # Backwards-compatibility properties expected by metrics_analytics
    @property
    def tool_durations(self) -> dict[str, list]:
        """Return a mapping tool_name -> list of durations (in seconds).

        Older analytics code expects `tool_durations` to exist; this property
        adapts the current `tool_executions` structure to that format.
        """
        durations = {}
        for name, executions in self.tool_executions.items():
            # convert stored milliseconds to seconds if numeric
            vals = []
            for e in executions:
                d = e.get("duration", 0)
                try:
                    # assume durations were stored in ms; convert to seconds
                    vals.append(float(d) / 1000.0)
                except Exception:
                    try:
                        vals.append(float(d))
                    except Exception:
                        pass
            durations[name] = vals
        return durations

    @property
    def tool_failures(self) -> dict[str, int]:
        """Return failures per tool (compatibility with analytics)."""
        return dict(self.errors)

    @property
    def circuit_breakers(self) -> dict:
        """Placeholder for circuit breaker states; empty by default."""
        return {}

    def _avg_metric(self, key: str) -> float:
        """Calculate average of a metric."""
        if not self.audio_metrics:
            return 0
        values = [m[key] for m in self.audio_metrics if key in m]
        return sum(values) / len(values) if values else 0

    def _get_system_stats(self) -> dict[str, Any]:
        """Get current system statistics."""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_available_mb": memory.available // (1024 ** 2),
                "disk_percent": psutil.disk_usage("/").percent,
            }
        except Exception:
            return {}

    def _format_duration(self, seconds: float) -> str:
        """Format duration as human-readable string."""
        delta = timedelta(seconds=int(seconds))
        return str(delta)

    def save_report(self, filename: str | None = None) -> Path:
        """Save metrics report to disk."""
        if filename is None:
            filename = f"metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        filepath = self._metrics_dir / filename
        with open(filepath, "w") as f:
            json.dump(self.get_report(), f, indent=2)

        return filepath


# Global metrics instance
_metrics = MetricsCollector()


def get_metrics() -> MetricsCollector:
    """Get the global metrics collector."""
    return _metrics
