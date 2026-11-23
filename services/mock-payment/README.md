# Mock Payment service

A sandbox payment provider so we can test failure handling without real money. It never
handles real card data and owns no persistent data.

## Planned endpoints

| Method | Route | Notes |
|---|---|---|
| GET | `/v1/health` | health check |
| POST | `/v1/payments` | charge (simulated) |
| POST | `/v1/refunds` | refund (Phase 2) |

Behaviour will be configurable (e.g. via environment variables): artificial delay, failure
rate, and malformed responses. This lets Reservation's timeouts, retries and compensation be
tested.

*Not implemented yet.* Called only by Reservation (internal).
