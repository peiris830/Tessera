"""DynamoDB access for the events table. The only module that talks to DynamoDB.

Table design (see docs/architecture.md):
  - Primary key:          eventId (partition key)
  - GSI by-status-start:  status (partition) + startsAt (sort) -> browse published, by date
  - GSI by-organiser:     organiserId (partition) + startsAt (sort) -> organiser's own events

Timestamps are stored as fixed-format UTC strings (2026-12-01T19:00:00Z) so that string
order equals time order, which is what makes startsAt usable as a sort key.
"""

from datetime import UTC, datetime
from typing import Any

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.models import Event, EventStatus, Venue
from app.pagination import InvalidPageTokenError

BY_STATUS_START = "by-status-start"
BY_ORGANISER = "by-organiser"
_START_KEY_FIELDS = {"eventId", "status", "startsAt"}


def to_iso(value: datetime) -> str:
    """Normalise to UTC, second precision, 'Z' suffix: lexicographically sortable."""
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class EventAlreadyExistsError(Exception):
    pass


class EventRepository:
    def __init__(self, table: Any) -> None:
        self._table = table  # a boto3 DynamoDB Table resource

    def create(self, event: Event) -> None:
        """Insert a new event; never overwrite an existing one."""
        try:
            self._table.put_item(
                Item=_to_item(event),
                # Condition expression: DynamoDB checks this atomically with the write.
                # If an item with this eventId already exists, the put is rejected.
                ConditionExpression="attribute_not_exists(eventId)",
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise EventAlreadyExistsError(event.event_id) from exc
            raise

    def get(self, event_id: str) -> Event | None:
        # Eventually consistent read (the default): cheaper, and may lag a write by
        # under a second, which is fine for browsing.
        item = self._table.get_item(Key={"eventId": event_id}).get("Item")
        return _from_item(item) if item else None

    def list_published(
        self, starts_from: str, limit: int, start_key: dict[str, Any] | None = None
    ) -> tuple[list[Event], dict[str, Any] | None]:
        """Published events starting at or after `starts_from`, soonest first.

        Returns (events, last_key). last_key is None when there are no more pages
        (DynamoDB may occasionally return a key whose next page turns out empty).
        """
        query: dict[str, Any] = {
            "IndexName": BY_STATUS_START,
            "KeyConditionExpression": Key("status").eq(EventStatus.PUBLISHED.value)
            & Key("startsAt").gte(starts_from),
            "Limit": limit,
        }
        if start_key is not None:
            _validate_start_key(start_key, starts_from)
            query["ExclusiveStartKey"] = start_key
        response = self._table.query(**query)
        events = [_from_item(item) for item in response.get("Items", [])]
        return events, response.get("LastEvaluatedKey")


def _validate_start_key(key: dict[str, Any], starts_from: str) -> None:
    """A client-supplied start key must be exactly a key this query could have produced."""
    if (
        set(key) != _START_KEY_FIELDS
        or not all(isinstance(v, str) for v in key.values())
        or key["status"] != EventStatus.PUBLISHED.value
        or key["startsAt"] < starts_from
    ):
        raise InvalidPageTokenError("start key does not match this query")


def _to_item(event: Event) -> dict[str, Any]:
    return {
        "eventId": event.event_id,
        "organiserId": event.organiser_id,
        "title": event.title,
        "description": event.description,
        "venue": {"name": event.venue.name, "city": event.venue.city},
        "startsAt": to_iso(event.starts_at),
        "capacity": event.capacity,
        "status": event.status.value,
        "createdAt": to_iso(event.created_at),
        "updatedAt": to_iso(event.updated_at),
    }


def _from_item(item: dict[str, Any]) -> Event:
    return Event(
        event_id=item["eventId"],
        organiser_id=item["organiserId"],
        title=item["title"],
        description=item.get("description", ""),
        venue=Venue(**item["venue"]),
        starts_at=item["startsAt"],
        capacity=int(item["capacity"]),  # boto3 returns DynamoDB numbers as Decimal
        status=item["status"],
        created_at=item["createdAt"],
        updated_at=item["updatedAt"],
    )
