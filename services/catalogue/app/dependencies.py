"""FastAPI dependencies.

Routes ask for an EventRepository via `Depends(get_repository)` instead of creating one, so
tests can swap in a repository backed by moto (`app.dependency_overrides`).
"""

import os
from functools import lru_cache

import boto3

from app.repository import EventRepository


@lru_cache
def get_repository() -> EventRepository:
    # Created once per Lambda execution environment and reused across warm invocations,
    # which also reuses the underlying HTTPS connection to DynamoDB.
    table = boto3.resource("dynamodb").Table(os.environ["EVENTS_TABLE_NAME"])
    return EventRepository(table)
