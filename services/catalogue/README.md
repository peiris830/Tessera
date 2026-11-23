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
- [ ] 2b: DynamoDB model + `/v1/events` endpoints
- [ ] 2c: role/ownership checks, OpenAPI spec, SAM template

## Local development (PowerShell, from this folder)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

pytest                     # run tests
ruff check . ; ruff format --check .
uvicorn app.main:app --reload --port 8001   # then open http://127.0.0.1:8001/docs
```

## Layout

| Path | Purpose |
|---|---|
| `app/main.py` | FastAPI app, middleware, routes; `handler` is the Lambda entry point (Mangum) |
| `app/correlation.py` | `X-Correlation-Id` validation/generation, stored per request in a ContextVar |
| `app/logging_config.py` | JSON log formatter (adds service + correlation ID to every line) |
| `app/errors.py` | `APIError` and handlers producing `{"error": {code, message, correlationId}}` |
| `tests/` | pytest suite, including a test invoking `handler` with an API Gateway event |
