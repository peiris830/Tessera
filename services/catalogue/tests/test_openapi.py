from app.main import PUBLIC_OPERATIONS, create_app
from scripts.export_openapi import SPEC_PATH, render_spec


def test_committed_spec_matches_the_code():
    assert SPEC_PATH.read_text(encoding="utf-8") == render_spec(), (
        "openapi.yaml is out of date: run `python scripts/export_openapi.py` and commit it"
    )


def test_only_public_reads_skip_jwt_in_the_spec():
    spec = create_app().openapi()

    for path, operations in spec["paths"].items():
        for method, operation in operations.items():
            if (method.upper(), path) in PUBLIC_OPERATIONS:
                assert operation.get("security") is None, (method, path)
            else:
                assert operation["security"] == [{"cognitoJwt": []}], (method, path)
    assert spec["paths"]["/v1/events"]["post"]["security"]  # same path, protected method


def test_error_responses_document_the_real_error_body():
    spec = create_app().openapi()
    responses = spec["paths"]["/v1/events/{event_id}"]["patch"]["responses"]

    for status in ("401", "403", "404", "409", "422"):
        schema_ref = responses[status]["content"]["application/json"]["schema"]["$ref"]
        assert schema_ref.endswith("/ErrorResponse")
    assert "HTTPValidationError" not in str(spec)  # FastAPI's default 422 shape isn't ours
