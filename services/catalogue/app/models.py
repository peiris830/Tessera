"""Domain and API models for events.

`Event` is the internal model (snake_case, includes organiser_id).
`EventOut` is what the public API returns (camelCase JSON, no organiser ID).
"""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Serialises fields as camelCase in JSON (startsAt), accepts either case on input."""

    model_config = ConfigDict(
        alias_generator=to_camel, validate_by_name=True, validate_by_alias=True
    )


class EventStatus(StrEnum):
    DRAFT = "DRAFT"  # visible to its organiser only
    PUBLISHED = "PUBLISHED"  # browsable and bookable
    CANCELLED = "CANCELLED"  # still viewable (attendees may hold tickets), not bookable


class Venue(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)


class Event(BaseModel):
    event_id: str
    organiser_id: str  # Cognito `sub` of the owning organiser (synthetic user ID)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    venue: Venue
    starts_at: AwareDatetime  # timezone-aware; naive datetimes are rejected
    capacity: int = Field(gt=0, le=1_000_000)
    status: EventStatus
    created_at: AwareDatetime
    updated_at: AwareDatetime


class EventOut(CamelModel):
    event_id: str
    title: str
    description: str
    venue: Venue
    starts_at: datetime
    capacity: int
    status: EventStatus

    @classmethod
    def from_event(cls, event: Event) -> "EventOut":
        return cls(
            event_id=event.event_id,
            title=event.title,
            description=event.description,
            venue=event.venue,
            starts_at=event.starts_at.astimezone(UTC),
            capacity=event.capacity,
            status=event.status,
        )


class EventPage(CamelModel):
    items: list[EventOut]
    next_token: str | None = None
