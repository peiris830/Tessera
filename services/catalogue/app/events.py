"""Public read endpoints for events. Create/update (organiser-only) arrive in step 2c."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import AwareDatetime

from app.dependencies import get_repository
from app.errors import APIError
from app.models import EventOut, EventPage, EventStatus
from app.pagination import MAX_TOKEN_LENGTH, InvalidPageTokenError, decode_token, encode_token
from app.repository import EventRepository, to_iso

router = APIRouter(prefix="/v1/events", tags=["events"])

Repo = Annotated[EventRepository, Depends(get_repository)]

# Statuses an unauthenticated-style "public" read may see. DRAFT stays hidden (404) so its
# existence isn't revealed; organisers will see their drafts via their own endpoint (2c).
_PUBLIC_STATUSES = {EventStatus.PUBLISHED, EventStatus.CANCELLED}


@router.get("", response_model=EventPage)
def list_events(
    repo: Repo,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    next_token: Annotated[str | None, Query(alias="nextToken", max_length=MAX_TOKEN_LENGTH)] = None,
    starts_from: Annotated[AwareDatetime | None, Query(alias="from")] = None,
) -> EventPage:
    """Upcoming published events, soonest first. Follow `nextToken` for more pages."""
    try:
        if next_token:
            start_key, from_iso = decode_token(next_token)
            if starts_from is not None and to_iso(starts_from) != from_iso:
                raise InvalidPageTokenError("token belongs to a different 'from' value")
        else:
            start_key, from_iso = None, to_iso(starts_from or datetime.now(UTC))
        events, last_key = repo.list_published(from_iso, limit, start_key)
    except InvalidPageTokenError as exc:
        raise APIError(400, "INVALID_NEXT_TOKEN", "nextToken is invalid or expired") from exc

    return EventPage(
        items=[EventOut.from_event(e) for e in events],
        next_token=encode_token(last_key, from_iso) if last_key else None,
    )


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str, repo: Repo) -> EventOut:
    event = repo.get(event_id)
    if event is None or event.status not in _PUBLIC_STATUSES:
        raise APIError(404, "EVENT_NOT_FOUND", "Event not found")
    return EventOut.from_event(event)
