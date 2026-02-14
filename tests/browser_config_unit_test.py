"""Unit tests for browser configuration"""

import os
import pytest
from deps.browser_config import BrowserConfig


def test_browser_config_defaults():
    """Test default configuration values"""
    config = BrowserConfig()

    # Retry settings
    assert config.max_retries == 3
    assert config.base_backoff_seconds == 2.0
    assert config.backoff_multiplier == 2.0
    assert config.max_backoff_seconds == 60.0
    assert config.jitter_factor == 0.1
    assert config.fd_exhaustion_backoff_seconds == 10.0

    # Timeout settings
    assert config.page_load_timeout_seconds == 60
    assert config.initial_page_wait_timeout_seconds == 20
    assert config.element_wait_timeout_seconds == 10
    assert config.cleanup_max_wait_seconds == 3.0
    assert config.process_poll_interval_seconds == 0.1

    # Circuit breaker settings
    assert config.circuit_breaker_enabled is True
    assert config.circuit_breaker_failure_threshold == 5
    assert config.circuit_breaker_success_threshold == 2
    assert config.circuit_breaker_timeout_seconds == 300

    # File descriptor thresholds
    assert config.fd_warning_threshold_percent == 80.0
    assert config.fd_info_threshold_percent == 50.0


def test_browser_config_from_environment(monkeypatch):
    """Test configuration from environment variables"""
    # Set environment variables
    monkeypatch.setenv("BROWSER_MAX_RETRIES", "5")
    monkeypatch.setenv("BROWSER_BASE_BACKOFF", "3.0")
    monkeypatch.setenv("BROWSER_BACKOFF_MULTIPLIER", "3.0")
    monkeypatch.setenv("BROWSER_MAX_BACKOFF", "120.0")
    monkeypatch.setenv("BROWSER_JITTER_FACTOR", "0.2")
    monkeypatch.setenv("BROWSER_FD_EXHAUSTION_BACKOFF", "15.0")
    monkeypatch.setenv("BROWSER_PAGE_LOAD_TIMEOUT", "90")
    monkeypatch.setenv("BROWSER_INITIAL_PAGE_WAIT_TIMEOUT", "30")
    monkeypatch.setenv("BROWSER_ELEMENT_WAIT_TIMEOUT", "15")
    monkeypatch.setenv("BROWSER_CLEANUP_MAX_WAIT", "5.0")
    monkeypatch.setenv("BROWSER_PROCESS_POLL_INTERVAL", "0.2")
    monkeypatch.setenv("BROWSER_CIRCUIT_BREAKER_ENABLED", "false")
    monkeypatch.setenv("BROWSER_CIRCUIT_BREAKER_THRESHOLD", "10")
    monkeypatch.setenv("BROWSER_CIRCUIT_BREAKER_SUCCESS_THRESHOLD", "3")
    monkeypatch.setenv("BROWSER_CIRCUIT_BREAKER_TIMEOUT", "600")
    monkeypatch.setenv("BROWSER_FD_WARNING_THRESHOLD", "90.0")
    monkeypatch.setenv("BROWSER_FD_INFO_THRESHOLD", "60.0")

    config = BrowserConfig.from_environment()

    # Verify all values were read from environment
    assert config.max_retries == 5
    assert config.base_backoff_seconds == 3.0
    assert config.backoff_multiplier == 3.0
    assert config.max_backoff_seconds == 120.0
    assert config.jitter_factor == 0.2
    assert config.fd_exhaustion_backoff_seconds == 15.0
    assert config.page_load_timeout_seconds == 90
    assert config.initial_page_wait_timeout_seconds == 30
    assert config.element_wait_timeout_seconds == 15
    assert config.cleanup_max_wait_seconds == 5.0
    assert config.process_poll_interval_seconds == 0.2
    assert config.circuit_breaker_enabled is False
    assert config.circuit_breaker_failure_threshold == 10
    assert config.circuit_breaker_success_threshold == 3
    assert config.circuit_breaker_timeout_seconds == 600
    assert config.fd_warning_threshold_percent == 90.0
    assert config.fd_info_threshold_percent == 60.0


def test_browser_config_circuit_breaker_enabled_variations(monkeypatch):
    """Test circuit breaker enabled parsing"""
    # Test "true" (lowercase)
    monkeypatch.setenv("BROWSER_CIRCUIT_BREAKER_ENABLED", "true")
    config = BrowserConfig.from_environment()
    assert config.circuit_breaker_enabled is True

    # Test "True" (capitalized)
    monkeypatch.setenv("BROWSER_CIRCUIT_BREAKER_ENABLED", "True")
    config = BrowserConfig.from_environment()
    assert config.circuit_breaker_enabled is True

    # Test "false"
    monkeypatch.setenv("BROWSER_CIRCUIT_BREAKER_ENABLED", "false")
    config = BrowserConfig.from_environment()
    assert config.circuit_breaker_enabled is False

    # Test "False"
    monkeypatch.setenv("BROWSER_CIRCUIT_BREAKER_ENABLED", "False")
    config = BrowserConfig.from_environment()
    assert config.circuit_breaker_enabled is False

    # Test "0"
    monkeypatch.setenv("BROWSER_CIRCUIT_BREAKER_ENABLED", "0")
    config = BrowserConfig.from_environment()
    assert config.circuit_breaker_enabled is False


def test_browser_config_partial_environment(monkeypatch):
    """Test that unset environment variables fall back to defaults"""
    # Only set some environment variables
    monkeypatch.setenv("BROWSER_MAX_RETRIES", "7")
    monkeypatch.setenv("BROWSER_PAGE_LOAD_TIMEOUT", "45")

    config = BrowserConfig.from_environment()

    # Check overridden values
    assert config.max_retries == 7
    assert config.page_load_timeout_seconds == 45

    # Check defaults for unset values
    assert config.base_backoff_seconds == 2.0
    assert config.element_wait_timeout_seconds == 10
    assert config.circuit_breaker_enabled is True
