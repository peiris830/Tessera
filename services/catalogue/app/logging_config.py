"""Structured (JSON) logging.

Every line is a single JSON object containing the service name and current correlation ID,
so CloudWatch Logs Insights can filter by field. Extra fields can be added per call:
    logger.info("event created", extra={"eventId": event_id})
Never log personal data; use synthetic user IDs only.
"""

import json
import logging
import sys
from datetime import UTC, datetime

from app.correlation import get_correlation_id

# Attributes every LogRecord has; anything else on the record came from `extra=`.
_STANDARD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", None, None))) | {
    "message",
    "asctime",
}


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "message": record.getMessage(),
            "correlationId": get_correlation_id(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                entry[key] = value
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry, default=str)


def configure_logging(service: str, level: str = "INFO") -> None:
    """Replace any existing root handlers (Lambda pre-installs one) with a JSON handler."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
