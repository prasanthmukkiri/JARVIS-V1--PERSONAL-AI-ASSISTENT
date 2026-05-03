"""
Enhanced error recovery with retry logic, fallback chains, and intelligent categorization.
"""
import time
import threading
from enum import Enum
from typing import Callable, Any, Optional, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error categorization for smarter recovery strategies."""
    NETWORK = "network"  # Network/connectivity issues
    TIMEOUT = "timeout"  # Tool execution timeout
    RESOURCE = "resource"  # Memory, CPU, or file system
    PERMISSION = "permission"  # Access denied or auth failures
    INVALID_INPUT = "invalid_input"  # Bad parameters or input
    TRANSIENT = "transient"  # Temporary/flaky issues
    PERMANENT = "permanent"  # Unrecoverable errors


@dataclass
class RetryConfig:
    """Retry strategy configuration."""
    max_attempts: int = 3
    initial_delay_ms: int = 100
    max_delay_ms: int = 5000
    backoff_multiplier: float = 2.0
    jitter_enabled: bool = True


@dataclass
class FallbackChain:
    """Chain of fallback alternatives for a tool."""
    tool_name: str
    primary: Callable
    fallbacks: List[tuple[str, Callable]]  # [(fallback_name, callable), ...]


class EnhancedRecoveryManager:
    """Manages error recovery with retry/fallback strategies."""

    def __init__(self):
        self.retry_config = RetryConfig()
        self.fallback_chains = {}
        self.error_history = {}
        self.lock = threading.Lock()

    def register_fallback_chain(self, chain: FallbackChain):
        """Register a fallback chain for a tool."""
        with self.lock:
            self.fallback_chains[chain.tool_name] = chain
            logger.info(f"[Recovery] Registered fallback chain for {chain.tool_name}")

    def categorize_error(self, error: Exception) -> ErrorCategory:
        """Categorize error for appropriate recovery strategy."""
        error_str = str(error).lower()
        error_type = type(error).__name__.lower()

        # Network errors
        if any(x in error_str for x in ['network', 'connection', 'socket', 'timeout', 'dns']):
            return ErrorCategory.NETWORK
        
        # Timeout errors
        if 'timeout' in error_str or 'timed out' in error_str:
            return ErrorCategory.TIMEOUT
        
        # Resource errors
        if any(x in error_str for x in ['memory', 'ram', 'disk', 'space', 'cpu']):
            return ErrorCategory.RESOURCE
        
        # Permission errors
        if any(x in error_str for x in ['permission', 'denied', 'forbidden', 'unauthorized', 'auth']):
            return ErrorCategory.PERMISSION
        
        # Invalid input
        if any(x in error_str for x in ['invalid', 'bad', 'unexpected', 'parse', 'json']):
            return ErrorCategory.INVALID_INPUT
        
        # Transient errors (typically retryable)
        if 'temporarily unavailable' in error_str or '503' in error_str or '429' in error_str:
            return ErrorCategory.TRANSIENT
        
        return ErrorCategory.PERMANENT

    def should_retry(self, category: ErrorCategory) -> bool:
        """Determine if error category warrants retry."""
        retryable = {
            ErrorCategory.NETWORK,
            ErrorCategory.TIMEOUT,
            ErrorCategory.TRANSIENT,
            ErrorCategory.RESOURCE,
        }
        return category in retryable

    def should_fallback(self, category: ErrorCategory) -> bool:
        """Determine if error category warrants fallback attempt."""
        fallbackable = {
            ErrorCategory.NETWORK,
            ErrorCategory.TIMEOUT,
            ErrorCategory.PERMISSION,
            ErrorCategory.TRANSIENT,
        }
        return category in fallbackable

    def execute_with_retry(
        self,
        tool_name: str,
        func: Callable,
        *args,
        **kwargs
    ) -> tuple[bool, Any, Optional[Exception]]:
        """Execute function with exponential backoff retry logic.
        
        Returns: (success, result, error)
        """
        config = self.retry_config
        delay_ms = config.initial_delay_ms
        last_error = None

        for attempt in range(1, config.max_attempts + 1):
            try:
                logger.info(f"[Recovery] {tool_name}: Attempt {attempt}/{config.max_attempts}")
                result = func(*args, **kwargs)
                if attempt > 1:
                    logger.info(f"[Recovery] {tool_name}: Recovered on attempt {attempt}")
                return (True, result, None)
            
            except Exception as e:
                last_error = e
                category = self.categorize_error(e)
                
                if not self.should_retry(category):
                    logger.error(f"[Recovery] {tool_name}: Non-retryable error ({category.value}): {e}")
                    return (False, None, e)
                
                if attempt < config.max_attempts:
                    # Add jitter
                    jitter = 0.1 if config.jitter_enabled else 0
                    sleep_time = delay_ms / 1000.0 * (1 + jitter)
                    logger.warning(f"[Recovery] {tool_name}: Retry in {sleep_time:.2f}s ({category.value})")
                    time.sleep(sleep_time)
                    delay_ms = min(int(delay_ms * config.backoff_multiplier), config.max_delay_ms)

        logger.error(f"[Recovery] {tool_name}: Failed after {config.max_attempts} attempts")
        return (False, None, last_error)

    def execute_with_fallback(
        self,
        tool_name: str,
        *args,
        **kwargs
    ) -> tuple[bool, Any, Optional[Exception], Optional[str]]:
        """Execute tool with fallback chain if primary fails.
        
        Returns: (success, result, error, tool_used)
        """
        chain = self.fallback_chains.get(tool_name)
        if not chain:
            logger.warning(f"[Recovery] No fallback chain for {tool_name}")
            return (False, None, None, None)

        # Try primary
        success, result, error = self.execute_with_retry(tool_name, chain.primary, *args, **kwargs)
        if success:
            return (True, result, None, tool_name)

        # Try fallbacks
        category = self.categorize_error(error) if error else ErrorCategory.PERMANENT
        if not self.should_fallback(category):
            logger.error(f"[Recovery] {tool_name}: Non-fallbackable error ({category.value})")
            return (False, None, error, tool_name)

        for fallback_name, fallback_func in chain.fallbacks:
            try:
                logger.info(f"[Recovery] {tool_name}: Attempting fallback '{fallback_name}'")
                result = fallback_func(*args, **kwargs)
                logger.info(f"[Recovery] {tool_name}: Fallback '{fallback_name}' succeeded")
                return (True, result, None, fallback_name)
            except Exception as e:
                logger.warning(f"[Recovery] Fallback '{fallback_name}' failed: {e}")
                last_error = e

        logger.error(f"[Recovery] {tool_name}: All fallbacks exhausted")
        return (False, None, last_error, None)

    def log_error(self, tool_name: str, error: Exception, category: Optional[ErrorCategory] = None):
        """Log error for analysis."""
        if category is None:
            category = self.categorize_error(error)

        with self.lock:
            if tool_name not in self.error_history:
                self.error_history[tool_name] = []
            
            self.error_history[tool_name].append({
                "timestamp": time.time(),
                "error": str(error),
                "category": category.value,
            })

    def get_error_summary(self, tool_name: str) -> dict:
        """Get error history for a tool."""
        with self.lock:
            history = self.error_history.get(tool_name, [])
            if not history:
                return {}
            
            categories = {}
            for entry in history:
                cat = entry["category"]
                categories[cat] = categories.get(cat, 0) + 1
            
            return {
                "total_errors": len(history),
                "by_category": categories,
                "last_error": history[-1]["error"] if history else None,
            }


# Global instance
_recovery_manager = None


def get_recovery_manager() -> EnhancedRecoveryManager:
    global _recovery_manager
    if _recovery_manager is None:
        _recovery_manager = EnhancedRecoveryManager()
    return _recovery_manager
