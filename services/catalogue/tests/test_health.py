import uuid

from app.correlation import HEADER


def test_health_returns_ok(client):
    response = client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "catalogue"}


def test_generates_correlation_id_when_missing(client):
    response = client.get("/v1/health")

    uuid.UUID(response.headers[HEADER])  # raises if not a valid UUID


def test_propagates_valid_incoming_correlation_id(client):
    response = client.get("/v1/health", headers={HEADER: "abc-123"})

    assert response.headers[HEADER] == "abc-123"


def test_replaces_malformed_correlation_id(client):
    for bad in ["has spaces", "x" * 200, "semi;colon"]:
        response = client.get("/v1/health", headers={HEADER: bad})

        assert response.headers[HEADER] != bad
        uuid.UUID(response.headers[HEADER])
