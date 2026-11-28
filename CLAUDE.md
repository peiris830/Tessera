# Tessera â€“ Cloud-Native Event Ticketing & Data Platform

> *A tessera was the token shown to enter the theatre in ancient Rome.*
> Tessera is a distributed ticketing platform on AWS: microservices for event browsing,
> reservations and ticket validation, plus an event-driven data platform for analytics.
> Portfolio project showing software engineering and data engineering together.

## How to work with me
- I'm building this to LEARN AWS, microservices, distributed systems and data engineering.
  I'm a CS graduate with Python, SQL and Azure experience, new to AWS.
- Build step by step. Before writing a new piece, briefly explain the concept and the design
  choice (1â€“3 short paragraphs), then implement it. Keep changes small enough to review.
- Explain AWS-specific things (IAM policies, SAM templates, DynamoDB condition expressions,
  Firehose, Glue, Athena) the first time they appear.
- Stop and ask before anything that costs money or is hard to undo (deploying, creating
  AWS resources, deleting stacks or data). Prefer free-tier-friendly options.
- Never commit secrets, tokens, real personal data or `.env` files. Payments only through the
  mock payment service.
- Data is hybrid: test, load and analytics data is synthetic (`@example.com` users from the
  seed script). Real people may self-register, as attendees only; their email stays in
  Cognito, never in the repo, logs, events or the data lake (use the Cognito `sub` as user ID).
- Dev machine: Windows, VS Code, Python, Git, Docker. Give PowerShell-compatible commands.
- Finish one phase properly (working, tested, documented) before starting the next.
- Keep `docs/build-log.md` up to date: at the end of every step, add an entry (what was
  built, reasoning, concepts, problems hit, how it was verified) and commit it with the step.
- Explain each step to me before committing it.
- Keep this CLAUDE.md up to date: whenever a step starts, finishes, or a decision is made,
  update "Current status" / "Decisions" here. It is tracked in git and committed with the step.
- Before building a new component, present its design decisions (tech + UI) with
  alternatives and a recommendation, and get my agreement first.

## Roles
- **Attendee:** browse events, reserve, pay (mock), hold tickets, cancel, transfer, join waitlists.
  Sees only their own reservations and tickets.
- **Organiser:** create/manage only their own events and capacity; sees analytics for their events.
- **Venue staff:** scan/validate tickets at entry.
All role and ownership checks are enforced on the server.

## Services
| Service | Owns | Responsibilities |
|---|---|---|
| Catalogue | events table | Events, venues, capacity definitions, search/browse |
| Reservation | reservations table | Holds with expiry, confirmation, capacity counters, waitlist, cancellations |
| Ticketing | tickets table | Ticket issuance (async), QR codes, transfer, entry validation |
| Mock Payment | â€“ | Sandbox payments/refunds with configurable delay, failure, malformed responses |
| Notifications | â€“ | Consumes events, sends (logged/simulated) attendee notifications |
| Frontend | â€“ | Attendee portal, organiser console, staff scanner page |
No service reads another service's table. Communication is via REST APIs or events only.

## Phased roadmap

### Phase 1 â€“ Core platform (MVP)
- Browse event â†’ reserve â†’ pay (mock) â†’ ticket issued async via SQS â†’ validate at entry â†’
  status updated in UI.
- Cognito auth with groups `attendee`, `organiser`, `venue_staff`; 403 tests for other users'
  resources.
- No overselling (two competing requests for the last place), no double entry,
  idempotent ticket issuance, compensation when payment/reservation fails.
- Timeouts/retries, health checks, controlled failure + recovery, structured logs with
  correlation ID, one alarm, DynamoDB PITR backup/restore evidence.
- Deployed with SAM; frontend on S3 + CloudFront.

### Phase 2 â€“ Real ticketing behaviour
- **Seat holds with expiry:** held for N minutes, auto-released (DynamoDB TTL + stream, or
  Step Functions).
- **Waitlist with auto-promotion:** cancellation/expiry promotes the next waitlisted attendee.
- **Cancellations & refunds** via mock payment (compensation flow).
- **Ticket transfer** between attendees with ownership checks.
- **QR-code tickets** + staff scanner page.

### Phase 3 â€“ Data platform
- All domain events published to **EventBridge** (`EventCreated`, `HoldPlaced`, `HoldExpired`,
  `ReservationConfirmed`, `ReservationCancelled`, `TicketIssued`, `TicketTransferred`,
  `TicketScanned`, `WaitlistPromoted`).
- **Kinesis Data Firehose â†’ S3 data lake** (raw zone, partitioned by date, Parquet).
- **Glue Data Catalog + Athena** for SQL over the lake.
- **dbt (dbt-athena)** models: staging â†’ marts. Metrics: sales per event, sell-through rate,
  time-to-sell-out, hold-to-purchase conversion, no-show rate, waitlist conversion.
- Data quality tests (dbt tests / Great Expectations).
- Organiser analytics dashboard (Streamlit or Grafana).

### Phase 4 â€“ Polish & optional extras
- CI/CD with GitHub Actions (lint, test, deploy to dev stack).
- Synthetic data generator simulating launch-day rushes (feeds load tests and the lake).
- Load tests with k6 or Locust at 3+ increasing levels.
- OpenTelemetry / X-Ray tracing.
- Optional ML: scalper/bot detection, sell-out demand forecasting.

## Stack decisions
| Concern | Choice |
|---|---|
| Language | Python 3.12, FastAPI (+ Mangum adapter for Lambda) |
| Hosting | AWS Lambda + API Gateway (HTTP API), one SAM stack per service |
| Operational data | One DynamoDB table per service |
| Identity | Amazon Cognito user pool + groups; API Gateway JWT authorizer |
| Messaging | SQS (+ DLQ) for work queues; EventBridge for domain events |
| Secrets | SSM Parameter Store / Secrets Manager |
| Frontend | React + TypeScript 5.9 + Vite SPA on S3 + CloudFront; types from OpenAPI (ADR 0005) |
| IaC | AWS SAM |
| Observability | CloudWatch Logs (JSON), metrics, alarms; X-Ray optional |
| Backup | DynamoDB point-in-time recovery |
| Data lake | Firehose â†’ S3 (Parquet) â†’ Glue Catalog â†’ Athena â†’ dbt |
| Tests | pytest, moto, httpx; k6 or Locust |

## Key correctness patterns
- **Capacity:** atomic `UpdateItem` with `ConditionExpression: held + confirmed < capacity`;
  a failed condition â†’ `409 Conflict`.
- **Ticket issuance idempotency:** `PutItem` with `attribute_not_exists(reservationId)`.
- **Entry validation:** conditional update `status = ISSUED â†’ USED`; a second scan â†’ `409`.
- **Event envelope:** `{eventId, eventType, version, occurredAt, correlationId, data}`;
  consumers deduplicate on `eventId`.
- **APIs:** versioned routes (`/v1/...`), consistent error body
  `{"error": {"code", "message", "correlationId"}}`, OpenAPI spec per service.
- **Correlation ID:** `X-Correlation-Id` header, generated at the edge, propagated via HTTP
  headers, SQS message attributes and event envelopes, present in every log line.
- **No personal data in logs or the data lake:** use synthetic user IDs only.

## Repo layout (target)
```
/docs                    architecture diagrams, ADRs, test evidence
/infra/shared            shared SAM stack (Cognito, EventBridge bus), outputs via SSM (ADR 0002)
/services/catalogue      src/app/ (packaged; SAM CodeUri: src/), src/requirements.txt, tests/,
                         scripts/, openapi.yaml (generated), template.yaml
/services/reservation
/services/ticketing
/services/mock-payment
/services/notifications
/frontend
/data-platform           firehose/glue infra, dbt project, dashboard
/tests/e2e               end-to-end tests
/tests/load              k6/Locust scripts
/scripts                 synthetic data generator, seed, backup/restore helpers
.github/workflows        CI/CD
README.md                overview, prerequisites, config variable names, deploy/teardown, tests
```

## Decisions log (details in docs/adr and docs/build-log.md)
- Region us-east-1; AWS CLI profile `tessera-dev` (`aws login`, temporary credentials).
- Dev IAM user: PowerUserAccess + inline `tessera-deployer-iam` (manage `tessera-*` roles only).
- Budgets exist ($1 zero-spend alert, $10 monthly); don't create more (first two free).
- Frontend (ADR 0005): React + TS 5.9 + Vite, Mantine 9 (compact-ish, Stitch-derived blue
  theme), TanStack Query, React Router, Tabler icons, Plus Jakarta Sans + JetBrains Mono,
  one app with role-aware nav, split-view layout ("less whitespace" = use space for content),
  times in viewer's local time + offset, generated mosaic covers.
- Sign-in (5b): Cognito classic hosted UI + OAuth 2.0 authorization code + PKCE (option B1,
  free on Lite tier); tokens per tab (sessionStorage); access token sent to APIs.
- Browsing is public (no sign-in); writes and drafts require auth.
- 5b-2 (agreed): Cognito domain = auto prefix `tessera-<env>-<8 hex from stack ID>` (classic
  hosted UI, `ManagedLoginVersion: 1`); OAuth code flow only, scopes `openid email`,
  callback/logout URLs as template parameters; tokens unchanged (60 min / 7 days).
  Self sign-up ON (hybrid data rule): email verification by code (Cognito default sender,
  50/day), post-confirmation Lambda adds self-registered users to `attendee`; organiser and
  staff only via the seed script. Login page styled with blue CSS only (no logo, no fonts).
  Frontend config: committed `frontend/.env.example` + `scripts/frontend-env.ps1` writing
  gitignored `.env.local` from SSM.
- Unsplash photos in 5e; organiser photo upload later.
## Current status
- [x] Phase 1 â€“ Step 1: repo scaffold + architecture diagram (docs/architecture.md, ADR 0001)
- [x] Open architecture questions resolved as ADRs 0002â€“0004
- [x] Phase 1 â€“ Step 2aâ€“2c: Catalogue skeleton, data model + reads, auth + organiser endpoints
- [x] Phase 1 â€“ Step 2d: Catalogue OpenAPI spec + SAM template (validated + built locally)
- [x] Phase 1 â€“ Step 3: shared stack deployed (tessera-dev-shared, us-east-1, profile tessera-dev)
- [x] Phase 1 â€“ Step 3b: synthetic test users (scripts/seed_users.py) + e2e token tests
- [x] Phase 1 â€“ Step 4: Catalogue deployed (tessera-dev-catalogue) + e2e API smoke tests
- [x] Phase 1 â€“ Step 4b: own artifacts bucket in shared stack, scripts/deploy.ps1 (deploy with
  `.\scripts\deploy.ps1 shared|catalogue`), quieter loggers, SAM-managed bucket removed
- [ ] Phase 1 â€“ Step 5 (in progress): frontend
  - [x] 5a: Mantine shell, split view, mosaic covers, sample data (4d12144)
  - [x] 5b-1 (deployed, 20 e2e pass): public `GET /v1/events` + `GET /v1/events/{id}`
    (Authorizer NONE; PUBLISHED/CANCELLED only, drafts 404 for everyone), new
    `GET /v1/organisers/me/events/{id}` (owner reads drafts), CORS (origins param, default
    `http://localhost:5173`) + token-less `OPTIONS /v1/{proxy+}` route (app answers 204;
    without it the JWT catch-all 401s preflights), OpenAPI security per operation,
    frontend types regenerated
  - [x] 5b-2 (deployed, 25 e2e pass): shared stack (now SAM + CAPABILITY_IAM): Cognito
    domain, app client OAuth, classic hosted UI CSS, self sign-up + inline post-confirmation
    trigger `tessera-dev-post-confirmation` (→ attendee), SSM `cognito/hosted-ui-url`;
    `frontend/.env.example` + `scripts/frontend-env.ps1`; config.ts reads
    VITE_CATALOGUE_API_URL, VITE_COGNITO_AUTHORITY, VITE_COGNITO_CLIENT_ID,
    VITE_COGNITO_HOSTED_UI_URL. Privacy note only in the verification email so far.
  - [ ] 5b-3: frontend sign-in (oidc-client-ts + react-oidc-context, PKCE, sessionStorage),
    user menu, role-aware nav (My events for organisers), bearer token on API calls,
    Cognito logout endpoint
  - [ ] 5c: live browse (public, no sign-in) Â· 5d: live organiser console
  - [ ] 5e: Unsplash cover photos via organiser-only backend proxy (key in SSM SecureString,
    cover URL restricted to images.unsplash.com, attribution, mosaic fallback)
- [ ] Later (after step 4): local dev environment: docker-compose with DynamoDB Local,
  AWS_ENDPOINT_URL, table bootstrap from template.yaml, local-only auth shortcut that refuses
  to start inside Lambda; e2e smoke tests runnable against local or AWS
- [ ] Later (Phase 2/4): organiser event photo upload: S3 presigned PUT URL endpoint, imageKey
  on events, type/size validation, resize Lambda, serve via CloudFront; generated mosaic covers
  stay as fallback. List costs first (S3 ~$0.023/GB-month, CloudFront free tier).
- [ ] Later (before sharing the hosted app): "delete my account" for self-registered users,
  privacy note shown before sign-up, cleanup of never-confirmed sign-ups, bot protection
  (Cognito threat protection needs the Plus tier: list costs or use a free alternative)
- [ ] Later: IAM permissions boundary capping `tessera-*` roles the dev user creates
  (closes the inline-policy gap in the `tessera-deployer-iam` policy)
- Note: venv uses `py -3.12` (PATH python is 3.10). SAM CLI, AWS CLI, Docker installed;
  build with `sam build --use-container`.
