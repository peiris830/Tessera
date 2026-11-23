# ADR 0003: Reservation creates the capacity counter on the first reservation for an event

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

Catalogue owns an event's **capacity definition**. Reservation owns **capacity consumption**:
a counter item `{eventId, capacity, held, confirmed}` in the `reservations` table, which is
updated atomically to prevent overselling. Reservation can't read the `events` table, so it
needs another way to learn the capacity. Phase 1 has no EventBridge consumers yet.

## Decision

On `POST /v1/reservations` for an event:

1. Try the atomic counter update
   (`ConditionExpression: held + confirmed < capacity`; increments `held`).
2. If the counter item **doesn't exist yet**, call Catalogue `GET /v1/events/{eventId}` and
   create the counter with `PutItem` + `ConditionExpression: attribute_not_exists(PK)`.
   If two first requests race, one put wins. The loser gets
   `ConditionalCheckFailedException`, ignores it and carries on.
3. Retry the counter update from step 1.

The call to Catalogue forwards the caller's own JWT. Browsing events is something any
signed-in user may do anyway, so no extra service credentials are needed.

## Alternatives considered

- **Create the counter from an `EventCreated` event:** the cleanest long-term option, but it
  needs the EventBridge pipeline (Phase 3) and handling for events that arrive late. We'll
  switch to it, or add it alongside, once domain events exist.
- **Read Catalogue on every reservation:** this puts Catalogue on the hot path of every
  purchase. It adds latency, and a Catalogue outage would stop all sales.
- **Reservation reads the `events` table directly:** this breaks the service boundary rule.

## Consequences

- Catalogue is called once per event, not once per reservation. After the first booking,
  sales carry on even if Catalogue is down. If Catalogue is down for an event's *first*
  booking, that request returns `503`.
- The counter holds a **snapshot** of capacity. In Phase 1, capacity changes after the first
  reservation aren't propagated. Catalogue should reject them, or we accept the snapshot.
  Propagation comes with `EventUpdated` events later.
- The race between two "first" requests is handled by the conditional put, so it's covered by
  the same no-overselling test.
