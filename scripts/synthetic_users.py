"""Synthetic test users, shared by seed_users.py and the end-to-end tests.

All addresses use example.com, a domain reserved for documentation, so no real person can
receive mail or be identified. The one shared password is random and lives only in SSM
Parameter Store as an encrypted SecureString: never in the repo, a file or shell history.
"""

import secrets
import string
from dataclasses import dataclass
from typing import Any

from botocore.exceptions import ClientError


@dataclass(frozen=True)
class SyntheticUser:
    email: str
    group: str


USERS = (
    SyntheticUser("attendee1@example.com", "attendee"),
    SyntheticUser("attendee2@example.com", "attendee"),  # "someone else's reservation" cases
    SyntheticUser("organiser1@example.com", "organiser"),
    SyntheticUser("organiser2@example.com", "organiser"),  # "not your event" cases
    SyntheticUser("staff1@example.com", "venue_staff"),
)


@dataclass(frozen=True)
class PlatformConfig:
    env: str
    user_pool_id: str
    app_client_id: str
    issuer_url: str


def password_parameter(env: str) -> str:
    return f"/tessera/{env}/test-users/password"


def load_config(ssm: Any, env: str) -> PlatformConfig:
    """Read the shared stack's SSM parameters (ADR 0002)."""
    names = {
        "user_pool_id": f"/tessera/{env}/cognito/user-pool-id",
        "app_client_id": f"/tessera/{env}/cognito/app-client-id",
        "issuer_url": f"/tessera/{env}/cognito/issuer-url",
    }
    response = ssm.get_parameters(Names=list(names.values()))
    if response["InvalidParameters"]:
        raise SystemExit(
            f"Missing SSM parameters {response['InvalidParameters']}: "
            f"is the shared stack (tessera-{env}-shared) deployed in this region?"
        )
    values = {p["Name"]: p["Value"] for p in response["Parameters"]}
    return PlatformConfig(env=env, **{field: values[name] for field, name in names.items()})


def generate_password(length: int = 24) -> str:
    """Random password meeting the pool policy (12+ chars, lower, upper, digit)."""
    alphabet = string.ascii_letters + string.digits
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in candidate)
            and any(c.isupper() for c in candidate)
            and any(c.isdigit() for c in candidate)
        ):
            return candidate


def get_password(ssm: Any, env: str) -> str | None:
    try:
        response = ssm.get_parameter(Name=password_parameter(env), WithDecryption=True)
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ParameterNotFound":
            return None
        raise
    return response["Parameter"]["Value"]


def create_password(ssm: Any, env: str) -> str:
    password = generate_password()
    ssm.put_parameter(
        Name=password_parameter(env),
        Value=password,
        # SecureString: encrypted at rest with the AWS-managed aws/ssm KMS key (free).
        Type="SecureString",
        Description="Password of the synthetic Tessera test users (created by seed_users.py)",
        Tags=[{"Key": "project", "Value": "tessera"}, {"Key": "env", "Value": env}],
    )
    return password


def sign_in(cognito: Any, config: PlatformConfig, email: str, password: str) -> dict[str, Any]:
    """Admin password sign-in: needs AWS credentials, so only scripts/tests can use it."""
    response = cognito.admin_initiate_auth(
        UserPoolId=config.user_pool_id,
        ClientId=config.app_client_id,
        AuthFlow="ADMIN_USER_PASSWORD_AUTH",
        AuthParameters={"USERNAME": email, "PASSWORD": password},
    )
    return response["AuthenticationResult"]  # AccessToken, IdToken, RefreshToken, ExpiresIn
