from app.main import create_app
from scripts.export_openapi import SPEC_PATH, render_spec


def test_committed_spec_matches_the_code():
    assert SPEC_PATH.read_text(encoding="utf-8") == render_spec(), (
        "openapi.yaml is out of date: run `python scripts/export_openapi.py` and commit it"
    )


def test_protected_operations_require_jwt_and_health_does_not():
    spec = create_app().openapi()

    assert spec["paths"]["/v1/health"]["get"].get("security") is None
    for path, operations in spec["paths"].items():
        if path != "/v1/health":
            for operation in operations.values():
                assert operation["security"] == [{"cognitoJwt": []}], path


def test_error_responses_document_the_real_error_body():
    spec = create_app().openapi()
    responses = spec["paths"]["/v1/events/{event_id}"]["patch"]["responses"]

    for status in ("401", "403", "404", "409", "422"):
        schema_ref = responses[status]["content"]["application/json"]["schema"]["$ref"]
        assert schema_ref.endswith("/ErrorResponse")
    assert "HTTPValidationError" not in str(spec)  # FastAPI's default 422 shape isn't ours
