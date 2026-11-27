"""Real Cognito tokens have exactly what the services' JWT authorizers will check.

API Gateway verifies a token's signature with the pool's public keys (JWKS), then checks the
issuer (`iss`), the audience (`client_id` in access tokens) and expiry. These tests do the same
against the deployed pool, so a wrong SSM value (like the https://https:// issuer from the
first shared-stack deploy) fails here instead of as a mysterious 401 later.
"""

from typing import Any

import jwt
import pytest
from botocore.exceptions import ClientError
from synthetic_users import USERS, PlatformConfig, SyntheticUser, sign_in


@pytest.fixture(scope="module")
def jwks(config: PlatformConfig) -> jwt.PyJWKClient:
    # The pool publishes its public signing keys here; the URL is derived from the issuer.
    return jwt.PyJWKClient(f"{config.issuer_url}/.well-known/jwks.json")


def verify(token: str, jwks: jwt.PyJWKClient, config: PlatformConfig, **kwargs: Any) -> dict:
    key = jwks.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        key.key,
        algorithms=["RS256"],
        issuer=config.issuer_url,  # must equal the SSM issuer-url exactly
        options={"require": ["exp", "iat", "iss", "sub", "token_use"]},
        **kwargs,
    )


@pytest.mark.parametrize("user", USERS, ids=lambda u: u.email)
def test_access_token_carries_identity_and_group(
    user: SyntheticUser, cognito: Any, config: PlatformConfig, password: str, jwks
):
    tokens = sign_in(cognito, config, user.email, password)
    claims = verify(tokens["AccessToken"], jwks, config)

    assert claims["token_use"] == "access"
    assert claims["client_id"] == config.app_client_id  # the audience the authorizer checks
    assert claims["cognito:groups"] == [user.group]


def test_id_token_audience_is_the_app_client(
    cognito: Any, config: PlatformConfig, password: str, jwks
):
    user = USERS[0]
    tokens = sign_in(cognito, config, user.email, password)
    claims = verify(tokens["IdToken"], jwks, config, audience=config.app_client_id)

    assert claims["token_use"] == "id"
    assert claims["email"] == user.email


def test_each_user_has_a_distinct_stable_id(cognito: Any, config: PlatformConfig, password: str):
    subs = {
        jwt.decode(
            sign_in(cognito, config, u.email, password)["AccessToken"],
            options={"verify_signature": False},  # only reading `sub`; verified above
        )["sub"]
        for u in USERS
    }
    assert len(subs) == len(USERS)


def test_wrong_password_is_rejected(cognito: Any, config: PlatformConfig):
    with pytest.raises(ClientError) as exc:
        sign_in(cognito, config, USERS[0].email, "Definitely-not-the-password-1")
    assert exc.value.response["Error"]["Code"] == "NotAuthorizedException"


def test_unknown_user_gets_the_same_error_as_wrong_password(cognito: Any, config: PlatformConfig):
    # PreventUserExistenceErrors: nobody can probe which emails have accounts.
    with pytest.raises(ClientError) as exc:
        sign_in(cognito, config, "nobody@example.com", "Definitely-not-the-password-1")
    assert exc.value.response["Error"]["Code"] == "NotAuthorizedException"


def test_plain_password_flow_is_disabled(cognito: Any, config: PlatformConfig, password: str):
    # USER_PASSWORD_AUTH (password sent by a public client) is deliberately not enabled.
    with pytest.raises(ClientError) as exc:
        cognito.initiate_auth(
            ClientId=config.app_client_id,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": USERS[0].email, "PASSWORD": password},
        )
    assert exc.value.response["Error"]["Code"] == "InvalidParameterException"
