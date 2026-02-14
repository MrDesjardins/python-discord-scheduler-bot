"""Circuit breaker pattern for browser operations"""

import threading
import time
from enum import Enum
from typing import Optional


class CircuitBreakerState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing recovery


class BrowserCircuitBreaker:
    """
    Circuit breaker to prevent repeated browser startup failures.

    States:
    - CLOSED: Normal operation, all requests allowed
    - OPEN: Too many failures, rejecting all requests
    - HALF_OPEN: Testing recovery, allowing limited requests

    Transitions:
    - CLOSED -> OPEN: After failure_threshold consecutive failures
    - OPEN -> HALF_OPEN: After timeout_seconds elapsed
    - HALF_OPEN -> CLOSED: After success_threshold consecutive successes
    - HALF_OPEN -> OPEN: On any failure
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_seconds: int = 300,
    ):
        self._failure_threshold = failure_threshold
        self._success_threshold = success_threshold
        self._timeout_seconds = timeout_seconds

        self._state = CircuitBreakerState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

        # Statistics
        self._total_calls = 0
        self._total_successes = 0
        self._total_failures = 0
        self._state_transitions = 0

    def allow_request(self) -> bool:
        """
        Check if a request should be allowed.
        Returns True if request is allowed, False if circuit is open.
        """
        with self._lock:
            self._total_calls += 1

            if self._state == CircuitBreakerState.CLOSED:
                return True

            if self._state == CircuitBreakerState.OPEN:
                # Check if enough time has passed to transition to half-open
                if self._last_failure_time and (time.time() - self._last_failure_time) >= self._timeout_seconds:
                    self._transition_to(CircuitBreakerState.HALF_OPEN)
                    return True
                return False

            # HALF_OPEN state - allow request to test recovery
            return True

    def record_success(self) -> None:
        """Record a successful operation"""
        with self._lock:
            self._total_successes += 1
            self._consecutive_failures = 0

            if self._state == CircuitBreakerState.HALF_OPEN:
                self._consecutive_successes += 1
                if self._consecutive_successes >= self._success_threshold:
                    self._transition_to(CircuitBreakerState.CLOSED)
                    self._consecutive_successes = 0

    def record_failure(self, exception: Exception) -> None:
        """Record a failed operation"""
        with self._lock:
            self._total_failures += 1
            self._consecutive_successes = 0
            self._consecutive_failures += 1
            self._last_failure_time = time.time()

            if self._state == CircuitBreakerState.HALF_OPEN:
                # Any failure in half-open state reopens the circuit
                self._transition_to(CircuitBreakerState.OPEN)
            elif self._state == CircuitBreakerState.CLOSED:
                # Too many consecutive failures opens the circuit
                if self._consecutive_failures >= self._failure_threshold:
                    self._transition_to(CircuitBreakerState.OPEN)

    def _transition_to(self, new_state: CircuitBreakerState) -> None:
        """Transition to a new state (must be called with lock held)"""
        if new_state != self._state:
            old_state = self._state
            self._state = new_state
            self._state_transitions += 1

            # Log state transition
            from deps.log import print_warning_log, print_log  # pylint: disable=import-outside-toplevel

            if new_state == CircuitBreakerState.OPEN:
                print_warning_log(
                    f"Circuit breaker OPENED after {self._consecutive_failures} failures. "
                    f"Will retry after {self._timeout_seconds}s"
                )
            elif new_state == CircuitBreakerState.HALF_OPEN:
                print_log("Circuit breaker entering HALF_OPEN state - testing recovery")
            elif new_state == CircuitBreakerState.CLOSED:
                print_log(f"Circuit breaker CLOSED - recovered from {old_state.value} state")

    def get_state(self) -> CircuitBreakerState:
        """Get current state"""
        with self._lock:
            return self._state

    def get_stats(self) -> dict:
        """Get circuit breaker statistics"""
        with self._lock:
            success_rate = (
                (self._total_successes / self._total_calls * 100) if self._total_calls > 0 else 0.0
            )

            return {
                "state": self._state.value,
                "total_calls": self._total_calls,
                "total_successes": self._total_successes,
                "total_failures": self._total_failures,
                "success_rate_percent": round(success_rate, 2),
                "consecutive_failures": self._consecutive_failures,
                "consecutive_successes": self._consecutive_successes,
                "state_transitions": self._state_transitions,
                "last_failure_time": self._last_failure_time,
            }

    def reset(self) -> None:
        """Reset circuit breaker to initial state (for testing)"""
        with self._lock:
            self._state = CircuitBreakerState.CLOSED
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._last_failure_time = None
