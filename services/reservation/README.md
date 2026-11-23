# Reservation service

**Owns:** `reservations` table (holds, reservations, per-event capacity counters, waitlist).

## Planned endpoints (Phase 1)

| Method | Route | Who | Notes |
|---|---|---|---|
| GET | `/v1/health` | anyone | health check |
| POST | `/v1/reservations` | attendee | place a hold; `409` if sold out |
| GET | `/v1/reservations` | attendee | caller's own reservations |
| GET | `/v1/reservations/{id}` | owning attendee | `403` for others |
| POST | `/v1/reservations/{id}/confirm` | owning attendee | pay via Mock Payment, then enqueue ticket issuance |

Phase 2 adds hold expiry, cancellation/refund and waitlist promotion.

**Calls:** Catalogue (capacity), Mock Payment. **Sends:** `IssueTicket` to SQS.
**Publishes (Phase 3):** `HoldPlaced`, `HoldExpired`, `ReservationConfirmed`,
`ReservationCancelled`, `WaitlistPromoted`.

*Not implemented yet.*
