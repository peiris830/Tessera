"""Create (or remove) the synthetic test users in the dev Cognito user pool.

    $env:AWS_PROFILE = "tessera-dev"
    python scripts/seed_users.py            # create/repair users; safe to re-run
    python scripts/seed_users.py --delete   # remove the users and the password parameter

Idempotent: re-running fixes passwords and group membership instead of failing. No emails
are sent (MessageAction=SUPPRESS), and the password is never printed.
"""

import argparse
from typing import Any

import boto3
from botocore.exceptions import ClientError
from synthetic_users import (
    USERS,
    SyntheticUser,
    create_password,
    get_password,
    load_config,
    password_parameter,
)


def ensure_user(cognito: Any, pool_id: str, user: SyntheticUser, password: str) -> str:
    try:
        cognito.admin_create_user(
            UserPoolId=pool_id,
            Username=user.email,
            UserAttributes=[
                {"Name": "email", "Value": user.email},
                {"Name": "email_verified", "Value": "true"},
            ],
            MessageAction="SUPPRESS",  # don't send an invitation email
        )
        outcome = "created"
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "UsernameExistsException":
            raise
        outcome = "exists"

    # Permanent=True skips the "must change password at first sign-in" state that
    # admin-created users otherwise start in.
    cognito.admin_set_user_password(
        UserPoolId=pool_id, Username=user.email, Password=password, Permanent=True
    )

    # Exactly one group per user: add the right one, remove any others.
    current = cognito.admin_list_groups_for_user(UserPoolId=pool_id, Username=user.email)
    for group in current["Groups"]:
        if group["GroupName"] != user.group:
            cognito.admin_remove_user_from_group(
                UserPoolId=pool_id, Username=user.email, GroupName=group["GroupName"]
            )
    cognito.admin_add_user_to_group(UserPoolId=pool_id, Username=user.email, GroupName=user.group)
    return outcome


def delete_all(cognito: Any, ssm: Any, pool_id: str, env: str) -> None:
    for user in USERS:
        try:
            cognito.admin_delete_user(UserPoolId=pool_id, Username=user.email)
            print(f"deleted  {user.email}")
        except ClientError as exc:
            if exc.response["Error"]["Code"] != "UserNotFoundException":
                raise
            print(f"absent   {user.email}")
    try:
        ssm.delete_parameter(Name=password_parameter(env))
        print(f"deleted  {password_parameter(env)}")
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ParameterNotFound":
            raise


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # Only dev: synthetic users must never be seeded into a production pool.
    parser.add_argument("--env", default="dev", choices=["dev"])
    parser.add_argument("--delete", action="store_true", help="remove users and password")
    args = parser.parse_args()

    session = boto3.Session()
    ssm, cognito = session.client("ssm"), session.client("cognito-idp")
    config = load_config(ssm, args.env)
    print(f"user pool {config.user_pool_id} ({session.region_name})")

    if args.delete:
        delete_all(cognito, ssm, config.user_pool_id, args.env)
        return

    password = get_password(ssm, args.env)
    if password is None:
        password = create_password(ssm, args.env)
        print(f"stored new password in {password_parameter(args.env)} (SecureString)")

    for user in USERS:
        outcome = ensure_user(cognito, config.user_pool_id, user, password)
        print(f"{outcome:<8} {user.email:<26} group={user.group}")


if __name__ == "__main__":
    main()
