# Build log

How Tessera was built, step by step, and why each choice was made. New entries are added at
the end of each step.

- **Architecture** (what the system is): [architecture.md](architecture.md)
- **Decisions** (formal, one per choice): [adr/](adr/)
- **This log** (how it was built, in order): concepts, reasoning, problems hit and how
  each step was verified.

---

## Step 1: Repo scaffold and architecture

**Built:** folder layout, per-service READMEs with planned endpoints, Git hygiene files,
[architecture.md](architecture.md) (system diagram, purchase-flow sequence diagram, correctness
rules, security model) and [ADR 0001](adr/0001-serverless-microservices-per-service-stack.md).

**Why serverless (Lambda + API Gateway HTTP API) instead of containers:**
the platform is idle most of the time, with spikes at ticket launches. Lambda costs nothing
when idle and scales automatically. ECS/Fargate would bill around the clock and needs a
VPC and load balancer.

**Why one DynamoDB table per service:** "no service reads another service's table" is what
makes these real microservices, not one app split over several Lambdas. Each service can
change its data model and deploy independently. Cross-service data flows through REST, SQS
or EventBridge.

**Key idea: correctness through conditional writes.** Overselling, duplicate tickets and
double entry are each prevented by a DynamoDB *condition expression*, a rule checked
atomically as part of the write. If it fails, nothing is written, so two concurrent requests
can never both pass.

**Housekeeping choices:**
- **`.gitattributes` forces LF line endings,** because Lambda and CI run on Linux, where CRLF
  breaks scripts.
- **`.gitignore` blocks `.env` files, keys and SAM build output** from the start.

---

## Step 1b: Open questions settled as ADRs

| ADR | Decision | Reasoning |
|---|---|---|
| [0002](adr/0002-shared-platform-stack.md) | Cognito and the EventBridge bus live in a shared stack (`infra/shared/`); IDs are shared via SSM Parameter Store | CloudFormation Exports lock values while any stack imports them. SSM keeps stacks loosely coupled and is free. |
| [0003](adr/0003-capacity-counter-initialisation.md) | Reservation creates each event's capacity counter on the first booking, fetching capacity from Catalogue once | Keeps Catalogue off the purchase path. A conditional put settles the race between two "first" bookings. |
| [0004](adr/0004-mock-payment-iam-auth.md) | Mock Payment is an HTTP API with IAM auth, and Reservation signs requests with SigV4 | Stays a real HTTP dependency (timeouts and malformed responses to test), with no secrets to store and no cost. |

---

## Step 2a: Catalogue service skeleton

**Built:** a FastAPI app with `/v1/health`, correlation-ID middleware, JSON logging, a
consistent error body and a Lambda entry point. Code is in `services/catalogue/app/`.

**One app, two ways to run it.** API Gateway doesn't send Lambda an HTTP request; it sends a
JSON *event*. **Mangum** translates that event into a request FastAPI understands, and
translates the response back. So the same FastAPI app runs locally under `uvicorn` and on
Lambda via `handler = Mangum(app)`, and almost everything can be tested without AWS.

**Plumbing before endpoints**, because retrofitting it into many routes later is painful:

| Concern | How | Why |
|---|---|---|
| Correlation ID | Middleware reads `X-Correlation-Id` or generates a UUID, stores it in a `ContextVar` and echoes it in the response | Traces one user action across services. Only `[A-Za-z0-9._-]{1,128}` is accepted, to prevent log injection. |
| JSON logs | A custom formatter adds service and correlation ID; `extra={...}` adds fields | CloudWatch Logs Insights can filter on fields. The formatter replaces Lambda's own plain-text handler to avoid duplicate lines. |
| Error format | Handlers map `APIError`, HTTP errors and validation errors to `{"error": {code, message, correlationId}}` | Clients handle one shape. Crashes return a generic 500 and never a stack trace. Validation messages don't repeat what the user sent. |
| Access log | One line per request: method, path, status, duration | The path only, no query string, because query strings can carry personal data. |

**Lambda cold vs warm starts.** Module-level code (logging setup, building the app,
`Mangum(...)`) runs once, when AWS starts a new execution environment. Later "warm"
requests only call `handler`, so setup cost is paid once.

**Problems hit:**
- **Local Python was 3.10.** I installed 3.12 alongside it to match the Lambda runtime;
  the `py -3.12` launcher picks it, and each service has its own `.venv`.
- **Starlette 1.x deprecates `httpx` for its TestClient in favour of `httpx2`.** I checked
  Starlette's source before switching, because a lookalike package name is a common
  supply-chain trick.
- **Pytest now treats unexpected warnings as errors,** so library deprecations get noticed.
  One harmless Mangum warning is ignored specifically.

**Verified:** 11 tests, including one that calls `handler()` with a realistic API Gateway
event; plus a real `uvicorn` run showing JSON log lines carrying the correlation ID.

**Deliberate shortcut:** each service will keep its own copy of the plumbing until a
second service exists. Sharing code across Lambdas needs a package or Lambda layer, which
isn't worth it until we can see what's genuinely common.

---

## Step 2b: Events data model and read endpoints

**Built:** the `Event`/`EventOut` models, `EventRepository` (the only DynamoDB code),
opaque pagination tokens, `GET /v1/events` and `GET /v1/events/{eventId}`, tested with moto.

**DynamoDB modelling starts from access patterns, not normalisation.** DynamoDB only queries
efficiently by key, so you list what you need to read and design the keys for it:

| Access pattern | Served by |
|---|---|
| Get one event | Table partition key `eventId` |
| Browse upcoming published events, soonest first | GSI `by-status-start`: `status` + `startsAt` |
| An organiser's events (step 2c) | GSI `by-organiser`: `organiserId` + `startsAt` |

**Important details and the reasoning behind them:**
- **Timestamps are stored as `YYYY-MM-DDTHH:MM:SSZ` (UTC, whole seconds).** Sort keys
  compare strings character by character. One fixed format makes alphabetical order the same
  as time order; mixed offsets or fractions would quietly break sorting.
- **`create()` uses `attribute_not_exists(eventId)`.** A plain `PutItem` silently overwrites
  an existing item; the condition makes creation insert-only, atomically. It's the same
  technique Ticketing will use to issue each ticket exactly once.
- **Query, never Scan, in request paths.** A Scan reads and bills for every item in the table.
- **`get()` uses an eventually consistent read:** half the cost of a strongly consistent one.
  A sub-second lag is fine for browsing.
- **Two models for one event.** `EventOut` lists exactly the public fields (with no
  `organiserId`), so new internal fields can't leak by accident.
- **Drafts return 404, not 403,** so nobody can tell that a private event exists.
- **Datetimes without a timezone are rejected,** since `19:00` without a zone is ambiguous.

**Pagination.** DynamoDB has no "page 5"; it returns `LastEvaluatedKey` and resumes from it
when given `ExclusiveStartKey`. We give clients a base64 `nextToken` containing:
- **DynamoDB's position**, which includes `eventId` to break ties between events starting
  in the same second;
- **the original `from` time.** Without it, page 2 would recompute "now", and the saved
  position could fall outside the new range. DynamoDB rejects that, and the user would see a 500.

The token comes from the client, so it's **untrusted input**. It's checked for length, bad
base64, bad JSON and shape, then the key must be exactly one this query could have produced.
Any failure returns `400 INVALID_NEXT_TOKEN`. "Opaque" isn't the same as secret, though:
anyone can decode it, and it contains nothing sensitive.

**Testing with moto.** moto intercepts boto3 calls and serves an in-memory DynamoDB.
Every test sets fake AWS credentials, so a mistake can never reach a real account. FastAPI's
`dependency_overrides` swaps the real repository for a moto-backed one.

**Trade-offs accepted:**
- **All published events share one GSI partition.** That's fine at this scale; at large
  scale you'd split by city or month.
- **The GSIs copy every attribute** (projection `ALL`). It costs a little extra storage,
  but queries never need a second lookup.
- **Venue is stored inside each event,** rather than as a separate entity.
- **boto3 is a dev dependency only,** because the Lambda runtime already includes it. That
  keeps the deployment package small.
- **The table schema is written out in the tests for now.** The SAM template in 2c will
  define the real table, and the two must match by hand until then.

**Scope change:** creating and editing events moved to 2c, because they're organiser-only
and need the authentication work.

**Verified:** 37 tests. They include paging through 5 events 2 at a time with no gaps or
duplicates, refusing to overwrite an existing event, and rejecting tampered or reused tokens.
