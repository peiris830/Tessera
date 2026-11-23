# ADR 0001: Serverless microservices, one SAM stack and one DynamoDB table per service

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

Tessera has to show microservice design (independent services, clear ownership, async
communication) while staying cheap enough for a personal AWS account. Traffic is low most of
the time, with spikes at event launches.

## Decision

- Each service is a FastAPI app on **AWS Lambda** behind an **API Gateway HTTP API**, deployed
  as its **own SAM stack**.
- Each service owns **one DynamoDB table** (on-demand billing). No service reads another
  service's table; services communicate only via REST, SQS or EventBridge.
- Identity is a shared **Cognito** user pool, with tokens validated by API Gateway's JWT
  authorizer. Role and ownership checks happen in service code.

## Alternatives considered

- **Containers on ECS/Fargate:** closer to "classic" microservices, but tasks bill while idle
  and need networking setup (VPC, load balancer). That's too costly and complex for the goal.
- **One shared database:** simpler queries, but it couples services together and undermines
  the microservice boundary this project is meant to show.
- **API Gateway REST API:** more features (usage plans, request validation), but it costs more
  and needs more configuration. HTTP API's JWT authorizer covers our needs.

## Consequences

- Close to zero cost when idle, and scales automatically during launch rushes.
- Correctness depends on DynamoDB conditional writes, not SQL transactions across tables.
- Cross-service queries are impossible by design. Analytics comes from the event-driven data
  lake (Phase 3).
- Cold starts add latency to the first request after idle time. That's acceptable here.
- More stacks to deploy. CI/CD (Phase 4) will automate this.
