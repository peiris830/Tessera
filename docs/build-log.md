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

---

## Step 2c: Authentication, roles, ownership and organiser endpoints

**Built:** `app/auth.py` (the caller, taken from JWT claims), organiser endpoints (create,
partial update, publish, list own events), and sign-in required on every events route.
The original step 2c was split so each part stays reviewable; the OpenAPI spec and the
SAM template moved to step 2d.

**Authentication vs authorisation, and where each happens:**
1. **Cognito issues a signed JWT at sign-in.** It carries `sub` (a stable, random user ID),
   `cognito:groups` and `exp`.
2. **API Gateway's JWT authorizer verifies the token before Lambda runs:** signature, issuer,
   audience and expiry. Bad tokens get 401. Valid claims reach Lambda at
   `requestContext.authorizer.jwt.claims`, which Mangum exposes as `request.scope["aws.event"]`.
3. **The service does authorisation** (roles and ownership). It trusts the claims because only
   API Gateway can invoke the function, and it **never** reads identity from a client header.
   A test proves an `X-User-Id` header is ignored.

**AWS quirk:** HTTP API flattens list claims, so `cognito:groups` arrives as the string
`"[organiser attendee]"`. The parser accepts that form, comma-separated strings and real lists.

**The access rules:**

| Situation | Response | Reasoning |
|---|---|---|
| No identity | 401 | |
| Wrong role | 403 `FORBIDDEN` | |
| Missing, or someone else's draft | 404 | Nobody can tell a private draft exists |
| Someone else's published event | 403 `NOT_EVENT_OWNER` | It's visible anyway, so 403 reveals nothing |
| The event's state forbids the change | 409 | e.g. a cancelled event, or a second publish |

**Protecting writes against races:**
- **`UpdateItem` is an upsert:** it creates the item if it doesn't exist. Every update
  therefore includes `attribute_exists(eventId)`; otherwise a PATCH to a made-up ID would
  create a phantom event.
- **Check-then-write has a gap.** The route reads the event to give precise errors (404, 403
  or 409), but something can change before the write. So the write repeats the checks in
  its condition: `organiserId = :owner AND #status = :expected`. If the event changed
  meanwhile, the write fails with `409 EVENT_STATE_CONFLICT`. In short: the read is for
  helpful messages, and the condition is what guarantees correctness.
- **`status` is a DynamoDB reserved word,** so update expressions use `#placeholders` for
  attribute names and `:placeholders` for values. They never concatenate user input into
  an expression.

**Other choices:**
- **No mass assignment:** request models use `extra="forbid"`, so a client can't send
  `organiserId` or `status`. The server sets them.
- **Whitespace is stripped from input,** so `"   "` doesn't count as a title.
- **Capacity locks after publishing** (ADR 0003): Reservation snapshots it once bookings
  start, so changing it later would put the services out of step.
- **Events are created as DRAFT;** publishing is a separate, explicit action that requires
  a start time in the future.
- **`/v1/organisers/me/events`** uses the `by-organiser` GSI. Its page token is pinned to the
  caller, so one organiser's token can't page through another's events.
- **The pagination token's second field became a general `scope`** (the `from` time for
  browsing, the organiser ID for "my events").
- **Pydantic v2 validator reuse:** a `FutureDatetime = Annotated[AwareDatetime,
  AfterValidator(...)]` type replaced the v1-style `field_validator(...)(func)` trick.

**Testing approach:**
- **Most tests swap the caller** with `dependency_overrides` (`act_as(ORGANISER)` /
  `act_as(None)`).
- **Lambda handler tests send real API Gateway events with authorizer claims**, proving
  the whole path from claims to caller to ownership.
- **Repository tests simulate races directly:** read DRAFT, someone else publishes, then
  the draft-only edit is rejected.

**Verified:** 92 tests. They include 403 and 404 for other organisers' events, mass-assignment
attempts rejected, PATCH on a missing ID creating nothing, and the race guard holding.

---

## Step 2d: OpenAPI spec and SAM template

**Built:** `services/catalogue/template.yaml` (the infrastructure as code), a generated
`openapi.yaml` with a drift test, and tests that check the template's security and cost rules.
The code moved to a `src/` layout. Nothing is deployed yet; deploying needs the shared stack
(step 3).

**What a SAM template is:**
- **CloudFormation** is AWS's infrastructure-as-code service. You describe resources in YAML
  and CloudFormation creates, updates or deletes them as one **stack**.
- **SAM** is a shorthand on top of it. `Transform: AWS::Serverless-2016-10-31` makes types like
  `AWS::Serverless::Function` expand into the Lambda function, its IAM role and its API
  Gateway routes.
- **`sam build`** installs the dependencies into a deployment package. `sam deploy` uploads it
  and runs CloudFormation.

**What the template creates:**

| Resource | Key settings | Why |
|---|---|---|
| DynamoDB table | on-demand billing, both GSIs, PITR, deletion protection in prod only | Pay per request (≈ $0 when idle); PITR gives the backup/restore evidence Phase 1 asks for |
| Lambda function | Python 3.12, arm64, 512 MB, 10 s timeout | arm64 (Graviton) is ~20% cheaper per GB-second; 10 s fails fast instead of hanging |
| IAM policy | `GetItem`/`PutItem`/`UpdateItem` on the table, `Query` on its indexes | Least privilege: only what the code calls. No `Scan`, no `DeleteItem`, no wildcards |
| HTTP API | Cognito JWT authorizer by default; `/v1/health` public; throttling 25 req/s, burst 50 | Unauthenticated requests are rejected before Lambda runs, so they cost nothing; throttling caps runaway bills |
| Log groups | 14-day retention | Without a retention setting CloudWatch keeps logs forever and charges for storage |
| Access log format | method, path, status, latency, request ID; no IP or user identity | No personal data in logs |
| SSM parameter | `/tessera/<env>/catalogue/api-url` | Other services find this API without hard-coded URLs (ADR 0002) |

**Concepts:**
- **IAM policies** say who may do which action on which resource. SAM attaches the policy to the
  function's execution role; the function gets temporary credentials for that role automatically,
  so there are no keys in code or config.
- **SSM-typed parameters** (`AWS::SSM::Parameter::Value<String>`): the template takes a parameter
  *name* such as `/tessera/dev/cognito/issuer-url`, and CloudFormation reads its value at deploy
  time. This is how the Catalogue stack picks up the shared stack's Cognito settings.
- **The JWT authorizer** checks the token's signature against Cognito's public keys, plus issuer,
  audience and expiry. The function still enforces roles and ownership itself.
- **`!Ref`, `!GetAtt`, `!Sub`, `!If`** are CloudFormation functions: refer to a resource, read one
  of its attributes (e.g. the table ARN), build a string, choose a value by condition.

**Choices:**
- **`src/` layout:** `CodeUri: src/` packages only the app and its runtime requirements, not the
  tests, `.venv` or dev tools. boto3 is left out because the Lambda runtime already includes it.
- **The spec is generated from the code** (`scripts/export_openapi.py`) and committed. A test
  regenerates it and fails if the two differ, so the published spec can't go stale. The spec now
  documents the real error body (`ErrorResponse`) for every error code and marks which routes
  need a bearer JWT.
- **The tests read the template.** `tests/cfn.py` parses it (keeping the `!Ref`-style tags), and
  `conftest.py` builds the moto table from the template's own definition, so tests and AWS can't
  disagree about keys and indexes. `test_template.py` turns the security rules into tests: least
  privilege, only health is public, throttling set, every log group has retention, access logs
  contain no IP or identity fields.
- **`sam build --use-container`** builds inside AWS's Lambda build image. This matters because
  pydantic-core ships compiled code: a Windows build would package a Windows binary that can't
  run on Lambda. It also sidesteps local Python version issues.

**Problems hit:**
- **Cross-architecture build:** SAM warns when building arm64 on an x86 machine. Docker emulates
  ARM, so the build is slower but works. The package was checked to contain
  `_pydantic_core.cpython-312-aarch64-linux-gnu.so`, the ARM Linux binary.
- **The SAM and AWS CLIs** had to be installed (`winget install Amazon.SAM-CLI` /
  `Amazon.AWSCLI`), and Docker had to be running for the container build.

**Cost:** nothing yet; nothing is deployed. When deployed: Lambda, API Gateway and DynamoDB
on-demand cost ≈ $0 at this traffic (free tier / pay per request), PITR about $0.20 per GB-month
(well under $0.01 for this table), and the SAM artifact bucket ≈ $0.01.

**Verified:** 104 tests (spec drift, template policies, the moto table built from the template).
`sam validate --lint` passed, and `sam build --use-container` succeeded: a 9.1 MB package with
ARM binaries and no tests, venv or boto3.