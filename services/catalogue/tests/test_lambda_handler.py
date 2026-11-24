"""Invoke the Lambda entry point the way API Gateway (HTTP API, payload format 2.0) does.

On AWS, Lambda doesn't receive an HTTP request: API Gateway calls `handler(event, context)`
with a JSON event like the one below, and expects a JSON dict back. Mangum does the
translation in both directions.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest

from app.dependencies import get_repository
from app.main import app as lambda_app
from app.main import handler


def http_api_event(
    method: str,
    path: str,
    headers: dict[str, str] | None = None,
    claims: dict | None = None,
    body: dict | None = None,
) -> dict:
    event = {
        "version": "2.0",
        "routeKey": f"{method} {path}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "abc123.execute-api.eu-west-1.amazonaws.com", **(headers or {})},
        "requestContext": {
            "accountId": "123456789012",
            "apiId": "abc123",
            "domainName": "abc123.execute-api.eu-west-1.amazonaws.com",
            "http": {
                "method": method,
                "path": path,
                "protocol": "HTTP/1.1",
                "sourceIp": "203.0.113.10",
                "userAgent": "pytest",
            },
            "requestId": "req-1",
            "routeKey": f"{method} {path}",
            "stage": "$default",
            "time": "23/Nov/2026:10:00:00 +0000",
            "timeEpoch": 1795428000000,
        },
        "isBase64Encoded": False,
    }
    if claims is not None:
        # What API Gateway's JWT authorizer adds after verifying the token.
        event["requestContext"]["authorizer"] = {"jwt": {"claims": claims, "scopes": None}}
    if body is not None:
        event["body"] = json.dumps(body)
        event["headers"]["content-type"] = "application/json"
    return event


@pytest.fixture
def lambda_repo(repo):
    """Point the real module-level app (the one `handler` serves) at the moto table."""
    lambda_app.dependency_overrides[get_repository] = lambda: repo
    yield repo
    lambda_app.dependency_overrides.clear()


def create_body() -> dict:
    starts = (datetime.now(UTC) + timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "title": "Via Lambda",
        "venue": {"name": "Hall", "city": "Town"},
        "startsAt": starts,
        "capacity": 10,
    }


def test_claims_from_authorizer_identify_the_organiser(lambda_repo):
    # Groups arrive flattened to a string, exactly as HTTP API sends them.
    claims = {"sub": "org-0001", "cognito:groups": "[organiser]"}
    event = http_api_event("POST", "/v1/events", claims=claims, body=create_body())

    result = handler(event, None)

    assert result["statusCode"] == 201
    created = lambda_repo.get(json.loads(result["body"])["eventId"])
    assert created.organiser_id == "org-0001"


def test_attendee_claims_are_forbidden_from_creating(lambda_repo):
    claims = {"sub": "att-0001", "cognito:groups": "[attendee]"}
    event = http_api_event("POST", "/v1/events", claims=claims, body=create_body())

    assert handler(event, None)["statusCode"] == 403


def test_event_without_authorizer_claims_is_unauthenticated(lambda_repo):
    event = http_api_event("GET", "/v1/events")

    assert handler(event, None)["statusCode"] == 401


def test_lambda_handler_serves_health_check():
    event = http_api_event("GET", "/v1/health", {"x-correlation-id": "lambda-test-1"})

    result = handler(event, None)

    assert result["statusCode"] == 200
    assert json.loads(result["body"]) == {"status": "ok", "service": "catalogue"}
    assert result["headers"]["x-correlation-id"] == "lambda-test-1"
