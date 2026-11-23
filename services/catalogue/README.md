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

*Not implemented yet.* Will contain `app/`, `tests/`, `openapi.yaml`, `template.yaml`.
