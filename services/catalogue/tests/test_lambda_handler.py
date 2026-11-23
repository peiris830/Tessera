"""Invoke the Lambda entry point the way API Gateway (HTTP API, payload format 2.0) does.

On AWS, Lambda doesn't receive an HTTP request: API Gateway calls `handler(event, context)`
with a JSON event like the one below, and expects a JSON dict back. Mangum does the
translation in both directions.
"""

import json

from app.main import handler


def http_api_event(method: str, path: str, headers: dict[str, str] | None = None) -> dict:
    return {
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


def test_lambda_handler_serves_health_check():
    event = http_api_event("GET", "/v1/health", {"x-correlation-id": "lambda-test-1"})

    result = handler(event, None)

    assert result["statusCode"] == 200
    assert json.loads(result["body"]) == {"status": "ok", "service": "catalogue"}
    assert result["headers"]["x-correlation-id"] == "lambda-test-1"
