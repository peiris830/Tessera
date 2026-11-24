"""Domain and API models for events.

`Event` is the internal model (snake_case, includes organiser_id).
`EventOut` is what the public API returns (camelCase JSON, no organiser ID).
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator
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


class InputModel(CamelModel):
    """Base for request bodies.

    extra="forbid" rejects unknown fields, preventing "mass assignment": a client can't
    smuggle in fields the server owns, like organiserId or status.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Venue(InputModel):
    name: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=100)


def _require_future(value: datetime) -> datetime:
    if value <= datetime.now(UTC):
        raise ValueError("must be in the future")
    return value


# A reusable type: timezone-aware AND in the future.
FutureDatetime = Annotated[AwareDatetime, AfterValidator(_require_future)]


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


class EventCreate(InputModel):
    """POST /v1/events body. The server sets eventId, organiserId, status and timestamps."""

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    venue: Venue
    starts_at: FutureDatetime
    capacity: int = Field(gt=0, le=1_000_000)


class EventUpdate(InputModel):
    """PATCH /v1/events/{id} body. Only the fields sent are changed."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    venue: Venue | None = None
    starts_at: FutureDatetime | None = None
    capacity: int | None = Field(default=None, gt=0, le=1_000_000)

    @model_validator(mode="after")
    def _at_least_one_non_null_field(self) -> "EventUpdate":
        changes = self.model_dump(exclude_unset=True)
        if not changes:
            raise ValueError("at least one field must be provided")
        if any(value is None for value in changes.values()):
            raise ValueError("fields cannot be set to null")
        return self


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
