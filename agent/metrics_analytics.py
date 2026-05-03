"""
Advanced metrics analytics and aggregation.
Computes performance statistics, trends, and insights from telemetry data.
"""
import json
import time
from collections import defaultdict
from statistics import mean, median, stdev
from typing import Dict, List, Any, Optional


class MetricsAnalytics:
    """Analyze tool performance metrics."""

    def __init__(self, metrics_manager=None):
        self.metrics = metrics_manager
        self.cache = {}
        self.cache_ttl = 30  # seconds

    def get_tool_stats(self) -> Dict[str, Any]:
        """Compute statistics for each tool."""
        if not self.metrics:
            return {}
        
        stats = {}
        for tool_name, durations in self.metrics.tool_durations.items():
            if not durations:
                continue
            
            stats[tool_name] = {
                "count": len(durations),
                "min": min(durations),
                "max": max(durations),
                "mean": mean(durations),
                "median": median(durations),
                "stdev": stdev(durations) if len(durations) > 1 else 0,
                "p95": sorted(durations)[int(len(durations) * 0.95)] if len(durations) > 0 else 0,
                "p99": sorted(durations)[int(len(durations) * 0.99)] if len(durations) > 0 else 0,
            }
        
        return stats

    def get_success_rates(self) -> Dict[str, float]:
        """Calculate success rate per tool."""
        if not self.metrics:
            return {}
        
        rates = {}
        for tool_name in self.metrics.tool_durations.keys():
            total = len(self.metrics.tool_durations.get(tool_name, []))
            failures = self.metrics.tool_failures.get(tool_name, 0)
            success = total - failures if total > 0 else 0
            rate = (success / total * 100) if total > 0 else 0
            rates[tool_name] = round(rate, 2)
        
        return rates

    def get_top_tools(self, limit: int = 5) -> List[tuple]:
        """Get most frequently used tools."""
        if not self.metrics:
            return []
        
        tools = [
            (name, len(durations))
            for name, durations in self.metrics.tool_durations.items()
        ]
        return sorted(tools, key=lambda x: x[1], reverse=True)[:limit]

    def get_slowest_tools(self, limit: int = 5) -> List[tuple]:
        """Get slowest tools by mean execution time."""
        stats = self.get_tool_stats()
        slowest = sorted(
            stats.items(),
            key=lambda x: x[1].get("mean", 0),
            reverse=True
        )[:limit]
        return [(name, data["mean"]) for name, data in slowest]

    def get_time_series(self, window_size: int = 10) -> Dict[str, List[float]]:
        """Get recent execution time trend for each tool."""
        if not self.metrics:
            return {}
        
        trends = {}
        for tool_name, durations in self.metrics.tool_durations.items():
            trends[tool_name] = durations[-window_size:] if len(durations) > 0 else []
        
        return trends

    def get_failure_summary(self) -> Dict[str, Any]:
        """Summarize tool failures."""
        if not self.metrics:
            return {"total": 0, "by_tool": {}}
        
        return {
            "total": sum(self.metrics.tool_failures.values()),
            "by_tool": dict(self.metrics.tool_failures),
            "circuit_broken": len(self.metrics.circuit_breakers),
        }

    def get_system_health_score(self) -> float:
        """Calculate overall system health (0-100)."""
        rates = self.get_success_rates()
        if not rates:
            return 100.0
        
        avg_success = mean(rates.values()) if rates else 100
        failures = self.get_failure_summary()
        circuit_penalty = min(failures["circuit_broken"] * 5, 20)
        
        health = max(0, avg_success - circuit_penalty)
        return round(health, 2)

    def get_dashboard_summary(self) -> Dict[str, Any]:
        """Get comprehensive dashboard summary."""
        return {
            "health_score": self.get_system_health_score(),
            "total_executions": sum(
                len(durations)
                for durations in self.metrics.tool_durations.values()
            ) if self.metrics else 0,
            "total_failures": self.get_failure_summary()["total"],
            "top_tools": self.get_top_tools(3),
            "slowest_tools": self.get_slowest_tools(3),
            "success_rates": self.get_success_rates(),
            "audio_metrics": self.metrics.audio_metrics if self.metrics else {},
        }

    def get_chart_data(self, chart_type: str) -> Dict[str, Any]:
        """Generate data for specific chart types."""
        if chart_type == "success_rates":
            rates = self.get_success_rates()
            return {
                "labels": list(rates.keys()),
                "values": list(rates.values()),
            }
        
        elif chart_type == "execution_times":
            stats = self.get_tool_stats()
            return {
                "labels": list(stats.keys()),
                "means": [s["mean"] for s in stats.values()],
                "p95": [s["p95"] for s in stats.values()],
                "p99": [s["p99"] for s in stats.values()],
            }
        
        elif chart_type == "tool_usage":
            top_tools = self.get_top_tools(10)
            return {
                "labels": [t[0] for t in top_tools],
                "values": [t[1] for t in top_tools],
            }
        
        elif chart_type == "failures":
            failures = self.get_failure_summary()
            return {
                "labels": list(failures["by_tool"].keys()),
                "values": list(failures["by_tool"].values()),
            }
        
        elif chart_type == "time_series":
            return self.get_time_series()
        
        return {}


# Global instance
_analytics = None


def get_analytics(metrics_manager=None) -> MetricsAnalytics:
    global _analytics
    if _analytics is None:
        _analytics = MetricsAnalytics(metrics_manager)
    return _analytics
