"""/v1/events: browse (public, no sign-in) and manage (owning organiser).

Browsing is public: API Gateway lets GET /v1/events and GET /v1/events/{id} through without a
token, so these routes never know who is calling and only ever show PUBLISHED and CANCELLED
events. Owners see their drafts via the authenticated /v1/organisers/me/events/{id}.

Rules for the write routes:
  - can't see it (missing, or someone else's DRAFT)    -> 404 EVENT_NOT_FOUND
  - can see it but it isn't yours (others' PUBLISHED)  -> 403 NOT_EVENT_OWNER
  - yours, but its state forbids the change            -> 409
"""

import logging
import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Query, Response
from pydantic import AwareDatetime

from app.auth import Caller, OrganiserCaller
from app.dependencies import Repo
from app.errors import APIError, error_responses
from app.models import Event, EventCreate, EventOut, EventPage, EventStatus, EventUpdate
from app.pagination import MAX_TOKEN_LENGTH, InvalidPageTokenError, decode_token, encode_token
from app.repository import EventConflictError, EventRepository, to_iso

logger = logging.getLogger("catalogue")

# Write routes declare OrganiserCaller, which requires a verified identity (401 otherwise):
# defence in depth, since API Gateway's JWT authorizer also protects them.
router = APIRouter(prefix="/v1/events", tags=["events"])

# Visible on the public routes. DRAFT is deliberately absent.
PUBLIC_STATUSES = frozenset({EventStatus.PUBLISHED, EventStatus.CANCELLED})


# ---------- browse (public) ----------


@router.get("", response_model=EventPage, responses=error_responses(400, 422))
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


@router.get("/{event_id}", response_model=EventOut, responses=error_responses(404, 422))
def get_event(event_id: str, repo: Repo) -> EventOut:
    """A published or cancelled event. Drafts are 404 here for everyone, including the owner."""
    event = repo.get(event_id)
    if event is None or event.status not in PUBLIC_STATUSES:
        raise APIError(404, "EVENT_NOT_FOUND", "Event not found")
    return EventOut.from_event(event)


# ---------- manage (organisers) ----------


@router.post("", status_code=201, response_model=EventOut, responses=error_responses(401, 403, 422))
def create_event(
    body: EventCreate, caller: OrganiserCaller, repo: Repo, response: Response
) -> EventOut:
    """Create a DRAFT event owned by the caller. Publish it separately."""
    now = datetime.now(UTC)
    event = Event(
        event_id=str(uuid.uuid4()),
        organiser_id=caller.user_id,
        status=EventStatus.DRAFT,
        created_at=now,
        updated_at=now,
        **body.model_dump(),
    )
    repo.create(event)
    logger.info("event created", extra={"eventId": event.event_id, "organiserId": caller.user_id})
    response.headers["Location"] = f"/v1/events/{event.event_id}"
    return EventOut.from_event(event)


@router.patch(
    "/{event_id}", response_model=EventOut, responses=error_responses(401, 403, 404, 409, 422)
)
def update_event(event_id: str, body: EventUpdate, caller: OrganiserCaller, repo: Repo) -> EventOut:
    event = load_owned(repo, event_id, caller)
    changes = body.model_dump(exclude_unset=True)

    if event.status == EventStatus.CANCELLED:
        raise APIError(409, "EVENT_NOT_EDITABLE", "Cancelled events can't be changed")
    if (
        event.status == EventStatus.PUBLISHED
        and "capacity" in changes
        and changes["capacity"] != event.capacity
    ):
        # Reservation snapshots capacity once bookings start (ADR 0003).
        raise APIError(409, "CAPACITY_LOCKED", "Capacity can't change after publishing")

    try:
        updated = repo.update_fields(
            event_id,
            changes,
            owner_id=caller.user_id,
            expected_status=event.status,
            now=datetime.now(UTC),
        )
    except EventConflictError as exc:
        raise _concurrent_change() from exc
    logger.info("event updated", extra={"eventId": event_id, "fields": sorted(changes)})
    return EventOut.from_event(updated)


@router.post(
    "/{event_id}/publish",
    response_model=EventOut,
    responses=error_responses(401, 403, 404, 409, 422),
)
def publish_event(event_id: str, caller: OrganiserCaller, repo: Repo) -> EventOut:
    event = load_owned(repo, event_id, caller)
    now = datetime.now(UTC)
    if event.status != EventStatus.DRAFT:
        raise APIError(409, "EVENT_NOT_DRAFT", "Only draft events can be published")
    if event.starts_at <= now:
        raise APIError(409, "EVENT_IN_PAST", "Events that have already started can't be published")

    try:
        published = repo.publish(event_id, owner_id=caller.user_id, now=now)
    except EventConflictError as exc:
        raise _concurrent_change() from exc
    logger.info("event published", extra={"eventId": event_id})
    return EventOut.from_event(published)


# ---------- helpers ----------


def load_owned(repo: EventRepository, event_id: str, caller: Caller) -> Event:
    """The caller's own event, else 404 (missing or someone else's draft: nothing to reveal)
    or 403 (someone else's published/cancelled event, which is public anyway)."""
    event = repo.get(event_id)
    if event is None:
        raise APIError(404, "EVENT_NOT_FOUND", "Event not found")
    if event.organiser_id != caller.user_id:
        if event.status not in PUBLIC_STATUSES:
            raise APIError(404, "EVENT_NOT_FOUND", "Event not found")
        raise APIError(403, "NOT_EVENT_OWNER", "You can only manage your own events")
    return event


def _concurrent_change() -> APIError:
    return APIError(409, "EVENT_STATE_CONFLICT", "The event changed meanwhile; reload and retry")
