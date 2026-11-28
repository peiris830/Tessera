from datetime import timedelta

import pytest

from app.models import EventStatus
from app.pagination import encode_token
from tests.conftest import make_event


def test_get_event_returns_public_fields_in_camel_case(client, repo):
    event = make_event()
    repo.create(event)

    response = client.get(f"/v1/events/{event.event_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["eventId"] == event.event_id
    assert body["startsAt"].endswith("Z")
    assert body["venue"] == {"name": "Test Hall", "city": "Testville"}
    assert set(body) == {
        "eventId", "title", "description", "venue", "startsAt", "capacity", "status"
    }  # fmt: skip
    assert "organiserId" not in body


def test_anonymous_visitors_can_browse_and_read_published_events(client, repo, act_as):
    event = make_event()
    repo.create(event)
    act_as(None)

    assert client.get(f"/v1/events/{event.event_id}").status_code == 200
    assert [e["eventId"] for e in client.get("/v1/events").json()["items"]] == [event.event_id]


def test_get_cancelled_event_is_still_visible(client, repo):
    event = make_event(status=EventStatus.CANCELLED)
    repo.create(event)

    assert client.get(f"/v1/events/{event.event_id}").json()["status"] == "CANCELLED"


@pytest.mark.parametrize("status", [EventStatus.DRAFT, None])
def test_get_draft_or_missing_event_returns_404(client, repo, status):
    event_id = "missing"
    if status is not None:
        event = make_event(status=status)
        repo.create(event)
        event_id = event.event_id

    response = client.get(f"/v1/events/{event_id}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EVENT_NOT_FOUND"


def test_list_returns_upcoming_published_events_soonest_first(client, repo):
    for title, days, status in [
        ("in 5 days", 5, EventStatus.PUBLISHED),
        ("in 1 day", 1, EventStatus.PUBLISHED),
        ("yesterday", -1, EventStatus.PUBLISHED),
        ("draft", 2, EventStatus.DRAFT),
    ]:
        repo.create(make_event(title=title, starts_in=timedelta(days=days), status=status))

    body = client.get("/v1/events").json()

    assert [e["title"] for e in body["items"]] == ["in 1 day", "in 5 days"]
    assert body["nextToken"] is None


def test_list_paginates_without_gaps_or_duplicates(client, repo):
    created = [make_event(title=f"e{i}", starts_in=timedelta(days=i + 1)) for i in range(5)]
    for event in created:
        repo.create(event)

    titles, token, pages = [], None, 0
    while True:
        params = {"limit": 2, **({"nextToken": token} if token else {})}
        body = client.get("/v1/events", params=params).json()
        titles += [e["title"] for e in body["items"]]
        token, pages = body["nextToken"], pages + 1
        if token is None or pages > 10:
            break

    assert titles == ["e0", "e1", "e2", "e3", "e4"]


def test_list_respects_from_parameter(client, repo):
    repo.create(make_event(title="soon", starts_in=timedelta(days=1)))
    repo.create(make_event(title="far", starts_in=timedelta(days=60)))
    future = make_event(starts_in=timedelta(days=30)).starts_at.isoformat().replace("+00:00", "Z")

    body = client.get("/v1/events", params={"from": future}).json()

    assert [e["title"] for e in body["items"]] == ["far"]


@pytest.mark.parametrize(
    "token",
    [
        "not-base64-$$$",
        "bm90IGpzb24",  # base64 of "not json"
        encode_token(  # well-formed token, but for a key this query could never produce
            {"eventId": "x", "status": "DRAFT", "startsAt": "2999-01-01T00:00:00Z"},
            "2000-01-01T00:00:00Z",
        ),
    ],
)
def test_list_rejects_invalid_next_token(client, token):
    response = client.get("/v1/events", params={"nextToken": token})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_NEXT_TOKEN"


def test_list_rejects_oversized_next_token(client):
    response = client.get("/v1/events", params={"nextToken": "a" * 1025})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_rejects_token_reused_with_different_from(client, repo):
    for i in range(3):
        repo.create(make_event(starts_in=timedelta(days=i + 1)))
    token = client.get("/v1/events", params={"limit": 1}).json()["nextToken"]

    response = client.get("/v1/events", params={"nextToken": token, "from": "2030-01-01T00:00:00Z"})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_NEXT_TOKEN"


@pytest.mark.parametrize("limit", [0, 101, "abc"])
def test_list_validates_limit(client, limit):
    response = client.get("/v1/events", params={"limit": limit})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_rejects_naive_from_datetime(client):
    response = client.get("/v1/events", params={"from": "2030-01-01T00:00:00"})

    assert response.status_code == 422
