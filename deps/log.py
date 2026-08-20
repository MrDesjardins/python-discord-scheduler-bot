"""Log into the console and the file."""

import logging
import json
from logging.handlers import RotatingFileHandler

logger = logging.getLogger("my_logger")
logger.setLevel(logging.INFO)

# https://docs.python.org/3/library/logging.html#logging.Formatter
formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

# Create a file handler to write logs to a file
file_handler = RotatingFileHandler(
    "app.log", mode="a", maxBytes=5 * 1024 * 1024, backupCount=2, encoding=None, delay=False
)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Create a stream handler to print logs to the console
console_handler = logging.StreamHandler()
# You can set the desired log level for console output
console_handler.setLevel(logging.DEBUG)
console_handler.setFormatter(formatter)

# Add the handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)

# AI prompts can be large and may contain the exact data needed to reproduce an
# inaccurate answer. Keep them in a separate, structured rotating log instead of
# making the operational app.log difficult to read.
ai_audit_logger = logging.getLogger("ai_audit")
ai_audit_logger.setLevel(logging.INFO)
ai_audit_logger.propagate = False
ai_audit_handler = RotatingFileHandler(
    "ai_audit.log",
    mode="a",
    maxBytes=25 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
    delay=False,
)
ai_audit_handler.setLevel(logging.INFO)
ai_audit_handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
ai_audit_logger.addHandler(ai_audit_handler)


def print_log(message: str) -> None:
    """Print the message to the log"""
    logger.info(message)


def print_error_log(message: str) -> None:
    """Print the error to the log"""
    logger.error(message)


def print_warning_log(message: str) -> None:
    """Print the warning to the log"""
    logger.warning(message)


def print_ai_audit_log(
    *,
    request_id: str,
    phase: str,
    request_type: str,
    content: str | None = None,
    provider: str | None = None,
    metadata: dict | None = None,
) -> None:
    """Write a structured prompt/response record for later AI quality review."""
    payload = {
        "request_id": request_id,
        "phase": phase,
        "request_type": request_type,
        "provider": provider,
        "content": content,
        "metadata": metadata or {},
    }
    ai_audit_logger.info(json.dumps(payload, ensure_ascii=False, default=str))
