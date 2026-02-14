"""Custom exceptions for browser operations"""


class BrowserException(Exception):
    """Base exception for all browser-related errors"""


class BrowserStartupException(BrowserException):
    """Raised when browser fails to start"""

    def __init__(self, message: str, retryable: bool = True):
        super().__init__(message)
        self.retryable = retryable


class BrowserTimeoutException(BrowserException):
    """Raised when browser operation times out"""


class BrowserResourceException(BrowserException):
    """Raised when browser hits resource limits (e.g., file descriptors)"""


class BrowserVersionMismatchException(BrowserStartupException):
    """Raised when Chrome and chromedriver versions don't match"""

    def __init__(self, message: str):
        super().__init__(message, retryable=False)


class CircuitBreakerOpenException(BrowserException):
    """Raised when circuit breaker is open and not accepting requests"""
