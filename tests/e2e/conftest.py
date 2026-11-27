"""Fixtures for end-to-end tests against a deployed environment.

Needs AWS credentials (e.g. $env:AWS_PROFILE = "tessera-dev") and the synthetic users from
scripts/seed_users.py. TESSERA_ENV selects the environment (default: dev).
"""

import os
from typing import Any

import boto3
import pytest
from synthetic_users import PlatformConfig, get_password, load_config


@pytest.fixture(scope="session")
def aws() -> boto3.Session:
    session = boto3.Session()
    if session.get_credentials() is None:
        pytest.skip("no AWS credentials: set AWS_PROFILE (e.g. tessera-dev) and run aws login")
    return session


@pytest.fixture(scope="session")
def ssm(aws: boto3.Session) -> Any:
    return aws.client("ssm")


@pytest.fixture(scope="session")
def cognito(aws: boto3.Session) -> Any:
    return aws.client("cognito-idp")


@pytest.fixture(scope="session")
def config(ssm: Any) -> PlatformConfig:
    return load_config(ssm, os.environ.get("TESSERA_ENV", "dev"))


@pytest.fixture(scope="session")
def password(ssm: Any, config: PlatformConfig) -> str:
    value = get_password(ssm, config.env)
    if value is None:
        pytest.fail("test users not seeded: run python scripts/seed_users.py first")
    return value
