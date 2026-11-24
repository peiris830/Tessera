"""Opaque pagination tokens.

DynamoDB returns `LastEvaluatedKey` when a page is full; passing it back as
`ExclusiveStartKey` continues from there. We hand it to clients as a URL-safe base64 string
(`nextToken`) together with the query's lower time bound, so page 2 runs exactly the same
query as page 1 even though "now" has moved on.

The token comes from the client, so it is untrusted: anything malformed raises
InvalidPageTokenError, and the caller validates the decoded key's contents.
"""

import base64
import json
from typing import Any

MAX_TOKEN_LENGTH = 1024


class InvalidPageTokenError(ValueError):
    pass


def encode_token(last_key: dict[str, Any], starts_from: str) -> str:
    raw = json.dumps({"k": last_key, "f": starts_from}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def decode_token(token: str) -> tuple[dict[str, Any], str]:
    if len(token) > MAX_TOKEN_LENGTH:
        raise InvalidPageTokenError("token too long")
    try:
        padded = token + "=" * (-len(token) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        key, starts_from = data["k"], data["f"]
    except (ValueError, KeyError, TypeError) as exc:  # bad base64/JSON/shape
        raise InvalidPageTokenError("malformed token") from exc
    if not isinstance(key, dict) or not isinstance(starts_from, str):
        raise InvalidPageTokenError("malformed token")
    return key, starts_from
