# Shared platform stack

CloudFormation stack `tessera-<env>-shared` for resources every service uses and none owns
([ADR 0002](../../docs/adr/0002-shared-platform-stack.md)). **Deploy it first, tear it down last.**

| Resource | Name (dev) | Notes |
|---|---|---|
| Cognito user pool | `tessera-dev-users` | Lite tier, email sign-in, optional TOTP MFA; self sign-up with email code (Cognito's free sender, 50/day) |
| App client | `tessera-dev-app` | Public (no secret); OAuth code flow + PKCE for the frontend (scopes `openid email`), admin password auth for scripts/tests |
| Hosted login page | `tessera-dev-<8 hex>.auth.<region>.amazoncognito.com` | Classic hosted UI, Tessera-blue CSS; suffix from the stack ID; callback/logout URLs are template parameters |
| Sign-up trigger | `tessera-dev-post-confirmation` | Lambda (inline code): self-registered users join `attendee`; may only call `AdminAddUserToGroup` |
| Groups | `attendee`, `organiser`, `venue_staff` | Arrive in tokens as `cognito:groups` |
| EventBridge bus | `tessera-dev-bus` | Domain events (Phase 3) |
| Artifacts bucket | `tessera-dev-artifacts-<account>-<region>` | Code uploaded by `sam deploy`; public access blocked, HTTPS only, expires after 90 days |

## Published SSM parameters (the contract services rely on)

| Parameter | Value |
|---|---|
| `/tessera/<env>/cognito/user-pool-id` | User pool ID |
| `/tessera/<env>/cognito/app-client-id` | App client ID (JWT audience) |
| `/tessera/<env>/cognito/issuer-url` | `https://cognito-idp.<region>.amazonaws.com/<pool id>` (JWT `iss`) |
| `/tessera/<env>/cognito/hosted-ui-url` | Hosted login page base URL (read by `scripts/frontend-env.ps1`) |
| `/tessera/<env>/eventbridge/bus-name` | Event bus name |
| `/tessera/<env>/artifacts/bucket-name` | Artifacts bucket (read by `scripts/deploy.ps1`) |

## Cost

≈ $0: Cognito Lite (incl. the hosted login page and domain) is free up to 10,000 monthly active users, the sign-up trigger runs inside Lambda's free tier, the event bus is free (publishing
costs $1 per million events), standard SSM parameters and CloudFormation are free. The artifacts
bucket holds a few MB (fractions of a cent), capped by the 90-day expiry.

## Commands (PowerShell)

```powershell
# from this folder: tests and checks
py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements-dev.txt
pytest                         # template policy tests + the trigger's inline code
sam validate --lint            # SAM + cfn-lint checks (local)

# from the repo root: deploy (shows the change set and asks before applying)
$env:AWS_PROFILE = "tessera-dev"
.\scripts\deploy.ps1 shared
aws ssm get-parameters-by-path --path /tessera/dev --recursive --query "Parameters[].[Name,Value]" --output table
```

**Teardown** (delete service stacks first; this deletes all users):

```powershell
aws s3 rm "s3://$(aws ssm get-parameter --name /tessera/dev/artifacts/bucket-name --query Parameter.Value --output text)" --recursive
sam delete --stack-name tessera-dev-shared
```

CloudFormation can't delete a non-empty bucket, hence emptying it first (the bucket isn't
versioned, so `aws s3 rm` removes everything).
