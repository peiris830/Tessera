"""Extracting the caller from API Gateway's JWT claims."""

import pytest

from app.auth import Caller, caller_from_event


def event_with_claims(claims) -> dict:
    return {"requestContext": {"authorizer": {"jwt": {"claims": claims, "scopes": None}}}}


@pytest.mark.parametrize(
    ("raw_groups", "expected"),
    [
        ("[organiser attendee]", {"organiser", "attendee"}),  # how HTTP API actually sends it
        ("[organiser]", {"organiser"}),
        ("organiser,attendee", {"organiser", "attendee"}),
        (["organiser", "venue_staff"], {"organiser", "venue_staff"}),  # a real JSON list
        ("[]", set()),
        (None, set()),
    ],
)
def test_parses_groups_in_every_format(raw_groups, expected):
    claims = {"sub": "user-1"}
    if raw_groups is not None:
        claims["cognito:groups"] = raw_groups

    caller = caller_from_event(event_with_claims(claims))

    assert caller == Caller(user_id="user-1", groups=frozenset(expected))


@pytest.mark.parametrize(
    "event",
    [
        None,
        {},
        {"requestContext": {}},  # no authorizer: route wasn't protected
        event_with_claims("not-a-dict"),
        event_with_claims({"cognito:groups": "[organiser]"}),  # no sub
        event_with_claims({"sub": ""}),
        event_with_claims({"sub": 123}),
    ],
)
def test_missing_or_malformed_claims_give_no_caller(event):
    assert caller_from_event(event) is None


def test_unauthenticated_request_to_protected_route_gets_401(client, act_as):
    act_as(None)

    response = client.get("/v1/organisers/me/events")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"


def test_identity_header_from_client_is_ignored(client, act_as):
    """Only API Gateway's verified claims count; headers are client-controlled."""
    act_as(None)

    response = client.get(
        "/v1/organisers/me/events", headers={"X-User-Id": "org-0001", "Authorization": "x"}
    )

    assert response.status_code == 401


def test_browsing_needs_no_identity(client, act_as):
    act_as(None)

    assert client.get("/v1/events").status_code == 200
