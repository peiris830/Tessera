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

---

## Step 3: AWS account setup and the shared platform stack

**Built:** `infra/shared/template.yaml`, deployed as `tessera-dev-shared` in us-east-1. It
contains the Cognito user pool, app client and the three role groups, the EventBridge bus,
and the four SSM parameters from ADR 0002. 22 policy tests, `samconfig.toml` for repeatable
deploys. This is the first step that created anything in AWS.

**Account setup (done once, not in the repo):**
- **CLI sign-in with `aws login`:** browser sign-in with the console password and MFA. The CLI
  gets temporary credentials, so there's no long-lived access key on disk. A named **profile**
  (`tessera-dev`) holds the identity and region; `$env:AWS_PROFILE` selects it per terminal.
- **Permissions:** the dev user has `PowerUserAccess`, which allows everything except IAM.
  That's enough for this stack (it has no IAM resources), but every Lambda needs an execution
  role. The admin account therefore attached an inline policy, `tessera-deployer-iam`: manage only roles named
  `tessera-*`, attach only four AWS-managed Lambda policies, and pass roles only to the
  services this project uses. Broad IAM rights would make the dev user an admin in all but
  name, since IAM can grant anything. The remaining gap (inline policies on `tessera-*` roles)
  will be closed with a permissions boundary later.
- **Budgets:** two already existed: a $1 zero-spend budget alerting at $0.01, and a $10
  monthly budget alerting at 85%, 100% and 100% forecast. The first two budgets are free and
  each extra one costs $0.02/day, so no new one was created.

**Concepts:**
- **Cognito user pool:** the user directory. At sign-in it issues an ID token (who you are),
  an access token (sent to APIs) and a refresh token. Tokens carry `sub` and `cognito:groups`
  and are signed with the pool's keys, which API Gateway checks.
- **App client and auth flows:** the client ID is the access token's `client_id`, which the JWT
  authorizers check as the audience. Only two sign-in flows are enabled. SRP lets the browser
  prove it knows the password without sending it. Admin password auth needs AWS credentials,
  so only scripts and tests can use it. Plain password sign-in is off.
- **EventBridge bus:** services publish domain events and rules route them to targets. It's
  created now so its name is fixed; publishing starts in Phase 3.
- **Change sets:** `sam deploy` shows the planned Add/Modify/Delete list and waits for
  confirmation. `Replacement: False` means a resource is updated in place and keeps its ID.
- **IaC over the console:** the template is repeatable, reviewable, tested and deleted as one
  unit. Changing managed resources by hand causes drift, so the console is for looking only.

**Choices:**
- **Lite tier, set explicitly:** new pools default to the pricier Essentials tier. Lite is
  free up to 10,000 monthly active users.
- **Admin-only user creation:** no public sign-up, so strangers can't create accounts or make
  Cognito send email. Synthetic users come from a script. To be revisited for the attendee
  portal.
- **Security settings:** email sign-in (case-insensitive), 12-character minimum password,
  optional authenticator-app MFA (SMS costs money), identical errors for "no such user" and
  "wrong password", 60-minute access tokens, revocable refresh tokens.
- **Plain CloudFormation:** there's no code to package, so no SAM transform. `sam deploy` still
  deploys it, so every stack deploys the same way.

**Problems hit:**
- **The first deploy wrote the issuer URL as `https://https://cognito-idp...`.** The template
  assumed Cognito's `ProviderURL` attribute had no scheme, but it already includes `https://`.
  Every JWT authorizer would have rejected every token, because `iss` must match exactly. The
  test had encoded the same wrong assumption, so it passed. Fixed with
  `!GetAtt UserPool.ProviderURL`, redeployed (change set: one in-place Modify), and the test
  now asserts the corrected form. Lesson: template tests check intent; only the deployed
  values prove behaviour. The next step adds a token check against the real pool.
- **VS Code's YAML extension flags `!Ref`/`!Sub` as unknown tags.** These are false alarms;
  `sam validate --lint` is the real check.

**Cost:** ≈ $0/month. Cognito Lite is free at this size, the bus is free with nothing
published, and standard SSM parameters and CloudFormation are free.

**Verified:** 22 tests and `sam validate --lint` pass. The stack shows `UPDATE_COMPLETE`. The
SSM parameters hold the right values, with a single `https://` in the issuer. The pool shows
the Lite tier, admin-only sign-up and optional MFA, and all three groups exist.

---

## Step 3b: Synthetic test users and an end-to-end token check

**Built:** `scripts/seed_users.py` and `scripts/synthetic_users.py`, which create five
synthetic users in the dev pool. Also `tests/e2e/test_cognito_tokens.py`, 10 tests that
sign those users in and verify their real tokens. Both use a root-level `.venv`
(`requirements-dev.txt`, `pyproject.toml`).

**Why:** the services trust only what API Gateway's JWT authorizer checks: signature, `iss`,
audience and expiry. Step 3 showed that template tests can encode a wrong assumption (the
`https://https://` issuer). These tests check the *deployed* pool the same way the authorizer
will, before any service depends on it.

**Users:** `attendee1`, `attendee2`, `organiser1`, `organiser2` and `staff1`, all
`@example.com` (a domain reserved for examples, so no real person is involved). Each has
exactly one group. The second attendee and organiser exist for the "someone else's
resource" 403 tests.

**Concepts:**
- **SSM SecureString:** a parameter encrypted at rest with a KMS key. The AWS-managed `aws/ssm`
  key is free. The test password is generated randomly, stored only there, and read back by
  the script and the tests. It never appears in the repo, a file, shell history or output.
  CloudFormation can't create SecureStrings, so the parameter lives outside the stack and
  `seed_users.py --delete` removes it.
- **JWKS:** a user pool publishes its public signing keys at
  `<issuer>/.well-known/jwks.json`. Verifying a token means checking its signature with
  those keys, then its claims. PyJWT does exactly what API Gateway does.
- **Access token vs ID token:** an access token has `client_id` (no `aud`), and that's what the
  authorizer checks as the audience. An ID token has `aud` equal to the client ID, plus `email`.
  APIs receive access tokens.
- **Admin-created users:** `MessageAction=SUPPRESS` sends no invitation email, and
  `admin_set_user_password(Permanent=True)` skips the forced password change.

**Choices:**
- **Idempotent seeding:** re-running repairs passwords and group membership instead of failing.
- **The script only accepts `--env dev`,** so synthetic users can't be seeded into prod.
- **One module defines the users** for both the script and the tests, so they can't disagree.
- **Named `synthetic_users.py`, not `test_users.py`,** because pytest treats `test_*.py`
  files as test modules.

**What the tests prove against the real pool:** for each user, the access token's signature
verifies, `iss` equals the SSM issuer URL exactly, `client_id` equals the app client ID and
`cognito:groups` is right. The ID token's audience is the client. Every user has a distinct
`sub`. A wrong password and an unknown user get the same `NotAuthorizedException`. The
plain-password flow is refused with `InvalidParameterException`, so the step 3 security
setting is confirmed on the live pool, not just in the template.

**Problems hit:**
- **boto3 couldn't use `aws login` credentials** (`MissingDependencyException: botocore[crt]`).
  The CLI bundles the AWS Common Runtime but the Python SDK doesn't. Fixed with
  `boto3[crt]` in `requirements-dev.txt`.

**Cost:** ≈ $0. Five monthly active users on the Lite tier (free up to 10,000), and one
standard SecureString with the AWS-managed key (KMS calls well inside the free 20,000 per
month).

**Verified:** `seed_users.py` created all 5 users (`CONFIRMED`; groups 2/2/1); 10 e2e tests
passed; the password parameter is a `SecureString`.

---

## Step 4: Catalogue deployed to AWS, with end-to-end smoke tests

**Built:** `services/catalogue/samconfig.toml` and `tests/e2e/test_catalogue_api.py`. The
Catalogue is now deployed as stack `tessera-dev-catalogue`: table, function, IAM role, HTTP
API with the JWT authorizer, log groups, and the SSM API URL. This is the first real service
running in AWS.

**Concepts:**
- **What `sam build` does:** it reads the template, chooses AWS's build image for the runtime
  and architecture (`build-python3.12:latest-arm64`), and runs pip inside it against `src/`.
  The code and Linux/ARM libraries land in `.aws-sam/build/`. Docker is needed only for this
  build: the zip must contain binaries for Lambda's OS and CPU (pydantic-core is compiled),
  which a Windows pip install wouldn't produce. GitHub Actions will take this over in Phase 4.
- **What `sam deploy` does:** it zips the build, uploads it to S3, swaps `CodeUri` for the S3
  address, then creates and runs a change set. `resolve_s3 = true` let SAM create its own
  bucket (stack `aws-sam-cli-managed-default`). Its odd name is CloudFormation auto-naming:
  stack name + logical ID + a random suffix, because bucket names are global across all accounts.
- **`CAPABILITY_IAM`:** an explicit acknowledgement that the stack creates IAM resources (the
  execution role). It's set in `samconfig.toml`.
- **Idle costs almost nothing:** Lambda, API Gateway and on-demand DynamoDB bill per request.
  Only storage (PITR, logs, the S3 artifacts) bills while idle, at fractions of a cent. There's
  nothing to "pause"; `sam delete` removes everything, and a redeploy takes about 2 minutes.

**What the smoke tests prove against the deployed API (with real Cognito tokens):**
- `/v1/health` is public. No token gets API Gateway's own 401; a forged token gets 401.
- `X-Correlation-Id` sent by the client comes back and appears in every log line.
- An attendee gets 403 `FORBIDDEN` when creating events.
- **Full lifecycle:**
  - organiser1 creates a DRAFT (201 + `Location`);
  - the attendee and organiser2 get 404 on it;
  - organiser1 publishes it, and everyone can see it;
  - organiser2 gets 403 `NOT_EVENT_OWNER` on PATCH;
  - it appears in the attendee's browse list and in organiser1's `/organisers/me/events`, not
    organiser2's.
- The test deletes its events from the table directly afterwards (dev only).

**Observed in AWS:**
- **Access log:** the 401 line has `authorizerError: "missing: token not provided"`, so it was
  rejected before Lambda ran.
- **Function logs:** one JSON line per request with `correlationId`, path only, and no IPs.
- **Latency:** a cold start of about 1.4 s (`Init Duration`) on the first request; warm
  requests about 75 ms at API Gateway.
- **The table:** PITR `ENABLED`, and empty after the tests.

**Problems hit and known limitations:**
- **API Gateway's 401 body is `{"message":"Unauthorized"}`,** not our error format. HTTP APIs
  can't customise authorizer responses (REST APIs can). Accepted, and asserted in the test so
  a change would be noticed.
- **A CloudWatch log search seemed to find nothing.** Windows PowerShell 5.1 strips embedded
  double quotes from arguments to native programs, which broke the filter pattern. The logs
  were fine. For JSON logs, use `{ $.correlationId = "..." }` patterns, or the console's Logs
  Insights.
- **Log noise:** `mangum.http` repeats each request and `botocore.credentials` logs at INFO.
  To be quietened in the next step.
- **The SAM-managed artifact bucket keeps every deploy's zip forever** (versioning, no
  lifecycle rule). It will be replaced by our own bucket in the shared stack.

**Cost:** about $0.00–0.02/month: PITR and S3 artifact storage, fractions of a cent each.
Everything else is per request and within free tiers.

**Verified:** the change set had 10 `+ Add` rows and the stack shows `CREATE_COMPLETE`. All 16
e2e tests passed on the first run (10 Cognito, 6 Catalogue). Logs, PITR and table cleanup were
checked in AWS.

---

## Step 4b: Own artifacts bucket, deploy script, quieter logs

**Built:**
- **An S3 artifacts bucket in the shared stack** (`tessera-<env>-artifacts-<account>-<region>`),
  with its bucket policy and the SSM parameter `/tessera/<env>/artifacts/bucket-name`.
- **`scripts/deploy.ps1`** (`shared` | `catalogue`).
- **Quieter third-party loggers** in the Catalogue.
- **The SAM-managed bucket stack was removed.** ADR 0002 gained an Amendments section.

**Why:**
- **The SAM-managed bucket turned on versioning with no lifecycle rule,** so every deploy's
  zip stayed forever, and it wasn't tagged as part of Tessera.
- **Our bucket is defined in IaC, tested and capped.** It lives in the shared stack because
  every service uses it and none owns it (ADR 0002).

**Concepts:**
- **Global bucket names:** S3 bucket names are unique across all AWS accounts. CloudFormation
  auto-names add a random suffix (`...-samclisourcebucket-czm8iguivi6j`); adding the account
  ID and region gives a readable name that is still unique.
- **Bucket policy (resource-based policy):** attached to the bucket, and it applies to every
  caller. Ours is a single explicit `Deny` when `aws:SecureTransport` is false. An explicit Deny
  beats any Allow in AWS's policy evaluation, so no IAM permission can override it.
- **Public access block + `BucketOwnerEnforced`:** the bucket can't be made public, whatever a
  later policy says. ACLs (the older per-object permission system) are switched off.
- **Lifecycle rule:** objects expire after 90 days. Not shorter: rolling back a failed update
  needs the *previous* deploy's zip. Unfinished multipart uploads are cleaned up after 1 day.
- **Change set details: `Static` vs `Dynamic`.** The Catalogue redeploy listed `CatalogueApi`
  as Modify. `describe-change-set` showed `Body`, `Evaluation: Dynamic`, caused by
  `CatalogueFunction.Arn`. The API definition references the function's ARN, and CloudFormation
  can't prove in advance that an updated function keeps its ARN. A code update never changes
  it, so the API was untouched. Lesson: read the details and the cause, not just the row count.

**Choices:**
- **The bucket name includes the account ID, so it stays out of committed config.**
  `samconfig.toml` no longer has `resolve_s3`, which means a plain `sam deploy` refuses to run.
  `deploy.ps1` checks the caller identity, reads the bucket from SSM, and runs `sam build` and
  `sam deploy --s3-bucket ...`, stopping at the first failure (PowerShell's
  `$ErrorActionPreference` doesn't cover exit codes from programs like `sam`, so the script
  checks `$LASTEXITCODE` itself).
- **Quieter loggers:** `mangum`, `botocore`, `boto3` and `urllib3` are set to WARNING. Mangum
  repeated our access line ("GET /v1/events 200") and botocore logged "Found credentials".

**Problems hit:**
- **Docker Desktop's engine stopped responding** (`500 Internal Server Error ... check if the
  server supports the requested API version`), although the app was open and its WSL VMs
  were running. The backend log showed the real cause: `connect tcp 192.168.65.7:2375: no
  route to host`, meaning the network link into the engine VM was broken. The "API version"
  wording was misleading. The tray "Restart" didn't restart the processes (their start time
  was unchanged). Fixed by fully restarting Docker Desktop, with `wsl --shutdown` if needed.
  The installed version (4.30, June 2024) is old, and updating it is advisable.
- **`deploy.ps1` stopped at the failed `sam build`, so nothing was half-deployed.**
- **The SAM-managed bucket was deleted before the Catalogue moved off it.** For about an hour,
  the live stack referenced a zip that no longer existed. That's harmless unless an update
  fails and needs to roll back, which is exactly why the new bucket keeps zips for 90 days.
  Order matters: redeploy onto the new bucket first, then delete the old one.

**Cost:** unchanged, ≈ $0.00–0.02/month. The old bucket's storage is gone, and the new one is
capped by its expiry rule.

**Verified:**
- **Tests and checks:** 29 shared-stack tests, 106 Catalogue tests and `sam validate --lint`
  for both templates pass.
- **Change sets:** the shared stack showed 3 `+ Add`. The Catalogue showed `CatalogueFunction`
  Modify (`Static`, new code) and `CatalogueApi` Modify (`Dynamic`, ARN reference), both
  `Replacement: False`.
- **In AWS:** the deployed function's code comes from the new bucket. All 16 e2e tests passed.
  Logs since the redeploy come only from the `catalogue` logger. The managed stack is
  `DELETE_COMPLETE`, and the new bucket is the only one in the account.

---

## Step 5a: Frontend foundation: React + TypeScript + Mantine, split-view layout

**Built:** the app in `frontend/`, ADR 0005, and `docs/design/ui-style.md`. It contains:
- **Stack:** Vite, React 19, TypeScript 5.9, Mantine 9, TanStack Query, React Router.
- **Shell:** a slim header with navigation and a light/dark toggle.
- **Pages:** browse events and My events, both built on a **split view** (list + detail pane),
  plus a create/edit form and a 404 page.
- **Mosaic covers:** generated per event.
- **A typed Catalogue client** generated from `openapi.yaml`.

The pages use clearly labelled **sample data** until sign-in (5b) and the live API (5c/5d).

**How the decisions were made:** after the first scaffold I'd chosen the libraries myself,
without discussing them; that was pointed out, and we went through each decision:
- **Mantine** over plain CSS, Tailwind or shadcn, for ready-made accessible forms, tables,
  dates and modals with theming.
- **TanStack Query** over hand-written fetching.
- **React Router** over TanStack Router: the industry standard, with typed routes as the
  trade-off.
- **One app with role-aware navigation.**

A **design study in Google Stitch** produced every screen at desktop and mobile size. Its
tokens (deep blue `#004FAD`, blue-tinted neutrals, an amber accent, 4–24px spacing) became the
Mantine theme. Its screens were corrected where they contradicted the API: no Edit on
cancelled events, capacity locked only after publishing, a cancelled state on the details
page.

"Less whitespace" first sounded like "make everything smaller". It actually meant **put empty
space to work**. Hence the split view: the selected event fills the right pane, and an idle
pane shows a summary rather than a blank box. Filters and counts sit above lists, and row
actions appear on hover.

**Concepts:**
- **Single-page app:** one HTML page plus a JS bundle. React renders each view and `fetch`es
  the APIs. `npm run build` writes static files for S3.
- **Typed client from OpenAPI:** Python models → `openapi.yaml` → TypeScript types
  (`openapi-typescript`) → `openapi-fetch` calls, so a backend change breaks the frontend
  build instead of failing in the browser. `npm run check:api` catches a forgotten
  regeneration.
- **Routing state in the URL:** `/events/:eventId` and `/organiser/events/:eventId` choose what
  the detail pane shows, so refresh, links and the back button work.
- **`VITE_*` config:** only prefixed variables reach the bundle, and everything in a bundle is
  public, so they hold IDs, never secrets.
- **Deterministic generated art:** an FNV-1a hash of the event ID seeds a small random-number
  generator (mulberry32), so the same event always gets the same mosaic and nothing is stored.
- **React purity:** components must give the same output for the same input. The linter
  rejected `Date.now()` during render, so time-dependent filtering moved into event handlers.

**Choices:**
- **Times are shown in the viewer's local time with the zone offset**
  (`12 Jul 2027, 19:30 GMT+5:30`); events have no venue time zone yet.
- **Fonts:** Plus Jakarta Sans + JetBrains Mono, **self-hosted** via `@fontsource`, so no
  request goes to Google Fonts. **Icons:** Tabler, imported per icon.
- **Covers:** generated mosaics now (free). **Unsplash photos are planned as step 5e,** after
  sign-in and the live organiser console: an organiser-only backend search proxy with the key
  in SSM, the photo saved on the event, attribution, and the mosaic as fallback. Organiser
  photo upload (S3 presigned URLs) is on the to-do list.
- **The UI mirrors server rules** (hides Edit on cancelled events, locks capacity) but never
  replaces them.

**Problems hit:**
- **`npm create vite@latest web -- --template react-ts` produced a non-React app.** Windows
  PowerShell removes a bare `--`, so npm ate `--template`. Fixed by quoting it: `'--'`.
- **`openapi-typescript` requires TypeScript 5** (`peer typescript@"^5.x"`), but create-vite
  now defaults to TypeScript 7, the native compiler without the JS API. Pinned 5.9 rather than
  forcing the install.
- **Mantine in jsdom needs stubs** for `matchMedia`, `ResizeObserver` and `document.fonts`
  (the auto-growing textarea).
- **Node's ICU formats UTC as `GMT+0`** where browsers show `GMT`; it's normalised.
- **The bundle is ~215 KB gzipped** (Mantine + dates + router + query). Code splitting is
  planned when hosting.

**Cost:** none. Everything runs locally.

**Verified:** `tsc` clean, oxlint clean (warnings fail), 17 Vitest tests pass:
- redirect and placeholder pane;
- selecting an event fills the detail pane;
- search filtering;
- no Edit on cancelled events, Publish only on drafts;
- capacity locked for published events;
- form validation messages;
- 404;
- date formatting in three zones;
- mosaic determinism;
- config validation;
- correlation IDs.

`check:api` passes and the production build succeeds.