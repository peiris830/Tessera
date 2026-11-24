import uuid
from datetime import UTC, datetime, timedelta

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.auth import Caller, get_caller
from app.dependencies import get_repository
from app.main import create_app
from app.models import Event, EventStatus, Venue
from app.repository import BY_ORGANISER, BY_STATUS_START, EventRepository

# Synthetic callers. ORGANISER owns events made by make_event() unless told otherwise.
ATTENDEE = Caller(user_id="att-0001", groups=frozenset({"attendee"}))
ORGANISER = Caller(user_id="org-0001", groups=frozenset({"organiser"}))
OTHER_ORGANISER = Caller(user_id="org-0002", groups=frozenset({"organiser"}))


@pytest.fixture(autouse=True)
def fake_aws_credentials(monkeypatch):
    """Fake credentials for every test, so nothing can ever reach a real AWS account."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-1")


def create_events_table(dynamodb, name: str):
    """Mirrors the events table that the SAM template will define (step 2c)."""
    return dynamodb.create_table(
        TableName=name,
        BillingMode="PAY_PER_REQUEST",  # on-demand: pay per request, no capacity planning
        AttributeDefinitions=[
            {"AttributeName": "eventId", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
            {"AttributeName": "startsAt", "AttributeType": "S"},
            {"AttributeName": "organiserId", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "eventId", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": BY_STATUS_START,
                "KeySchema": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "startsAt", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": BY_ORGANISER,
                "KeySchema": [
                    {"AttributeName": "organiserId", "KeyType": "HASH"},
                    {"AttributeName": "startsAt", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )


@pytest.fixture
def repo():
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="eu-west-1")
        yield EventRepository(create_events_table(dynamodb, "test-events"))


@pytest.fixture
def app(repo):
    application = create_app()
    application.dependency_overrides[get_repository] = lambda: repo
    # Stands in for API Gateway's verified JWT claims. Default: a signed-in attendee.
    application.dependency_overrides[get_caller] = lambda: ATTENDEE
    return application


@pytest.fixture
def act_as(app):
    """act_as(ORGANISER) switches the caller; act_as(None) means no identity (-> 401)."""

    def _act_as(caller: Caller | None) -> None:
        if caller is None:
            app.dependency_overrides.pop(get_caller, None)  # real extraction: no claims
        else:
            app.dependency_overrides[get_caller] = lambda: caller

    return _act_as


@pytest.fixture
def client(app):
    return TestClient(app)


def make_event(
    *,
    starts_in: timedelta = timedelta(days=7),
    status: EventStatus = EventStatus.PUBLISHED,
    title: str = "Synthetic Jazz Night",
    organiser_id: str = "org-0001",
) -> Event:
    now = datetime.now(UTC)
    return Event(
        event_id=str(uuid.uuid4()),
        organiser_id=organiser_id,
        title=title,
        description="A synthetic test event.",
        venue=Venue(name="Test Hall", city="Testville"),
        starts_at=now + starts_in,
        capacity=100,
        status=status,
        created_at=now,
        updated_at=now,
    )
