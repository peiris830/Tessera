import json
import logging

from pydantic import BaseModel

from app.correlation import HEADER, set_correlation_id
from app.errors import APIError
from app.logging_config import JsonFormatter


def assert_error_body(response, status, code):
    assert response.status_code == status
    error = response.json()["error"]
    assert error["code"] == code
    assert error["message"]
    # The body's correlation ID matches the response header, so a user can quote it.
    assert error["correlationId"] == response.headers[HEADER]


def test_unknown_route_returns_404_error_body(client):
    assert_error_body(client.get("/v1/nope"), 404, "NOT_FOUND")


def test_wrong_method_returns_405_error_body(client):
    assert_error_body(client.post("/v1/health"), 405, "METHOD_NOT_ALLOWED")


def test_api_error_uses_its_own_code(app, client):
    @app.get("/v1/test-api-error")
    def _():
        raise APIError(409, "SOLD_OUT", "No places left")

    assert_error_body(client.get("/v1/test-api-error"), 409, "SOLD_OUT")


def test_validation_error_returns_422_error_body(app, client):
    class Body(BaseModel):
        name: str

    @app.post("/v1/test-validation")
    def _(body: Body):
        return body

    response = client.post("/v1/test-validation", json={})

    assert_error_body(response, 422, "VALIDATION_ERROR")
    assert "name" in response.json()["error"]["message"]


def test_unhandled_exception_returns_500_without_leaking_details(app, client):
    @app.get("/v1/test-crash")
    def _():
        raise RuntimeError("secret internal detail")

    response = client.get("/v1/test-crash")

    assert_error_body(response, 500, "INTERNAL_ERROR")
    assert "secret internal detail" not in response.text


def test_log_lines_are_json_with_correlation_id_and_extras():
    set_correlation_id("corr-42")
    record = logging.LogRecord("catalogue", logging.INFO, __file__, 1, "hello", None, None)
    record.eventId = "evt-1"  # what `extra={"eventId": ...}` does

    line = json.loads(JsonFormatter("catalogue").format(record))

    assert line["message"] == "hello"
    assert line["service"] == "catalogue"
    assert line["correlationId"] == "corr-42"
    assert line["eventId"] == "evt-1"
