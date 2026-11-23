"""Correlation ID handling.

A correlation ID ties together every log line and call that belongs to one user action,
across services. It travels in the X-Correlation-Id header and is kept in a ContextVar so
any code handling the current request can read it without passing it around.
"""

import re
import uuid
from contextvars import ContextVar

HEADER = "X-Correlation-Id"

# Only accept short, simple IDs from callers. Anything else (too long, spaces, newlines)
# is replaced, so a client can't inject fake log lines through this header.
_VALID = re.compile(r"[A-Za-z0-9._-]{1,128}")

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


def resolve_correlation_id(incoming: str | None) -> str:
    """Return the caller's ID if it is well-formed, otherwise a new UUID."""
    if incoming and _VALID.fullmatch(incoming):
        return incoming
    return str(uuid.uuid4())


def set_correlation_id(value: str) -> None:
    _correlation_id.set(value)


def get_correlation_id() -> str:
    return _correlation_id.get()
