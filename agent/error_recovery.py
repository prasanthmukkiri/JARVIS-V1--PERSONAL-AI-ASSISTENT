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
    """Circuit breaker for a single tool."""

    def __init__(
        self,
        tool_name: str,
        failure_threshold: int = 3,
        success_threshold: int = 2,
        timeout_seconds: int = 60,
    ):
        """
        Initialize circuit breaker.

        Args:
            tool_name: Name of the tool
            failure_threshold: Failures before opening circuit
            success_threshold: Successes needed to close circuit
            timeout_seconds: Time before attempting recovery
        """
        self.tool_name = tool_name
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_seconds = timeout_seconds

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_error_msg = ""

    def record_success(self):
        """Record a successful execution."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self, error_msg: str = ""):
        """Record a failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.last_error_msg = error_msg

        if self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN

        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.success_count = 0

    def is_available(self) -> bool:
        """Check if tool can be used."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self.last_failure_time and time.time() - self.last_failure_time > self.timeout_seconds:
                self.state = CircuitState.HALF_OPEN
                self.failure_count = 0
                return True
            return False

        # HALF_OPEN
        return True

    def get_state(self) -> dict:
        """Get circuit state information."""
        return {
            "tool": self.tool_name,
            "state": self.state.value,
            "failures": self.failure_count,
            "successes": self.success_count,
            "last_error": self.last_error_msg,
            "recovery_time": (
                self.last_failure_time + self.timeout_seconds - time.time()
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
