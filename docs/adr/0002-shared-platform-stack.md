# ADR 0002: Shared platform stack in `infra/shared/`, outputs published via SSM

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

Some resources are used by every service and belong to none of them: the **Cognito user pool**
(with its app client and the `attendee`, `organiser`, `venue_staff` groups) and the
**EventBridge bus** for domain events. They need a home outside the per-service stacks
(ADR 0001), and services need a way to find their IDs and ARNs.

## Decision

- Shared resources live in one SAM stack at **`infra/shared/template.yaml`**, deployed as
  `tessera-<env>-shared` (e.g. `tessera-dev-shared`). It's deployed **before** any service stack.
- The shared stack writes the values services need to **SSM Parameter Store**:
  - `/tessera/<env>/cognito/user-pool-id`
  - `/tessera/<env>/cognito/app-client-id`
  - `/tessera/<env>/cognito/issuer-url`
  - `/tessera/<env>/eventbridge/bus-name`
  - `/tessera/<env>/artifacts/bucket-name` *(added 2026-11-28, see Amendments)*
- Service templates read them with SAM/CloudFormation dynamic references, e.g.
  `{{resolve:ssm:/tessera/dev/cognito/user-pool-id}}`, or as SSM-typed parameters.
- Service-specific URLs follow the same pattern. Each service publishes its own base URL
  (e.g. `/tessera/<env>/catalogue/api-url`) for the services that call it.

## Alternatives considered

- **CloudFormation Exports/`Fn::ImportValue`:** built in, but an exported value can't be changed
  or deleted while any stack imports it. That makes the stacks rigid and teardown order fiddly.
- **Shared resources inside one service's stack:** this would tie every service to that
  service's lifecycle; deleting it would break authentication for all of them.
- **Hard-coded IDs in each template:** these break whenever the shared stack is recreated, and
  they don't work across environments.

## Consequences

- One extra stack to deploy and tear down (shared first on deploy, last on teardown).
- Stacks are loosely coupled: a service only depends on a parameter name, not on another stack.
- Standard SSM parameters are free, which suits the free tier.
- `infra/` is added to the repo layout.

## Amendments

- **2026-11-28, deployment artifacts bucket.** The shared stack also owns the S3 bucket that
  `sam deploy` uploads service code to (`tessera-<env>-artifacts-<account>-<region>`: public
  access blocked, HTTPS only, objects expire after 90 days). It replaces the SAM-managed
  bucket, which kept every upload forever. Its name contains the account ID, so it isn't
  committed in `samconfig.toml`: `scripts/deploy.ps1` reads `/tessera/<env>/artifacts/bucket-name`
  and passes `--s3-bucket`. Teardown must empty the bucket before deleting the shared stack.
