"""Organiser endpoints: create, update, publish, list own events, with role/ownership checks."""

from datetime import UTC, datetime, timedelta

import pytest

from app.models import EventStatus
from app.pagination import encode_token
from tests.conftest import ATTENDEE, ORGANISER, OTHER_ORGANISER, make_event


def future(days: int = 30) -> str:
    return (datetime.now(UTC) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_event_body(**overrides) -> dict:
    body = {
        "title": "Synthetic Launch Party",
        "description": "Test event",
        "venue": {"name": "Test Arena", "city": "Testville"},
        "startsAt": future(),
        "capacity": 250,
    }
    return {**body, **overrides}


def error_code(response) -> str:
    return response.json()["error"]["code"]


# ---------- create ----------


def test_organiser_creates_draft_event(client, act_as):
    act_as(ORGANISER)

    response = client.post("/v1/events", json=new_event_body())

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "DRAFT"
    assert body["capacity"] == 250
    assert response.headers["Location"] == f"/v1/events/{body['eventId']}"


def test_created_draft_is_visible_to_owner_only(client, act_as):
    act_as(ORGANISER)
    event_id = client.post("/v1/events", json=new_event_body()).json()["eventId"]
    mine = f"/v1/organisers/me/events/{event_id}"

    assert client.get(mine).json()["status"] == "DRAFT"
    act_as(OTHER_ORGANISER)
    assert client.get(mine).status_code == 404  # someone else's draft: not revealed
    act_as(ATTENDEE)
    assert client.get(mine).status_code == 403  # organiser route


def test_drafts_never_appear_on_public_routes_even_for_owner(client, act_as):
    act_as(ORGANISER)
    event_id = client.post("/v1/events", json=new_event_body()).json()["eventId"]

    for caller in (ORGANISER, ATTENDEE, None):
        act_as(caller)
        assert client.get(f"/v1/events/{event_id}").status_code == 404


def test_my_event_route_for_others_published_event_is_403(client, act_as, repo):
    event = make_event(organiser_id=OTHER_ORGANISER.user_id)
    repo.create(event)
    act_as(ORGANISER)

    response = client.get(f"/v1/organisers/me/events/{event.event_id}")

    assert response.status_code == 403
    assert error_code(response) == "NOT_EVENT_OWNER"


def test_my_event_route_requires_identity_and_existing_event(client, act_as):
    act_as(None)
    assert client.get("/v1/organisers/me/events/nope").status_code == 401
    act_as(ORGANISER)
    assert client.get("/v1/organisers/me/events/nope").status_code == 404


def test_attendee_cannot_create_event(client, act_as):
    act_as(ATTENDEE)

    response = client.post("/v1/events", json=new_event_body())

    assert response.status_code == 403
    assert error_code(response) == "FORBIDDEN"


def test_unauthenticated_cannot_create_event(client, act_as):
    act_as(None)

    assert client.post("/v1/events", json=new_event_body()).status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"startsAt": "2020-01-01T00:00:00Z"},  # in the past
        {"startsAt": "2030-01-01T00:00:00"},  # no timezone
        {"title": "   "},  # blank after stripping whitespace
        {"capacity": 0},
        {"organiserId": "someone-else"},  # mass assignment attempt
        {"status": "PUBLISHED"},  # mass assignment attempt
        {"venue": {"name": "X", "city": "Y", "extra": "z"}},
    ],
)
def test_create_rejects_invalid_or_server_owned_fields(client, act_as, overrides):
    act_as(ORGANISER)

    response = client.post("/v1/events", json=new_event_body(**overrides))

    assert response.status_code == 422
    assert error_code(response) == "VALIDATION_ERROR"


# ---------- update ----------


def test_owner_updates_any_field_of_draft(client, repo, act_as):
    event = make_event(status=EventStatus.DRAFT)
    repo.create(event)
    act_as(ORGANISER)

    response = client.patch(
        f"/v1/events/{event.event_id}", json={"title": "Renamed", "capacity": 500}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"
    assert repo.get(event.event_id).capacity == 500


def test_owner_can_rename_published_event(client, repo, act_as):
    event = make_event(status=EventStatus.PUBLISHED)
    repo.create(event)
    act_as(ORGANISER)

    response = client.patch(f"/v1/events/{event.event_id}", json={"title": "Renamed"})

    assert response.status_code == 200


def test_capacity_is_locked_after_publishing(client, repo, act_as):
    event = make_event(status=EventStatus.PUBLISHED)
    repo.create(event)
    act_as(ORGANISER)

    response = client.patch(f"/v1/events/{event.event_id}", json={"capacity": 999})

    assert response.status_code == 409
    assert error_code(response) == "CAPACITY_LOCKED"
    assert repo.get(event.event_id).capacity == event.capacity


def test_cancelled_event_cannot_be_updated(client, repo, act_as):
    event = make_event(status=EventStatus.CANCELLED)
    repo.create(event)
    act_as(ORGANISER)

    response = client.patch(f"/v1/events/{event.event_id}", json={"title": "x"})

    assert response.status_code == 409
    assert error_code(response) == "EVENT_NOT_EDITABLE"


def test_other_organiser_gets_403_on_published_event(client, repo, act_as):
    event = make_event(status=EventStatus.PUBLISHED)
    repo.create(event)
    act_as(OTHER_ORGANISER)

    response = client.patch(f"/v1/events/{event.event_id}", json={"title": "Hijacked"})

    assert response.status_code == 403
    assert error_code(response) == "NOT_EVENT_OWNER"
    assert repo.get(event.event_id).title == event.title


def test_other_organiser_gets_404_on_draft(client, repo, act_as):
    event = make_event(status=EventStatus.DRAFT)
    repo.create(event)
    act_as(OTHER_ORGANISER)

    response = client.patch(f"/v1/events/{event.event_id}", json={"title": "Hijacked"})

    assert response.status_code == 404


def test_attendee_cannot_update(client, repo, act_as):
    event = make_event()
    repo.create(event)
    act_as(ATTENDEE)

    assert client.patch(f"/v1/events/{event.event_id}", json={"title": "x"}).status_code == 403


def test_update_missing_event_returns_404_and_creates_nothing(client, repo, act_as):
    act_as(ORGANISER)

    response = client.patch("/v1/events/does-not-exist", json={"title": "x"})

    assert response.status_code == 404
    assert repo.get("does-not-exist") is None


@pytest.mark.parametrize(
    "body",
    [{}, {"title": None}, {"status": "PUBLISHED"}, {"startsAt": "2020-01-01T00:00:00Z"}],
)
def test_update_rejects_empty_null_or_invalid_bodies(client, repo, act_as, body):
    event = make_event(status=EventStatus.DRAFT)
    repo.create(event)
    act_as(ORGANISER)

    response = client.patch(f"/v1/events/{event.event_id}", json=body)

    assert response.status_code == 422


# ---------- publish ----------


def test_owner_publishes_draft_and_it_becomes_browsable(client, repo, act_as):
    event = make_event(status=EventStatus.DRAFT)
    repo.create(event)
    act_as(ORGANISER)

    response = client.post(f"/v1/events/{event.event_id}/publish")

    assert response.status_code == 200
    assert response.json()["status"] == "PUBLISHED"
    act_as(ATTENDEE)
    listed = [e["eventId"] for e in client.get("/v1/events").json()["items"]]
    assert event.event_id in listed


def test_publishing_twice_returns_409(client, repo, act_as):
    event = make_event(status=EventStatus.DRAFT)
    repo.create(event)
    act_as(ORGANISER)
    client.post(f"/v1/events/{event.event_id}/publish")

    response = client.post(f"/v1/events/{event.event_id}/publish")

    assert response.status_code == 409
    assert error_code(response) == "EVENT_NOT_DRAFT"


def test_cannot_publish_event_in_the_past(client, repo, act_as):
    event = make_event(status=EventStatus.DRAFT, starts_in=timedelta(hours=-1))
    repo.create(event)
    act_as(ORGANISER)

    response = client.post(f"/v1/events/{event.event_id}/publish")

    assert response.status_code == 409
    assert error_code(response) == "EVENT_IN_PAST"


def test_other_organiser_cannot_publish(client, repo, act_as):
    event = make_event(status=EventStatus.DRAFT)
    repo.create(event)
    act_as(OTHER_ORGANISER)

    assert client.post(f"/v1/events/{event.event_id}/publish").status_code == 404
    assert repo.get(event.event_id).status == EventStatus.DRAFT


# ---------- list own events ----------


def test_organiser_lists_only_own_events_in_all_statuses(client, repo, act_as):
    mine = [
        make_event(title="draft", status=EventStatus.DRAFT, starts_in=timedelta(days=3)),
        make_event(title="published", starts_in=timedelta(days=1)),
        make_event(title="past", starts_in=timedelta(days=-5)),
    ]
    for event in [*mine, make_event(title="theirs", organiser_id=OTHER_ORGANISER.user_id)]:
        repo.create(event)
    act_as(ORGANISER)

    body = client.get("/v1/organisers/me/events").json()

    assert [e["title"] for e in body["items"]] == ["past", "published", "draft"]


def test_my_events_paginates(client, repo, act_as):
    for i in range(3):
        repo.create(make_event(title=f"e{i}", starts_in=timedelta(days=i + 1)))
    act_as(ORGANISER)

    first = client.get("/v1/organisers/me/events", params={"limit": 2}).json()
    second = client.get(
        "/v1/organisers/me/events", params={"limit": 2, "nextToken": first["nextToken"]}
    ).json()

    assert [e["title"] for e in first["items"] + second["items"]] == ["e0", "e1", "e2"]


def test_my_events_rejects_another_organisers_token(client, repo, act_as):
    for i in range(2):
        repo.create(make_event(starts_in=timedelta(days=i + 1)))
    act_as(ORGANISER)
    token = client.get("/v1/organisers/me/events", params={"limit": 1}).json()["nextToken"]

    act_as(OTHER_ORGANISER)
    response = client.get("/v1/organisers/me/events", params={"nextToken": token})

    assert response.status_code == 400


def test_forged_token_for_another_organiser_is_rejected(client, act_as):
    act_as(ORGANISER)
    forged = encode_token(
        {"eventId": "x", "organiserId": OTHER_ORGANISER.user_id, "startsAt": future()},
        ORGANISER.user_id,
    )

    response = client.get("/v1/organisers/me/events", params={"nextToken": forged})

    assert response.status_code == 400


def test_attendee_cannot_list_organiser_events(client, act_as):
    act_as(ATTENDEE)

    assert client.get("/v1/organisers/me/events").status_code == 403
