"""
Advanced Error Recovery
=======================
Circuit breaker pattern, auto-retry, and fallback strategies for tools.

Features:
- Circuit breaker: disable failing tools temporarily
- Exponential backoff: retry with increasing delays
- Fallback tools: try alternative tool when primary fails
- Metrics tracking: monitor tool reliability
- User notification: inform about tool degradation

Usage:
    recovery = ErrorRecoveryManager()
    
    # Record a tool failure
    recovery.record_failure("browser_control", exception)
    
    # Check if tool is available
    if recovery.is_available("browser_control"):
        # Use tool
    else:
        # Use fallback or skip
        
    # Get circuit state
    state = recovery.get_circuit_state("browser_control")
"""

from __future__ import annotations

import time
from collections import defaultdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Tool disabled
    HALF_OPEN = "half_open"  # Testing after recovery


class ToolCircuit:
    """Circuit breaker for a single tool with exponential backoff."""

    # Backoff ladder: 60s → 120s → 300s → 600s → 1800s (30 min max)
    _BACKOFF = [60, 120, 300, 600, 1800]

    def __init__(
        self,
        tool_name: str,
        failure_threshold: int = 3,
        success_threshold: int = 2,
        timeout_seconds: int = 60,  # kept for API compat, used as backoff[0]
    ):
        self.tool_name        = tool_name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold

        self.state = CircuitState.CLOSED
        self.failure_count  = 0
        self.success_count  = 0
        self.open_count     = 0   # how many times circuit has opened — drives backoff
        self.last_failure_time: Optional[float] = None
        self.last_error_msg = ""

    def _current_timeout(self) -> int:
        """Return exponentially growing timeout based on how many times we've tripped."""
        idx = min(self.open_count, len(self._BACKOFF) - 1)
        return self._BACKOFF[idx]

    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state       = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.open_count    = max(0, self.open_count - 1)  # decay on full recovery
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self, error_msg: str = ""):
        self.failure_count    += 1
        self.last_failure_time = time.time()
        self.last_error_msg    = error_msg

        if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            self.state      = CircuitState.OPEN
            self.open_count += 1   # escalate backoff

        elif self.state == CircuitState.HALF_OPEN:
            self.state      = CircuitState.OPEN
            self.open_count += 1
            self.success_count = 0

    def is_available(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            elapsed = time.time() - (self.last_failure_time or 0)
            if elapsed > self._current_timeout():
                self.state         = CircuitState.HALF_OPEN
                self.failure_count = 0
                return True
            return False

        return True  # HALF_OPEN — allow one probe

    def get_state(self) -> dict:
        timeout = self._current_timeout()
        return {
            "tool":          self.tool_name,
            "state":         self.state.value,
            "failures":      self.failure_count,
            "successes":     self.success_count,
            "open_count":    self.open_count,
            "last_error":    self.last_error_msg,
            "timeout":       timeout,
            "recovery_time": (
                max(0, self.last_failure_time + timeout - time.time())
                if self.last_failure_time else None
            ),
        }


class ErrorRecoveryManager:
    """Manage error recovery for all tools."""

    def __init__(self):
        self.circuits: dict[str, ToolCircuit] = {}
        self.fallbacks: dict[str, list[str]] = {
            "browser_control": ["file_controller"],  # Fallback for browser: use file operations
            "web_search": ["browser_control"],  # Fallback for search: use browser directly
            "open_app": ["desktop_control"],  # Fallback: use desktop control
        }
        self.retry_delays = [1, 2, 5, 10]  # Exponential backoff in seconds

    def get_circuit(self, tool_name: str) -> ToolCircuit:
        """Get or create circuit for a tool."""
        if tool_name not in self.circuits:
            self.circuits[tool_name] = ToolCircuit(tool_name)
        return self.circuits[tool_name]

    def record_failure(self, tool_name: str, error: Exception | str):
        """Record a tool failure."""
        circuit = self.get_circuit(tool_name)
        error_msg = str(error)[:100]
        circuit.record_failure(error_msg)

    def record_success(self, tool_name: str):
        """Record a tool success."""
        circuit = self.get_circuit(tool_name)
        circuit.record_success()

    def is_available(self, tool_name: str) -> bool:
        """Check if tool is available."""
        circuit = self.get_circuit(tool_name)
        return circuit.is_available()

    def get_fallback_tools(self, tool_name: str) -> list[str]:
        """Get fallback tools for a tool."""
        return [t for t in self.fallbacks.get(tool_name, []) if self.is_available(t)]

    def get_all_states(self) -> dict[str, dict]:
        """Get state of all circuits."""
        return {name: circuit.get_state() for name, circuit in self.circuits.items()}

    def get_health_summary(self) -> dict:
        """Get overall system health."""
        states = self.get_all_states()
        total = len(states)
        closed = sum(1 for s in states.values() if s["state"] == "closed")
        open = sum(1 for s in states.values() if s["state"] == "open")

        return {
            "total_tools": total,
            "healthy": closed,
            "degraded": open,
            "health_percent": (closed / total * 100) if total > 0 else 100,
            "circuits": states,
        }


# Global recovery manager
_recovery_manager = ErrorRecoveryManager()


def get_recovery_manager() -> ErrorRecoveryManager:
    """Get the global error recovery manager."""
    return _recovery_manager
