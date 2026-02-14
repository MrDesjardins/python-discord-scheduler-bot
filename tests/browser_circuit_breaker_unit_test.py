"""Unit tests for browser circuit breaker"""

import time
import threading
import pytest
from deps.browser_circuit_breaker import BrowserCircuitBreaker, CircuitBreakerState


@pytest.fixture
def circuit_breaker():
    """Create a circuit breaker for testing"""
    cb = BrowserCircuitBreaker(
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=1,  # 1 second timeout, tests wait 2s for margin
    )
    return cb


def test_circuit_breaker_initial_state(circuit_breaker):
    """Test circuit breaker starts in CLOSED state"""
    assert circuit_breaker.get_state() == CircuitBreakerState.CLOSED
    assert circuit_breaker.allow_request() is True


def test_circuit_breaker_closed_to_open_transition(circuit_breaker):
    """Test circuit opens after failure threshold"""
    # Should stay closed for first 2 failures
    circuit_breaker.record_failure(Exception("Test error 1"))
    assert circuit_breaker.get_state() == CircuitBreakerState.CLOSED
    assert circuit_breaker.allow_request() is True

    circuit_breaker.record_failure(Exception("Test error 2"))
    assert circuit_breaker.get_state() == CircuitBreakerState.CLOSED
    assert circuit_breaker.allow_request() is True

    # Third failure should open the circuit
    circuit_breaker.record_failure(Exception("Test error 3"))
    assert circuit_breaker.get_state() == CircuitBreakerState.OPEN
    assert circuit_breaker.allow_request() is False


def test_circuit_breaker_open_to_half_open_transition(circuit_breaker):
    """Test circuit transitions from OPEN to HALF_OPEN after timeout"""
    # Open the circuit
    for _ in range(3):
        circuit_breaker.record_failure(Exception("Test error"))

    assert circuit_breaker.get_state() == CircuitBreakerState.OPEN
    assert circuit_breaker.allow_request() is False

    # Wait for timeout (1 second + 1 second buffer = 2 seconds total)
    time.sleep(2.0)

    # Next request should transition to half-open
    assert circuit_breaker.allow_request() is True
    assert circuit_breaker.get_state() == CircuitBreakerState.HALF_OPEN


def test_circuit_breaker_half_open_to_closed_transition(circuit_breaker):
    """Test circuit closes after success threshold in half-open state"""
    # Open the circuit
    for _ in range(3):
        circuit_breaker.record_failure(Exception("Test error"))

    # Wait for timeout and transition to half-open
    time.sleep(2.0)
    circuit_breaker.allow_request()  # Transition to half-open

    assert circuit_breaker.get_state() == CircuitBreakerState.HALF_OPEN

    # First success - should stay half-open
    circuit_breaker.record_success()
    assert circuit_breaker.get_state() == CircuitBreakerState.HALF_OPEN

    # Second success - should close the circuit
    circuit_breaker.record_success()
    assert circuit_breaker.get_state() == CircuitBreakerState.CLOSED
    assert circuit_breaker.allow_request() is True


def test_circuit_breaker_half_open_to_open_on_failure(circuit_breaker):
    """Test circuit reopens on any failure in half-open state"""
    # Open the circuit
    for _ in range(3):
        circuit_breaker.record_failure(Exception("Test error"))

    # Wait for timeout and transition to half-open
    time.sleep(2.0)
    circuit_breaker.allow_request()

    assert circuit_breaker.get_state() == CircuitBreakerState.HALF_OPEN

    # Any failure in half-open state should reopen the circuit
    circuit_breaker.record_failure(Exception("Test error"))
    assert circuit_breaker.get_state() == CircuitBreakerState.OPEN
    assert circuit_breaker.allow_request() is False


def test_circuit_breaker_success_resets_failure_count(circuit_breaker):
    """Test that success resets consecutive failure count"""
    # Record 2 failures
    circuit_breaker.record_failure(Exception("Test error 1"))
    circuit_breaker.record_failure(Exception("Test error 2"))
    assert circuit_breaker.get_state() == CircuitBreakerState.CLOSED

    # Record a success - should reset failure count
    circuit_breaker.record_success()

    # Now 3 more failures needed to open (not 1)
    circuit_breaker.record_failure(Exception("Test error 3"))
    assert circuit_breaker.get_state() == CircuitBreakerState.CLOSED

    circuit_breaker.record_failure(Exception("Test error 4"))
    assert circuit_breaker.get_state() == CircuitBreakerState.CLOSED

    circuit_breaker.record_failure(Exception("Test error 5"))
    assert circuit_breaker.get_state() == CircuitBreakerState.OPEN


def test_circuit_breaker_statistics(circuit_breaker):
    """Test circuit breaker statistics collection"""
    # Call allow_request to increment total_calls
    circuit_breaker.allow_request()
    circuit_breaker.allow_request()
    circuit_breaker.allow_request()

    # Record some operations
    circuit_breaker.record_success()
    circuit_breaker.record_success()
    circuit_breaker.record_failure(Exception("Test error"))

    stats = circuit_breaker.get_stats()

    assert stats["state"] == "closed"
    assert stats["total_calls"] == 3
    assert stats["total_successes"] == 2
    assert stats["total_failures"] == 1
    assert stats["success_rate_percent"] == pytest.approx(66.67, rel=0.1)
    assert stats["consecutive_failures"] == 1
    assert stats["consecutive_successes"] == 0
    assert stats["state_transitions"] == 0  # No transitions yet
    assert stats["last_failure_time"] is not None


def test_circuit_breaker_state_transition_count(circuit_breaker):
    """Test state transition counting"""
    # Initial state
    assert circuit_breaker.get_stats()["state_transitions"] == 0

    # CLOSED -> OPEN
    for _ in range(3):
        circuit_breaker.record_failure(Exception("Test error"))
    assert circuit_breaker.get_stats()["state_transitions"] == 1

    # OPEN -> HALF_OPEN
    time.sleep(2.0)
    circuit_breaker.allow_request()
    assert circuit_breaker.get_stats()["state_transitions"] == 2

    # HALF_OPEN -> CLOSED
    circuit_breaker.record_success()
    circuit_breaker.record_success()
    assert circuit_breaker.get_stats()["state_transitions"] == 3


def test_circuit_breaker_thread_safety():
    """Test circuit breaker is thread-safe"""
    cb = BrowserCircuitBreaker(failure_threshold=100, success_threshold=2, timeout_seconds=10)

    def record_operations():
        for i in range(50):
            if i % 2 == 0:
                cb.record_success()
            else:
                cb.record_failure(Exception("Test error"))
            cb.allow_request()

    # Run multiple threads concurrently
    threads = [threading.Thread(target=record_operations) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify statistics are consistent
    stats = cb.get_stats()
    assert stats["total_successes"] + stats["total_failures"] == 250  # 50 ops * 5 threads


def test_circuit_breaker_reset(circuit_breaker):
    """Test circuit breaker reset functionality"""
    # Open the circuit
    for _ in range(3):
        circuit_breaker.record_failure(Exception("Test error"))

    assert circuit_breaker.get_state() == CircuitBreakerState.OPEN

    # Reset
    circuit_breaker.reset()

    # Should be back to initial state
    assert circuit_breaker.get_state() == CircuitBreakerState.CLOSED
    assert circuit_breaker.allow_request() is True

    stats = circuit_breaker.get_stats()
    assert stats["consecutive_failures"] == 0
    assert stats["consecutive_successes"] == 0
    assert stats["last_failure_time"] is None
