# Catalogue service

**Owns:** `events` table (events, venues, capacity definitions).

## Endpoints

| Method | Route | Who | Notes |
|---|---|---|---|
| GET | `/v1/health` | anyone | liveness check |
| GET | `/v1/events` | anyone (no token) | upcoming published events, soonest first; `limit`, `from`, `nextToken` |
| GET | `/v1/events/{eventId}` | anyone (no token) | published/cancelled events only; drafts are `404` for everyone, owner included |
| POST | `/v1/events` | organiser | creates a DRAFT owned by the caller; `201` + `Location` |
| PATCH | `/v1/events/{eventId}` | owning organiser | partial update; capacity locked once published (`409 CAPACITY_LOCKED`) |
| POST | `/v1/events/{eventId}/publish` | owning organiser | DRAFT → PUBLISHED; must start in the future |
| GET | `/v1/organisers/me/events` | organiser | caller's own events, all statuses |
| GET | `/v1/organisers/me/events/{eventId}` | owning organiser | one of the caller's events, drafts included |

**CORS:** browsers may call the API from the origins in the `AllowedOrigins` template parameter
(default `http://localhost:5173`). Preflight `OPTIONS` requests go through a token-less route
and get an empty `204`; API Gateway adds the CORS headers.

**Access rules:** no identity on a protected route → `401`; wrong role → `403 FORBIDDEN`; can't see it (missing or
someone else's draft) → `404`; can see it but not yours → `403 NOT_EVENT_OWNER`; state forbids
the change → `409`. Identity comes only from API Gateway's verified JWT claims.

**Publishes (Phase 3):** `EventCreated`.

## Status

- [x] 2a: skeleton: health check, correlation IDs, JSON logs, consistent error body, Lambda handler
- [x] 2b: DynamoDB model, repository, public read endpoints
- [x] 2c: authentication/roles/ownership, organiser endpoints (create, update, publish, list own)
- [x] 2d: OpenAPI spec (generated, drift-tested), SAM template (table, function, API, logs)
- [x] 4: deployed to dev (`tessera-dev-catalogue`); e2e smoke tests in `tests/e2e/`
- [x] 5b-1: public browsing, owner draft route, CORS for the frontend

## Data model (`events` table)

| Key / index | Partition key | Sort key | Serves |
|---|---|---|---|
| Table | `eventId` | – | get one event |
| GSI `by-status-start` | `status` | `startsAt` | browse upcoming published events, soonest first |
| GSI `by-organiser` | `organiserId` | `startsAt` | an organiser's own events (2c) |

Timestamps are stored as `YYYY-MM-DDTHH:MM:SSZ` (UTC) so string order equals time order.
List endpoints paginate with an opaque `nextToken`; pass it back unchanged to get the next page.

## Local development (PowerShell, from this folder)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

pytest                     # run tests
ruff check . ; ruff format --check .
python scripts/export_openapi.py            # regenerate openapi.yaml after API changes
uvicorn app.main:app --reload --port 8001 --app-dir src   # then open http://127.0.0.1:8001/docs
```

## Build and deploy (AWS SAM)

```powershell
sam validate --lint              # check template.yaml (local, no AWS calls needed)
sam build                        # in AWS's Python 3.12 arm64 build image (needs Docker running)

# from the repo root: build + deploy (reads the artifacts bucket from SSM; shows the change
# set and asks before applying). samconfig.toml: stack tessera-dev-catalogue, us-east-1.
$env:AWS_PROFILE = "tessera-dev"
.\scripts\deploy.ps1 catalogue
sam delete --stack-name tessera-dev-catalogue   # teardown (deletes the table and its data)
```

Deploy the shared stack (`infra/shared`) first: this template reads its Cognito SSM
parameters. End-to-end tests for the deployed API live in `tests/e2e/` at the repo root.

Tests use **moto** (in-memory fake AWS) with fake credentials, so they never touch a real
account. Running the server locally serves `/v1/health`; the events endpoints need a real
table (`EVENTS_TABLE_NAME`) until a local DynamoDB option is added.

## Layout

Only `src/` is packaged into the Lambda (SAM `CodeUri: src/`).

| Path | Purpose |
|---|---|
| `src/requirements.txt` | Runtime dependencies (packaged) |
| `src/app/main.py` | FastAPI app, middleware, OpenAPI security; `handler` is the Lambda entry point |
| `src/app/correlation.py` | `X-Correlation-Id` validation/generation, stored per request in a ContextVar |
| `src/app/logging_config.py` | JSON log formatter (adds service + correlation ID to every line) |
| `src/app/errors.py` | `APIError`, error handlers, `ErrorResponse` schema for the spec |
| `src/app/models.py` | `Event` (internal), request bodies, `EventOut`/`EventPage` (public API) |
| `src/app/repository.py` | The only DynamoDB code: conditional create/update/publish, get, queries |
| `src/app/pagination.py` | Encode/decode the opaque `nextToken` |
| `src/app/dependencies.py` | `get_repository()`: the table client, overridden in tests |
| `src/app/auth.py` | `Caller` from API Gateway JWT claims; `get_caller` (401), `require_organiser` (403) |
| `src/app/events.py` | `/v1/events` routes: browse + organiser management |
| `src/app/organisers.py` | `/v1/organisers/me/events` |
| `template.yaml` | SAM template: table, function, HTTP API + JWT authorizer, log groups, SSM URL |
| `openapi.yaml` | Generated API spec (`scripts/export_openapi.py`); a test fails if it drifts |
| `tests/` | pytest suite; `tests/cfn.py` reads `template.yaml` so moto builds the same table |
| `requirements-dev.txt` | Local tools and test dependencies (not packaged) |
