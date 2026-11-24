# Catalogue service

**Owns:** `events` table (events, venues, capacity definitions).

## Endpoints

| Method | Route | Who | Notes |
|---|---|---|---|
| GET | `/v1/health` | anyone | liveness check |
| GET | `/v1/events` | any signed-in user | upcoming published events, soonest first; `limit`, `from`, `nextToken` |
| GET | `/v1/events/{eventId}` | any signed-in user | published/cancelled events; drafts only for their owner (others: 404) |
| POST | `/v1/events` | organiser | creates a DRAFT owned by the caller; `201` + `Location` |
| PATCH | `/v1/events/{eventId}` | owning organiser | partial update; capacity locked once published (`409 CAPACITY_LOCKED`) |
| POST | `/v1/events/{eventId}/publish` | owning organiser | DRAFT → PUBLISHED; must start in the future |
| GET | `/v1/organisers/me/events` | organiser | caller's own events, all statuses |

**Access rules:** no identity → `401`; wrong role → `403 FORBIDDEN`; can't see it (missing or
someone else's draft) → `404`; can see it but not yours → `403 NOT_EVENT_OWNER`; state forbids
the change → `409`. Identity comes only from API Gateway's verified JWT claims.

**Publishes (Phase 3):** `EventCreated`.

## Status

- [x] 2a: skeleton: health check, correlation IDs, JSON logs, consistent error body, Lambda handler
- [x] 2b: DynamoDB model, repository, public read endpoints
- [x] 2c: authentication/roles/ownership, organiser endpoints (create, update, publish, list own)
- [ ] 2d: OpenAPI spec, SAM template

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
uvicorn app.main:app --reload --port 8001   # then open http://127.0.0.1:8001/docs
```

Tests use **moto** (in-memory fake AWS) with fake credentials, so they never touch a real
account. Running the server locally serves `/v1/health`; the events endpoints need a real
table (`EVENTS_TABLE_NAME`) until a local DynamoDB option is added.

## Layout

| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI app, middleware, routes; `handler` is the Lambda entry point (Mangum) |
| `app/correlation.py` | `X-Correlation-Id` validation/generation, stored per request in a ContextVar |
| `app/logging_config.py` | JSON log formatter (adds service + correlation ID to every line) |
| `app/errors.py` | `APIError` and handlers producing `{"error": {code, message, correlationId}}` |
| `app/models.py` | `Event` (internal) and `EventOut`/`EventPage` (public API, camelCase) |
| `app/repository.py` | The only DynamoDB code: create (conditional), get, list published |
| `app/pagination.py` | Encode/decode the opaque `nextToken` |
| `app/dependencies.py` | `get_repository()`: the table client, overridden in tests |
| `app/auth.py` | `Caller` from API Gateway JWT claims; `get_caller` (401), `require_organiser` (403) |
| `app/events.py` | `/v1/events` routes: browse + organiser management |
| `app/organisers.py` | `/v1/organisers/me/events` |
| `tests/` | pytest suite, including a test invoking `handler` with an API Gateway event |
