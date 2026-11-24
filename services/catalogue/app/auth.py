"""Who is calling, and what may they do?

Authentication happens BEFORE this code runs: API Gateway's JWT authorizer verifies the
Cognito token (signature, issuer, audience, expiry) and rejects bad tokens with 401. For
valid tokens it passes the claims to Lambda inside the event at
    requestContext.authorizer.jwt.claims
Mangum exposes that event to FastAPI as request.scope["aws.event"].

We trust these claims because only API Gateway can invoke the function. Identity is never
read from a client-supplied header. Running locally (no API Gateway) there are no claims, so
every protected route returns 401; tests inject a caller via dependency overrides.
"""

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request

from app.errors import APIError

ATTENDEE = "attendee"
ORGANISER = "organiser"
VENUE_STAFF = "venue_staff"


@dataclass(frozen=True)
class Caller:
    user_id: str  # Cognito `sub`: a stable, random ID (never an email or name)
    groups: frozenset[str]

    def is_in(self, group: str) -> bool:
        return group in self.groups


def caller_from_event(event: Any) -> Caller | None:
    """Extract the caller from an API Gateway (HTTP API) event, or None if absent/invalid."""
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
    except (KeyError, TypeError):
        return None
    if not isinstance(claims, dict):
        return None
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        return None
    return Caller(user_id=sub, groups=_parse_groups(claims.get("cognito:groups")))


def _parse_groups(raw: Any) -> frozenset[str]:
    """HTTP API flattens list claims to a string like "[organiser attendee]"; accept both."""
    if raw is None:
        return frozenset()
    if isinstance(raw, list):
        return frozenset(str(group) for group in raw)
    text = str(raw).strip()
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    return frozenset(text.replace(",", " ").split())


def get_caller(request: Request) -> Caller:
    caller = caller_from_event(request.scope.get("aws.event"))
    if caller is None:
        raise APIError(401, "UNAUTHENTICATED", "Authentication required")
    return caller


CurrentCaller = Annotated[Caller, Depends(get_caller)]


def require_organiser(caller: CurrentCaller) -> Caller:
    if not caller.is_in(ORGANISER):
        raise APIError(403, "FORBIDDEN", "Organiser role required")
    return caller


OrganiserCaller = Annotated[Caller, Depends(require_organiser)]
