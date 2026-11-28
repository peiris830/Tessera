"""Policy-as-tests for template.yaml: security and cost rules that must not regress."""

import importlib

from app.repository import BY_ORGANISER, BY_STATUS_START
from tests.cfn import load_template, resource

# Exactly the DynamoDB calls app/repository.py makes. If the code starts needing another
# action, this test fails until the IAM policy is updated deliberately.
EXPECTED_DYNAMODB_ACTIONS = {
    "dynamodb:GetItem",
    "dynamodb:PutItem",
    "dynamodb:UpdateItem",
    "dynamodb:Query",
}


def function_props() -> dict:
    return resource("CatalogueFunction")["Properties"]


def policy_statements() -> list[dict]:
    return [s for policy in function_props()["Policies"] for s in policy["Statement"]]


def test_function_policy_is_least_privilege():
    statements = policy_statements()
    actions = {a for s in statements for a in s["Action"]}

    assert actions == EXPECTED_DYNAMODB_ACTIONS
    for statement in statements:
        assert statement["Effect"] == "Allow"
        assert "*" not in statement["Action"]
        assert statement["Resource"] != "*"  # always scoped to our table


def test_query_is_the_only_action_on_indexes():
    by_resource = {str(s["Resource"]): set(s["Action"]) for s in policy_statements()}
    index_actions = [actions for res, actions in by_resource.items() if "/index/" in res]

    assert index_actions == [{"dynamodb:Query"}]


def test_handler_setting_points_at_real_lambda_entry_point():
    module_name, attr = function_props()["Handler"].rsplit(".", 1)

    assert function_props()["CodeUri"] == "src/"
    assert callable(getattr(importlib.import_module(module_name), attr))
    assert function_props()["Runtime"] == "python3.12"


def test_table_indexes_match_repository_constants():
    indexes = {
        i["IndexName"] for i in resource("EventsTable")["Properties"]["GlobalSecondaryIndexes"]
    }

    assert indexes == {BY_STATUS_START, BY_ORGANISER}


def test_table_is_on_demand_with_point_in_time_recovery():
    props = resource("EventsTable")["Properties"]

    assert props["BillingMode"] == "PAY_PER_REQUEST"
    assert props["PointInTimeRecoverySpecification"]["PointInTimeRecoveryEnabled"] is True


def test_every_log_group_has_a_retention_limit():
    log_groups = [
        r for r in load_template()["Resources"].values() if r["Type"] == "AWS::Logs::LogGroup"
    ]

    assert len(log_groups) == 2
    assert all("RetentionInDays" in g["Properties"] for g in log_groups)


def test_api_requires_jwt_by_default_and_only_read_routes_are_public():
    api = resource("CatalogueApi")["Properties"]
    events = function_props()["Events"]
    public = {
        (e["Properties"]["Method"], e["Properties"]["Path"])
        for e in events.values()
        if e["Properties"].get("Auth", {}).get("Authorizer") == "NONE"
    }

    assert api["Auth"]["DefaultAuthorizer"] == "CognitoJwt"
    # Exactly these: GET reads plus the CORS preflight. Every write goes through the JWT
    # authorizer (OPTIONS is answered with an empty 204 and never reaches a handler).
    assert public == {
        ("GET", "/v1/health"),
        ("GET", "/v1/events"),
        ("GET", "/v1/events/{eventId}"),
        ("OPTIONS", "/v1/{proxy+}"),
    }
    assert events["Api"]["Properties"].get("Auth") is None  # catch-all uses the default


def test_public_routes_match_the_apps_public_operations():
    from app.main import PUBLIC_OPERATIONS

    template_paths = {
        (e["Properties"]["Method"], e["Properties"]["Path"].replace("{eventId}", "{event_id}"))
        for e in function_props()["Events"].values()
        if e["Properties"].get("Auth", {}).get("Authorizer") == "NONE"
        and e["Properties"]["Method"] != "OPTIONS"  # preflight isn't an API operation
    }
    assert template_paths == PUBLIC_OPERATIONS


def test_cors_allows_only_listed_origins_and_needed_headers():
    cors = resource("CatalogueApi")["Properties"]["CorsConfiguration"]
    origins_param = load_template()["Parameters"]["AllowedOrigins"]

    assert cors["AllowOrigins"] == {"!Ref": "AllowedOrigins"}
    assert "*" not in origins_param["Default"]
    assert origins_param["Default"] == "http://localhost:5173"
    assert set(cors["AllowHeaders"]) == {"authorization", "content-type", "x-correlation-id"}
    assert "x-correlation-id" in cors["ExposeHeaders"]
    assert cors["AllowCredentials"] is False


def test_api_is_throttled():
    settings = resource("CatalogueApi")["Properties"]["DefaultRouteSettings"]

    assert settings["ThrottlingRateLimit"] > 0
    assert settings["ThrottlingBurstLimit"] > 0


def test_access_log_format_contains_no_ip_or_user_identity():
    log_format = resource("CatalogueApi")["Properties"]["AccessLogSettings"]["Format"]

    for forbidden in ("sourceIp", "identity", "claims", "principalId"):
        assert forbidden not in log_format
