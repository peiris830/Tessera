# Tessera

> *A tessera was the token shown to enter the theatre in ancient Rome.*

Tessera is a cloud-native event ticketing platform on AWS. It has two halves:

- **Microservices** for browsing events, reserving seats, paying (mock), issuing tickets and
  validating them at the door. They are built with Python/FastAPI on Lambda + API Gateway,
  each with its own DynamoDB table.
- **An event-driven data platform.** Domain events flow EventBridge → Firehose → S3 (Parquet)
  → Glue/Athena → dbt and feed an organiser analytics dashboard.

It is a portfolio project combining software engineering and data engineering.

## Architecture

See [docs/architecture.md](docs/architecture.md) for the system diagram, the main request flow
and the correctness rules. Design decisions are recorded in [docs/adr/](docs/adr/), and
[docs/build-log.md](docs/build-log.md) explains how it was built step by step and why.

| Service | Owns | Responsibilities |
|---|---|---|
| [Catalogue](services/catalogue/) | `events` table | Events, venues, capacity, browse/search |
| [Reservation](services/reservation/) | `reservations` table | Holds, confirmation, capacity counters, waitlist, cancellation |
| [Ticketing](services/ticketing/) | `tickets` table | Async ticket issuance, QR codes, transfer, entry validation |
| [Mock Payment](services/mock-payment/) | – | Sandbox payments/refunds with configurable failures |
| [Notifications](services/notifications/) | – | Consumes domain events, sends simulated notifications |
| [Frontend](frontend/) | – | Attendee portal, organiser console, staff scanner |

## Repository layout

```
docs/                 architecture, ADRs, test evidence
infra/shared/         shared SAM stack: Cognito user pool, EventBridge bus
services/<name>/      src/app/, tests/, openapi.yaml, template.yaml (one SAM stack per service)
frontend/             static site (S3 + CloudFront)
data-platform/        Firehose/Glue infra, dbt project, dashboard
tests/e2e/            end-to-end tests against a deployed stack
tests/load/           k6/Locust scripts
scripts/              synthetic data generator, seeding, backup/restore helpers
.github/workflows/    CI/CD
```

## Status

Phase 1 (core platform) is in progress. The scaffold and architecture docs are done, and the
[shared platform stack](infra/shared/) (Cognito with a hosted login page and self sign-up, EventBridge bus) and the
[Catalogue](services/catalogue/) service are deployed to the dev environment and covered by
end-to-end tests. Browsing events is public. The [frontend](frontend/) has its shell, theme and
split-view layout, and signs people in with Cognito (pages still show sample data until they
are connected to the live API). The other services are still to come.

## Prerequisites

Python 3.12, Docker, AWS CLI v2 (2.32+ for `aws login`), AWS SAM CLI and an AWS account.
Each service and `infra/shared` has its own README with test and deploy commands.

## Deploying (PowerShell, repo root)

```powershell
aws login --profile tessera-dev; $env:AWS_PROFILE = "tessera-dev"
.\scripts\deploy.ps1 shared       # first: Cognito, event bus, artifacts bucket, SSM parameters
.\scripts\deploy.ps1 catalogue    # sam build (Docker running) + sam deploy
.\scripts\frontend-env.ps1         # frontend/.env.local from SSM (after either deploy)
```

Each deploy shows a CloudFormation change set and waits for confirmation.

## Test users and end-to-end tests (PowerShell, repo root)

```powershell
py -3.12 -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements-dev.txt
$env:AWS_PROFILE = "tessera-dev"          # after: aws login --profile tessera-dev
python scripts/seed_users.py              # synthetic users (attendee1/2, organiser1/2, staff1 @example.com)
pytest                                    # tests/e2e against the deployed dev environment
python scripts/seed_users.py --delete     # remove the users and their password parameter
```

The test users' password is random and stored only in SSM Parameter Store
(`/tessera/dev/test-users/password`, SecureString).

## Data & secrets policy

Test, load and analytics data is synthetic. Real people may sign up (as attendees only); their
email stays in Cognito and never appears in the repo, logs, events or the data lake, which use
Cognito's user ID instead. Secrets live in SSM
Parameter Store / Secrets Manager, never in the repo. Payments go only through the mock
payment service.

## License

[MIT](LICENSE)
