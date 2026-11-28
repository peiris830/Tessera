"""/v1/organisers/me: the calling organiser's own resources."""

from typing import Annotated

from fastapi import APIRouter, Query

from app.auth import OrganiserCaller
from app.dependencies import Repo
from app.errors import APIError, error_responses
from app.events import load_owned
from app.models import EventOut, EventPage
from app.pagination import MAX_TOKEN_LENGTH, InvalidPageTokenError, decode_token, encode_token

router = APIRouter(prefix="/v1/organisers/me", tags=["organisers"])


@router.get("/events", response_model=EventPage, responses=error_responses(400, 401, 403, 422))
def list_my_events(
    caller: OrganiserCaller,
    repo: Repo,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    next_token: Annotated[str | None, Query(alias="nextToken", max_length=MAX_TOKEN_LENGTH)] = None,
) -> EventPage:
    """All of the caller's events (drafts, published, cancelled), ordered by start time."""
    try:
        start_key = None
        if next_token:
            start_key, scope = decode_token(next_token)
            if scope != caller.user_id:  # a token issued to a different organiser
                raise InvalidPageTokenError("token belongs to another caller")
        events, last_key = repo.list_by_organiser(caller.user_id, limit, start_key)
    except InvalidPageTokenError as exc:
        raise APIError(400, "INVALID_NEXT_TOKEN", "nextToken is invalid or expired") from exc

    return EventPage(
        items=[EventOut.from_event(e) for e in events],
        next_token=encode_token(last_key, caller.user_id) if last_key else None,
    )


@router.get(
    "/events/{event_id}", response_model=EventOut, responses=error_responses(401, 403, 404, 422)
)
def get_my_event(event_id: str, caller: OrganiserCaller, repo: Repo) -> EventOut:
    """One of the caller's own events in any status, including drafts (the public
    GET /v1/events/{id} never returns drafts). Other organisers' events: 404 or 403."""
    return EventOut.from_event(load_owned(repo, event_id, caller))
