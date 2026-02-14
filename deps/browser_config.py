"""Configuration for browser operations"""

import os
from dataclasses import dataclass


@dataclass
class BrowserConfig:
    """Configuration for BrowserContextManager"""

    # Retry settings
    max_retries: int = 3
    base_backoff_seconds: float = 2.0
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 60.0
    jitter_factor: float = 0.1
    fd_exhaustion_backoff_seconds: float = 10.0

    # Timeout settings
    page_load_timeout_seconds: int = 60
    initial_page_wait_timeout_seconds: int = 20
    element_wait_timeout_seconds: int = 10
    cleanup_max_wait_seconds: float = 3.0
    process_poll_interval_seconds: float = 0.1

    # Circuit breaker settings
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_success_threshold: int = 2
    circuit_breaker_timeout_seconds: int = 300

    # File descriptor thresholds
    fd_warning_threshold_percent: float = 80.0
    fd_info_threshold_percent: float = 50.0

    @classmethod
    def from_environment(cls) -> "BrowserConfig":
        """Create config from environment variables, falling back to defaults"""
        return cls(
            # Retry settings
            max_retries=int(os.getenv("BROWSER_MAX_RETRIES", "3")),
            base_backoff_seconds=float(os.getenv("BROWSER_BASE_BACKOFF", "2.0")),
            backoff_multiplier=float(os.getenv("BROWSER_BACKOFF_MULTIPLIER", "2.0")),
            max_backoff_seconds=float(os.getenv("BROWSER_MAX_BACKOFF", "60.0")),
            jitter_factor=float(os.getenv("BROWSER_JITTER_FACTOR", "0.1")),
            fd_exhaustion_backoff_seconds=float(os.getenv("BROWSER_FD_EXHAUSTION_BACKOFF", "10.0")),
            # Timeout settings
            page_load_timeout_seconds=int(os.getenv("BROWSER_PAGE_LOAD_TIMEOUT", "60")),
            initial_page_wait_timeout_seconds=int(os.getenv("BROWSER_INITIAL_PAGE_WAIT_TIMEOUT", "20")),
            element_wait_timeout_seconds=int(os.getenv("BROWSER_ELEMENT_WAIT_TIMEOUT", "10")),
            cleanup_max_wait_seconds=float(os.getenv("BROWSER_CLEANUP_MAX_WAIT", "3.0")),
            process_poll_interval_seconds=float(os.getenv("BROWSER_PROCESS_POLL_INTERVAL", "0.1")),
            # Circuit breaker settings
            circuit_breaker_enabled=os.getenv("BROWSER_CIRCUIT_BREAKER_ENABLED", "true").lower() == "true",
            circuit_breaker_failure_threshold=int(os.getenv("BROWSER_CIRCUIT_BREAKER_THRESHOLD", "5")),
            circuit_breaker_success_threshold=int(os.getenv("BROWSER_CIRCUIT_BREAKER_SUCCESS_THRESHOLD", "2")),
            circuit_breaker_timeout_seconds=int(os.getenv("BROWSER_CIRCUIT_BREAKER_TIMEOUT", "300")),
            # File descriptor thresholds
            fd_warning_threshold_percent=float(os.getenv("BROWSER_FD_WARNING_THRESHOLD", "80.0")),
            fd_info_threshold_percent=float(os.getenv("BROWSER_FD_INFO_THRESHOLD", "50.0")),
        )
