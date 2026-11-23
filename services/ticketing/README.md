# Ticketing service

**Owns:** `tickets` table (tickets, scan state).

## Planned interface (Phase 1)

| Method | Route / trigger | Who | Notes |
|---|---|---|---|
| — | SQS `IssueTicket` consumer | system | idempotent: `attribute_not_exists(reservationId)` |
| GET | `/v1/health` | anyone | health check |
| GET | `/v1/tickets` | attendee | caller's own tickets (filter by `reservationId`) |
| GET | `/v1/tickets/{ticketId}` | owning attendee | `403` for others |
| POST | `/v1/tickets/{ticketId}/scan` | venue_staff | `ISSUED → USED`; second scan `409` |

Phase 2 adds QR codes and transfer.
**Publishes (Phase 3):** `TicketIssued`, `TicketTransferred`, `TicketScanned`.

*Not implemented yet.*
