from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.models import EventStatus
from app.pagination import InvalidPageTokenError
from app.repository import EventAlreadyExistsError, EventConflictError, to_iso
from tests.conftest import make_event


def now_iso() -> str:
    return to_iso(datetime.now(UTC))


def test_to_iso_normalises_timezone_and_precision():
    colombo = timezone(timedelta(hours=5, minutes=30))
    value = datetime(2026, 12, 1, 19, 30, 15, 999999, tzinfo=colombo)

    assert to_iso(value) == "2026-12-01T14:00:15Z"


def test_create_then_get_round_trips(repo):
    event = make_event()
    repo.create(event)

    assert repo.get(event.event_id) == event.model_copy(
        update={  # stored at second precision
            "starts_at": event.starts_at.replace(microsecond=0),
            "created_at": event.created_at.replace(microsecond=0),
            "updated_at": event.updated_at.replace(microsecond=0),
        }
    )


def test_get_missing_returns_none(repo):
    assert repo.get("does-not-exist") is None


def test_create_refuses_to_overwrite_existing_event(repo):
    event = make_event()
    repo.create(event)

    with pytest.raises(EventAlreadyExistsError):
        repo.create(event.model_copy(update={"title": "Overwritten"}))
    assert repo.get(event.event_id).title == event.title


def test_list_published_filters_and_sorts(repo):
    later = make_event(starts_in=timedelta(days=10), title="later")
    sooner = make_event(starts_in=timedelta(days=2), title="sooner")
    for event in [
        later,
        sooner,
        make_event(starts_in=timedelta(days=-1), title="past"),
        make_event(status=EventStatus.DRAFT, title="draft"),
        make_event(status=EventStatus.CANCELLED, title="cancelled"),
    ]:
        repo.create(event)

    events, last_key = repo.list_published(now_iso(), limit=10)

    assert [e.title for e in events] == ["sooner", "later"]
    assert last_key is None


@pytest.mark.parametrize(
    "bad_key",
    [
        {"eventId": "x"},  # missing fields
        {"eventId": "x", "status": "DRAFT", "startsAt": "2999-01-01T00:00:00Z"},  # wrong status
        {"eventId": "x", "status": "PUBLISHED", "startsAt": "2000-01-01T00:00:00Z"},  # before range
        {"eventId": 1, "status": "PUBLISHED", "startsAt": "2999-01-01T00:00:00Z"},  # wrong type
        {"eventId": "x", "status": "PUBLISHED", "startsAt": "2999-01-01T00:00:00Z", "y": "z"},
    ],
)
def test_list_published_rejects_foreign_start_keys(repo, bad_key):
    with pytest.raises(InvalidPageTokenError):
        repo.list_published(now_iso(), limit=10, start_key=bad_key)


# ---------- conditional writes: the race guards ----------


def test_update_fails_if_status_changed_since_read(repo):
    """Simulates a race: we read DRAFT, someone publishes, then our draft-only edit lands."""
    event = make_event(status=EventStatus.DRAFT)
    repo.create(event)
    repo.publish(event.event_id, owner_id=event.organiser_id, now=datetime.now(UTC))

    with pytest.raises(EventConflictError):
        repo.update_fields(
            event.event_id,
            {"capacity": 5},
            owner_id=event.organiser_id,
            expected_status=EventStatus.DRAFT,
            now=datetime.now(UTC),
        )
    assert repo.get(event.event_id).capacity == event.capacity


def test_update_fails_for_non_owner_even_without_route_checks(repo):
    event = make_event()
    repo.create(event)

    with pytest.raises(EventConflictError):
        repo.update_fields(
            event.event_id,
            {"title": "Hijacked"},
            owner_id="someone-else",
            expected_status=EventStatus.PUBLISHED,
            now=datetime.now(UTC),
        )


def test_update_never_creates_a_missing_item(repo):
    """UpdateItem is an upsert; attribute_exists(eventId) prevents phantom items."""
    with pytest.raises(EventConflictError):
        repo.update_fields(
            "ghost",
            {"title": "x"},
            owner_id="org-0001",
            expected_status=EventStatus.DRAFT,
            now=datetime.now(UTC),
        )
    assert repo.get("ghost") is None


def test_publish_refuses_event_that_already_started(repo):
    event = make_event(status=EventStatus.DRAFT, starts_in=timedelta(minutes=-1))
    repo.create(event)

    with pytest.raises(EventConflictError):
        repo.publish(event.event_id, owner_id=event.organiser_id, now=datetime.now(UTC))


def test_update_changes_gsi_sort_key(repo):
    """Changing startsAt also re-sorts the event in the browse index."""
    a = make_event(title="a", starts_in=timedelta(days=1))
    b = make_event(title="b", starts_in=timedelta(days=2))
    repo.create(a)
    repo.create(b)

    repo.update_fields(
        a.event_id,
        {"starts_at": datetime.now(UTC) + timedelta(days=3)},
        owner_id=a.organiser_id,
        expected_status=EventStatus.PUBLISHED,
        now=datetime.now(UTC),
    )

    events, _ = repo.list_published(now_iso(), limit=10)
    assert [e.title for e in events] == ["b", "a"]
