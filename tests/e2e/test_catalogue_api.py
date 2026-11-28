"""Smoke tests for the deployed Catalogue API, with real Cognito tokens.

Covers the path unit tests can't: API Gateway's JWT authorizer, the real token claims reaching
the Lambda, IAM permissions on the real table, and ownership/visibility rules end to end.
Events created here are deleted from DynamoDB afterwards (dev only).
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Any

import httpx
import pytest
from synthetic_users import PlatformConfig, sign_in


@pytest.fixture(scope="module")
def api_url(ssm: Any, config: PlatformConfig) -> str:
    try:
        return ssm.get_parameter(Name=f"/tessera/{config.env}/catalogue/api-url")["Parameter"][
            "Value"
        ]
    except ssm.exceptions.ParameterNotFound:
        pytest.skip(f"Catalogue not deployed (no /tessera/{config.env}/catalogue/api-url)")


@pytest.fixture(scope="module")
def http(api_url: str) -> Iterator[httpx.Client]:
    with httpx.Client(base_url=api_url, timeout=15) as client:
        yield client


@pytest.fixture(scope="module")
def token(cognito: Any, config: PlatformConfig, password: str):
    @cache
    def access_token(email: str) -> str:
        return sign_in(cognito, config, email, password)["AccessToken"]

    return access_token


@pytest.fixture(scope="module")
def as_user(token):
    def headers(email: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token(email)}"}

    return headers


@pytest.fixture(scope="module")
def created_events(aws: Any, config: PlatformConfig) -> Iterator[list[str]]:
    """Collects IDs of events the tests create, then deletes them from the table."""
    ids: list[str] = []
    yield ids
    table = aws.resource("dynamodb").Table(f"tessera-{config.env}-catalogue-events")
    for event_id in ids:
        table.delete_item(Key={"eventId": event_id})


def new_event_body() -> dict[str, Any]:
    starts = (datetime.now(UTC) + timedelta(days=30)).replace(microsecond=0)
    return {
        "title": "[e2e] Smoke test concert",
        "description": "Created by tests/e2e; deleted afterwards.",
        "venue": {"name": "Test Hall", "city": "Testville"},
        "startsAt": starts.isoformat(),
        "capacity": 100,
    }


# ---------------------------------------------------------------- edge and identity


def test_health_is_public(http: httpx.Client):
    response = http.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "catalogue"}
    assert response.headers["x-correlation-id"]


def test_missing_token_is_rejected_by_api_gateway(http: httpx.Client):
    response = http.get("/v1/events")
    assert response.status_code == 401
    # API Gateway's own body, not ours: HTTP APIs can't customise authorizer responses.
    assert response.json() == {"message": "Unauthorized"}


def test_forged_token_is_rejected(http: httpx.Client):
    response = http.get("/v1/events", headers={"Authorization": "Bearer not.a.jwt"})
    assert response.status_code == 401


def test_correlation_id_is_propagated(http: httpx.Client, as_user):
    response = http.get(
        "/v1/events",
        headers={**as_user("attendee1@example.com"), "X-Correlation-Id": "e2e-check-123"},
    )
    assert response.status_code == 200
    assert response.headers["x-correlation-id"] == "e2e-check-123"


# ---------------------------------------------------------------- roles and ownership


def test_attendee_cannot_create_events(http: httpx.Client, as_user):
    response = http.post(
        "/v1/events", json=new_event_body(), headers=as_user("attendee1@example.com")
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_event_lifecycle_and_visibility(http: httpx.Client, as_user, created_events: list[str]):
    owner = as_user("organiser1@example.com")
    other = as_user("organiser2@example.com")
    attendee = as_user("attendee1@example.com")

    # Organiser creates a DRAFT (writes to the real table through the Lambda's IAM role).
    created = http.post("/v1/events", json=new_event_body(), headers=owner)
    assert created.status_code == 201, created.text
    event = created.json()
    created_events.append(event["eventId"])
    assert event["status"] == "DRAFT"
    assert created.headers["location"] == f"/v1/events/{event['eventId']}"
    path = f"/v1/events/{event['eventId']}"

    # Drafts are invisible to everyone but the owner.
    assert http.get(path, headers=owner).status_code == 200
    assert http.get(path, headers=attendee).status_code == 404
    assert http.patch(path, json={"title": "Hijacked"}, headers=other).status_code == 404

    # Publish; now everyone can see it, but only the owner can change it.
    published = http.post(f"{path}/publish", headers=owner)
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "PUBLISHED"
    assert http.get(path, headers=attendee).json()["status"] == "PUBLISHED"

    hijack = http.patch(path, json={"title": "Hijacked"}, headers=other)
    assert hijack.status_code == 403
    assert hijack.json()["error"]["code"] == "NOT_EVENT_OWNER"

    # It shows up when an attendee browses (follow pages until found).
    assert _browse_contains(http, attendee, event["eventId"])

    # The owner's own list includes it (by-organiser index); the other organiser's doesn't.
    mine = http.get("/v1/organisers/me/events", headers=owner).json()["items"]
    theirs = http.get("/v1/organisers/me/events", headers=other).json()["items"]
    assert event["eventId"] in {e["eventId"] for e in mine}
    assert event["eventId"] not in {e["eventId"] for e in theirs}


def _browse_contains(http: httpx.Client, headers: dict[str, str], event_id: str) -> bool:
    params: dict[str, Any] = {"limit": 100}
    for _ in range(10):
        page = http.get("/v1/events", params=params, headers=headers)
        assert page.status_code == 200, page.text
        body = page.json()
        if event_id in {e["eventId"] for e in body["items"]}:
            return True
        if not body.get("nextToken"):
            return False
        params["nextToken"] = body["nextToken"]
    return False
