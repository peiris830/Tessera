# ADR 0004: Mock Payment is an internal HTTP API protected by IAM (SigV4)

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

Mock Payment stands in for an external payment provider. Only Reservation should be able to
call it; attendees must never be able to "pay" directly. It has to behave like a real HTTP
dependency, with delays, timeouts, error codes and malformed bodies, so that Reservation's
timeouts, retries and compensation can be tested properly.

## Decision

- Mock Payment is exposed through an **API Gateway HTTP API** whose routes use the
  **`AWS_IAM` authorizer**.
- The Reservation function's IAM role is granted `execute-api:Invoke` on Mock Payment's
  API ARN only. No other role is.
- Reservation signs each request with **AWS Signature Version 4 (SigV4)**, using the Lambda's
  temporary role credentials (via `botocore`'s signer with `httpx`).
- Unsigned or wrongly signed requests are rejected by API Gateway with `403` before the Lambda
  runs.

## Alternatives considered

- **Direct Lambda invoke (`lambda:InvokeFunction`):** simple and IAM-secured, but it isn't HTTP.
  There are no status codes, timeouts or malformed responses to handle, which defeats the
  purpose of a realistic mock.
- **API key or shared secret header:** a long-lived secret to store and rotate. It's weaker
  than short-lived IAM credentials, and API keys aren't available on HTTP APIs anyway.
- **Cognito machine-to-machine (client credentials) tokens:** realistic for third-party
  APIs, but Cognito charges for M2M tokens, and it adds token caching logic.
- **Public, unauthenticated endpoint:** unacceptable even for a mock.

## Consequences

- No secrets to manage; credentials are temporary and rotated by AWS.
- Reservation needs a small signing helper for outbound calls. The same helper can be reused
  for any future internal service-to-service call.
- Calling Mock Payment by hand (e.g. with curl) needs signed requests. For local
  development, the service runs with `uvicorn` without API Gateway, so no signing is needed.
