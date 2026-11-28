"""Policy-as-tests for the shared stack: identity settings, the SSM contract, tagging.

These run locally in milliseconds and fail before a bad change ever reaches AWS.
"""

from functools import cache
from pathlib import Path
from typing import Any

import pytest
import yaml

TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "template.yaml"

# The contract from ADR 0002: service templates read exactly these names.
EXPECTED_SSM_PARAMETERS = {
    "/tessera/${Env}/cognito/user-pool-id",
    "/tessera/${Env}/cognito/app-client-id",
    "/tessera/${Env}/cognito/issuer-url",
    "/tessera/${Env}/cognito/hosted-ui-url",  # read by scripts/frontend-env.ps1
    "/tessera/${Env}/eventbridge/bus-name",
    "/tessera/${Env}/artifacts/bucket-name",  # read by scripts/deploy.ps1
}


class _CfnLoader(yaml.SafeLoader):
    """SafeLoader that keeps CloudFormation tags, e.g. `!Ref X` -> {"!Ref": "X"}."""


def _construct_tag(loader: yaml.SafeLoader, suffix: str, node: yaml.Node) -> dict[str, Any]:
    if isinstance(node, yaml.ScalarNode):
        value: Any = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    return {f"!{suffix}": value}


_CfnLoader.add_multi_constructor("!", _construct_tag)


@cache
def template() -> dict[str, Any]:
    return yaml.load(TEMPLATE_PATH.read_text(encoding="utf-8"), Loader=_CfnLoader)


def resources_of_type(cfn_type: str) -> dict[str, dict[str, Any]]:
    return {k: v for k, v in template()["Resources"].items() if v["Type"] == cfn_type}


def props(logical_id: str) -> dict[str, Any]:
    return template()["Resources"][logical_id]["Properties"]


# ---------------------------------------------------------------- user pool


def test_self_sign_up_requires_email_verification_with_free_sender():
    pool = props("UserPool")
    assert pool["AdminCreateUserConfig"]["AllowAdminCreateUserOnly"] is False  # hybrid rule
    assert pool["AutoVerifiedAttributes"] == ["email"]
    assert pool["EmailConfiguration"] == {"EmailSendingAccount": "COGNITO_DEFAULT"}
    assert "{####}" in pool["VerificationMessageTemplate"]["EmailMessage"]


def test_self_registered_users_become_attendees_via_post_confirmation_trigger():
    function = props("PostConfirmationFunction")
    (event,) = function["Events"].values()
    assert event == {
        "Type": "Cognito",
        "Properties": {"UserPool": {"!Ref": "UserPool"}, "Trigger": "PostConfirmation"},
    }
    assert 'GROUP = "attendee"' in function["InlineCode"]


def test_user_pool_uses_free_lite_tier():
    assert props("UserPool")["UserPoolTier"] == "LITE"


def test_password_policy_is_strong():
    policy = props("UserPool")["Policies"]["PasswordPolicy"]
    assert policy["MinimumLength"] >= 12
    assert policy["RequireLowercase"] and policy["RequireUppercase"] and policy["RequireNumbers"]


def test_mfa_available_without_sms_costs():
    pool = props("UserPool")
    assert pool["MfaConfiguration"] in {"OPTIONAL", "ON"}
    assert pool["EnabledMfas"] == ["SOFTWARE_TOKEN_MFA"]


def test_usernames_are_case_insensitive():
    assert props("UserPool")["UsernameConfiguration"]["CaseSensitive"] is False


def test_prod_user_pool_has_deletion_protection():
    assert props("UserPool")["DeletionProtection"] == {"!If": ["IsProd", "ACTIVE", "INACTIVE"]}


# ---------------------------------------------------------------- app client


def test_app_client_is_public_without_secret():
    assert props("AppClient")["GenerateSecret"] is False


def test_app_client_never_accepts_plain_password_from_browsers():
    flows = set(props("AppClient")["ExplicitAuthFlows"])
    assert flows == {
        "ALLOW_USER_SRP_AUTH",
        "ALLOW_ADMIN_USER_PASSWORD_AUTH",
        "ALLOW_REFRESH_TOKEN_AUTH",
    }
    assert "ALLOW_USER_PASSWORD_AUTH" not in flows


def test_app_client_hides_whether_a_user_exists():
    assert props("AppClient")["PreventUserExistenceErrors"] == "ENABLED"


def test_tokens_are_short_lived_and_revocable():
    client = props("AppClient")
    assert client["EnableTokenRevocation"] is True
    assert client["TokenValidityUnits"]["AccessToken"] == "minutes"
    assert client["AccessTokenValidity"] <= 60


def test_oauth_allows_only_the_code_flow_with_minimal_scopes():
    client = props("AppClient")
    assert client["AllowedOAuthFlowsUserPoolClient"] is True
    assert client["AllowedOAuthFlows"] == ["code"]  # never "implicit" (tokens in the URL)
    assert set(client["AllowedOAuthScopes"]) == {"openid", "email"}
    assert client["SupportedIdentityProviders"] == ["COGNITO"]


def test_redirect_urls_are_parameters_defaulting_to_the_dev_server():
    client = props("AppClient")
    params = template()["Parameters"]
    assert client["CallbackURLs"] == {"!Ref": "CallbackUrls"}
    assert client["LogoutURLs"] == {"!Ref": "LogoutUrls"}
    assert params["CallbackUrls"]["Default"] == "http://localhost:5173/auth/callback"
    assert params["LogoutUrls"]["Default"] == "http://localhost:5173/"
    for name in ("CallbackUrls", "LogoutUrls"):
        assert "*" not in params[name]["Default"]


# ---------------------------------------------------------------- hosted login page


def test_domain_prefix_is_derived_from_the_stack_id_and_uses_the_classic_ui():
    domain = props("UserPoolDomain")
    template_str, variables = domain["Domain"]["!Sub"]
    assert template_str == "tessera-${Env}-${Suffix}"
    assert "AWS::StackId" in str(variables["Suffix"])  # no account ID or name in the URL
    assert domain["ManagedLoginVersion"] == 1  # classic hosted UI: free on the Lite tier


def test_login_page_css_uses_only_cognito_customizable_classes():
    style = template()["Resources"]["LoginPageStyle"]
    assert style["DependsOn"] == "UserPoolDomain"
    selectors = [rule.split("{")[0].strip() for rule in style["Properties"]["CSS"].split("}")]
    for selector in filter(None, selectors):
        assert selector.split(":")[0].endswith("-customizable"), selector


# ---------------------------------------------------------------- sign-up trigger


def test_trigger_can_only_add_users_to_groups():
    (policy,) = props("PostConfirmationFunction")["Policies"]
    (statement,) = policy["Statement"]
    assert statement["Effect"] == "Allow"
    assert statement["Action"] == ["cognito-idp:AdminAddUserToGroup"]
    assert statement["Resource"] == {
        "!Sub": "arn:aws:cognito-idp:${AWS::Region}:${AWS::AccountId}:userpool/*"
    }


def test_trigger_is_small_fast_and_logs_with_retention():
    function = props("PostConfirmationFunction")
    assert function["MemorySize"] == 128
    assert function["Timeout"] <= 5  # Cognito gives triggers 5 seconds
    assert function["LoggingConfig"]["LogGroup"] == {"!Ref": "PostConfirmationLogGroup"}
    assert "RetentionInDays" in props("PostConfirmationLogGroup")


# ---------------------------------------------------------------- groups


def test_exactly_the_three_role_groups_exist():
    groups = resources_of_type("AWS::Cognito::UserPoolGroup").values()
    assert {g["Properties"]["GroupName"] for g in groups} == {
        "attendee",
        "organiser",
        "venue_staff",
    }
    assert all(g["Properties"]["UserPoolId"] == {"!Ref": "UserPool"} for g in groups)


# ---------------------------------------------------------------- SSM contract (ADR 0002)


def test_ssm_parameters_match_adr_0002_contract():
    names = {
        p["Properties"]["Name"]["!Sub"] for p in resources_of_type("AWS::SSM::Parameter").values()
    }
    assert names == EXPECTED_SSM_PARAMETERS


def test_ssm_parameters_are_free_standard_strings():
    for param in resources_of_type("AWS::SSM::Parameter").values():
        assert param["Properties"]["Type"] == "String"
        assert "Tier" not in param["Properties"]  # default tier is Standard (free)


def test_issuer_url_matches_cognito_token_iss():
    # ProviderURL already includes "https://"; prefixing it again produced https://https://...
    # in the first deploy, which every JWT authorizer would have rejected.
    issuer = {"!GetAtt": "UserPool.ProviderURL"}
    assert props("IssuerUrlParameter")["Value"] == issuer
    assert template()["Outputs"]["IssuerUrl"]["Value"] == issuer


def test_catalogue_reads_parameters_this_stack_writes():
    catalogue = (TEMPLATE_PATH.parents[2] / "services" / "catalogue" / "template.yaml").read_text(
        encoding="utf-8"
    )
    for name in ("cognito/issuer-url", "cognito/app-client-id"):
        assert f"/tessera/dev/{name}" in catalogue


# ---------------------------------------------------------------- artifacts bucket


def test_artifacts_bucket_name_is_unique_without_random_suffix():
    assert props("ArtifactsBucket")["BucketName"] == {
        "!Sub": "tessera-${Env}-artifacts-${AWS::AccountId}-${AWS::Region}"
    }


def test_artifacts_bucket_blocks_all_public_access():
    block = props("ArtifactsBucket")["PublicAccessBlockConfiguration"]
    assert block == {
        "BlockPublicAcls": True,
        "BlockPublicPolicy": True,
        "IgnorePublicAcls": True,
        "RestrictPublicBuckets": True,
    }
    rules = props("ArtifactsBucket")["OwnershipControls"]["Rules"]
    assert rules == [{"ObjectOwnership": "BucketOwnerEnforced"}]  # ACLs disabled


def test_artifacts_bucket_is_encrypted():
    config = props("ArtifactsBucket")["BucketEncryption"]["ServerSideEncryptionConfiguration"]
    assert config[0]["ServerSideEncryptionByDefault"]["SSEAlgorithm"] in {"AES256", "aws:kms"}


def test_old_artifacts_expire_but_not_before_rollback_could_need_them():
    (rule,) = props("ArtifactsBucket")["LifecycleConfiguration"]["Rules"]
    assert rule["Status"] == "Enabled"
    assert 60 <= rule["ExpirationInDays"] <= 365
    assert rule["AbortIncompleteMultipartUpload"]["DaysAfterInitiation"] <= 7


def test_artifacts_bucket_refuses_plain_http():
    policy = props("ArtifactsBucketPolicy")
    assert policy["Bucket"] == {"!Ref": "ArtifactsBucket"}
    (statement,) = policy["PolicyDocument"]["Statement"]
    assert statement["Effect"] == "Deny"
    assert statement["Principal"] == "*"
    assert statement["Condition"] == {"Bool": {"aws:SecureTransport": "false"}}
    assert {"!Sub": "${ArtifactsBucket.Arn}/*"} in statement["Resource"]


# ---------------------------------------------------------------- hygiene


def test_the_trigger_is_the_only_thing_needing_iam():
    """No hand-written IAM: the one role is SAM's, generated for the trigger function."""
    assert not [r for r in template()["Resources"].values() if r["Type"].startswith("AWS::IAM::")]
    functions = resources_of_type("AWS::Serverless::Function")
    assert set(functions) == {"PostConfirmationFunction"}


@pytest.mark.parametrize(
    ("logical_id", "tags_key"),
    [
        ("UserPool", "UserPoolTags"),
        ("EventBus", "Tags"),
        ("UserPoolIdParameter", "Tags"),
        ("AppClientIdParameter", "Tags"),
        ("IssuerUrlParameter", "Tags"),
        ("HostedUiUrlParameter", "Tags"),
        ("PostConfirmationFunction", "Tags"),
        ("EventBusNameParameter", "Tags"),
        ("ArtifactsBucket", "Tags"),
        ("ArtifactsBucketParameter", "Tags"),
    ],
)
def test_resources_are_tagged_for_cost_tracking(logical_id: str, tags_key: str):
    tags = props(logical_id)[tags_key]
    if isinstance(tags, list):  # EventBridge uses [{Key, Value}], others use a map
        tags = {t["Key"]: t["Value"] for t in tags}
    assert tags["project"] == "tessera"
    assert tags["env"] == {"!Ref": "Env"}
