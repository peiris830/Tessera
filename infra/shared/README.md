# Shared platform stack

SAM stack `tessera-<env>-shared` for resources used by all services (see
[ADR 0002](../../docs/adr/0002-shared-platform-stack.md)):

- Cognito user pool, app client and groups (`attendee`, `organiser`, `venue_staff`)
- EventBridge bus for domain events

It publishes IDs and ARNs to SSM Parameter Store under `/tessera/<env>/...` so service stacks
can reference them. Deploy it first and tear it down last.

*Not implemented yet.*
