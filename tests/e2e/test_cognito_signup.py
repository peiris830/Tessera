"""Sign-in and sign-up plumbing in the deployed shared stack (step 5b-2).

Checks the real user pool, app client, hosted login page and post-confirmation trigger.
No email is sent: the trigger is invoked directly with Cognito's event shape for a temporary
synthetic user (deleted afterwards). A real sign-up through the login page is tried by hand
in 5b-3.
"""

import json
import uuid
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from synthetic_users import PlatformConfig

CALLBACK = "http://localhost:5173/auth/callback"


@pytest.fixture(scope="module")
def hosted_ui_url(ssm: Any, config: PlatformConfig) -> str:
    try:
        name = f"/tessera/{config.env}/cognito/hosted-ui-url"
        return ssm.get_parameter(Name=name)["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        pytest.skip("hosted UI not deployed yet (step 5b-2)")


def authorize(hosted_ui_url: str, config: PlatformConfig, redirect_uri: str) -> httpx.Response:
    """The first request of the browser sign-in flow (no redirects followed)."""
    params = {
        "client_id": config.app_client_id,
        "response_type": "code",
        "scope": "openid email",
        "redirect_uri": redirect_uri,
        "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM",  # RFC 7636 example
        "code_challenge_method": "S256",
    }
    return httpx.get(f"{hosted_ui_url}/oauth2/authorize", params=params, timeout=15)


def test_pool_allows_self_sign_up_with_the_trigger_attached(cognito: Any, config: PlatformConfig):
    pool = cognito.describe_user_pool(UserPoolId=config.user_pool_id)["UserPool"]

    assert pool["AdminCreateUserConfig"]["AllowAdminCreateUserOnly"] is False
    trigger_arn = pool["LambdaConfig"]["PostConfirmation"]
    assert trigger_arn.endswith(f":function:tessera-{config.env}-post-confirmation")


def test_app_client_uses_only_the_code_flow(cognito: Any, config: PlatformConfig):
    client = cognito.describe_user_pool_client(
        UserPoolId=config.user_pool_id, ClientId=config.app_client_id
    )["UserPoolClient"]

    assert client["AllowedOAuthFlows"] == ["code"]
    assert set(client["AllowedOAuthScopes"]) == {"openid", "email"}
    assert CALLBACK in client["CallbackURLs"]


def test_login_page_starts_sign_in_for_a_listed_callback(hosted_ui_url, config):
    response = authorize(hosted_ui_url, config, CALLBACK)

    assert response.status_code == 302
    assert "/login" in response.headers["location"]


def test_login_page_refuses_an_unlisted_callback(hosted_ui_url, config):
    """Stops an attacker's site receiving sign-in codes."""
    response = authorize(hosted_ui_url, config, "https://evil.example/callback")

    assert "redirect_mismatch" in response.headers.get("location", response.text)


@pytest.fixture
def unconfirmed_user(cognito: Any, config: PlatformConfig) -> Iterator[str]:
    """A temporary synthetic user with no groups; deleted afterwards. No email is sent."""
    email = f"signup-e2e-{uuid.uuid4().hex[:8]}@example.com"
    user = cognito.admin_create_user(
        UserPoolId=config.user_pool_id,
        Username=email,
        UserAttributes=[{"Name": "email", "Value": email}],
        MessageAction="SUPPRESS",
    )["User"]
    try:
        yield user["Username"]  # Cognito's generated ID (we sign in by email)
    finally:
        cognito.admin_delete_user(UserPoolId=config.user_pool_id, Username=email)


def test_trigger_makes_a_confirmed_sign_up_an_attendee(
    aws: Any, cognito: Any, config: PlatformConfig, unconfirmed_user: str
):
    event = {
        "version": "1",
        "triggerSource": "PostConfirmation_ConfirmSignUp",
        "region": aws.region_name,
        "userPoolId": config.user_pool_id,
        "userName": unconfirmed_user,
        "request": {"userAttributes": {}},
        "response": {},
    }
    result = aws.client("lambda").invoke(
        FunctionName=f"tessera-{config.env}-post-confirmation", Payload=json.dumps(event)
    )
    assert "FunctionError" not in result, result["Payload"].read()

    groups = cognito.admin_list_groups_for_user(
        UserPoolId=config.user_pool_id, Username=unconfirmed_user
    )["Groups"]
    assert [g["GroupName"] for g in groups] == ["attendee"]
