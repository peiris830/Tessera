# Shared platform stack

CloudFormation stack `tessera-<env>-shared` for resources every service uses and none owns
([ADR 0002](../../docs/adr/0002-shared-platform-stack.md)). **Deploy it first, tear it down last.**

| Resource | Name (dev) | Notes |
|---|---|---|
| Cognito user pool | `tessera-dev-users` | Lite tier, email sign-in, admin-created users only, optional TOTP MFA |
| App client | `tessera-dev-app` | Public (no secret); SRP for browsers, admin password auth for scripts/tests |
| Groups | `attendee`, `organiser`, `venue_staff` | Arrive in tokens as `cognito:groups` |
| EventBridge bus | `tessera-dev-bus` | Domain events (Phase 3) |

## Published SSM parameters (the contract services rely on)

| Parameter | Value |
|---|---|
| `/tessera/<env>/cognito/user-pool-id` | User pool ID |
| `/tessera/<env>/cognito/app-client-id` | App client ID (JWT audience) |
| `/tessera/<env>/cognito/issuer-url` | `https://cognito-idp.<region>.amazonaws.com/<pool id>` (JWT `iss`) |
| `/tessera/<env>/eventbridge/bus-name` | Event bus name |

## Cost

≈ $0: Cognito Lite is free up to 10,000 monthly active users, the event bus is free (publishing
costs $1 per million events), standard SSM parameters and CloudFormation are free.

## Commands (PowerShell, from this folder)

```powershell
py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements-dev.txt
pytest                         # template policy tests
sam validate --lint            # SAM + cfn-lint checks (local)

$env:AWS_PROFILE = "tessera-dev"
sam deploy                     # uses samconfig.toml; shows the change set and asks before applying
aws ssm get-parameters-by-path --path /tessera/dev --recursive --query "Parameters[].[Name,Value]" --output table

sam delete --stack-name tessera-dev-shared   # teardown (deletes all users); service stacks first
```
