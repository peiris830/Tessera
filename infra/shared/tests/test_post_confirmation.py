"""Runs the post-confirmation trigger's inline code (exactly what template.yaml deploys).

boto3 is replaced by a fake module, so these tests need no AWS access or credentials.
"""

import sys
import types
from typing import Any
from unittest.mock import MagicMock

import pytest
from test_template import props


@pytest.fixture
def trigger(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, MagicMock]:
    cognito = MagicMock()
    fake_boto3 = types.ModuleType("boto3")
    fake_boto3.client = lambda service: cognito  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "boto3", fake_boto3)

    module = types.ModuleType("post_confirmation")
    exec(props("PostConfirmationFunction")["InlineCode"], module.__dict__)
    return module, cognito


def event(trigger_source: str) -> dict[str, Any]:
    """The shape Cognito sends (trimmed to what the code reads, plus realistic extras)."""
    return {
        "version": "1",
        "triggerSource": trigger_source,
        "region": "us-east-1",
        "userPoolId": "us-east-1_TestPool",
        "userName": "0f1e2d3c-aaaa-bbbb-cccc-1234567890ab",
        "request": {"userAttributes": {"email": "someone@example.com"}},
        "response": {},
    }


def test_confirmed_sign_up_joins_the_attendee_group(trigger):
    module, cognito = trigger
    incoming = event("PostConfirmation_ConfirmSignUp")

    result = module.handler(incoming, None)

    cognito.admin_add_user_to_group.assert_called_once_with(
        UserPoolId="us-east-1_TestPool",
        Username="0f1e2d3c-aaaa-bbbb-cccc-1234567890ab",
        GroupName="attendee",
    )
    assert result is incoming  # Cognito requires the event back


def test_password_reset_confirmation_changes_nothing(trigger):
    module, cognito = trigger

    module.handler(event("PostConfirmation_ConfirmForgotPassword"), None)

    cognito.admin_add_user_to_group.assert_not_called()


def test_email_is_never_logged(trigger, caplog: pytest.LogCaptureFixture):
    module, _ = trigger

    with caplog.at_level("INFO"):
        module.handler(event("PostConfirmation_ConfirmSignUp"), None)

    assert "someone@example.com" not in caplog.text
    assert "0f1e2d3c-aaaa-bbbb-cccc-1234567890ab" in caplog.text
