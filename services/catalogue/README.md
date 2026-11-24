# Catalogue service

**Owns:** `events` table (events, venues, capacity definitions).

## Planned endpoints (Phase 1)

| Method | Route | Who | Notes |
|---|---|---|---|
| GET | `/v1/health` | anyone | health check |
| GET | `/v1/events` | any signed-in user | browse/search published events |
| GET | `/v1/events/{eventId}` | any signed-in user | event detail incl. capacity |
| POST | `/v1/events` | organiser | create event; caller becomes owner |
| PATCH | `/v1/events/{eventId}` | owning organiser | 403 for other organisers |

**Publishes (Phase 3):** `EventCreated`.

## Status

- [x] 2a: skeleton: health check, correlation IDs, JSON logs, consistent error body, Lambda handler
- [x] 2b: DynamoDB model, repository, public read endpoints (`GET /v1/events`, `GET /v1/events/{eventId}`)
- [ ] 2c: role/ownership checks, create/update/organiser endpoints, OpenAPI spec, SAM template

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
| `app/events.py` | `/v1/events` routes |
| `tests/` | pytest suite, including a test invoking `handler` with an API Gateway event |
