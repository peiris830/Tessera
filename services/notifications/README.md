# Notifications service

Consumes domain events from EventBridge (e.g. `ReservationConfirmed`, `TicketIssued`) and sends
**simulated** attendee notifications (structured log lines, no real email/SMS). Deduplicates on
the event envelope's `eventId`. No public API.

*Not implemented yet.*
