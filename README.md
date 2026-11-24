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
[Catalogue](services/catalogue/) service is built and tested with its SAM template; it isn't
deployed yet. The other services are still to come.

## Prerequisites

*To be completed as the services are built.* Expected: Python 3.12, Docker, AWS CLI v2,
AWS SAM CLI and an AWS account (free tier).

## Data & secrets policy

Synthetic data only, and no personal data in logs or the data lake. Secrets live in SSM
Parameter Store / Secrets Manager, never in the repo. Payments go only through the mock
payment service.

## License

[MIT](LICENSE)
