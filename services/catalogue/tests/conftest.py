import uuid
from datetime import UTC, datetime, timedelta

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_aws

from app.dependencies import get_repository
from app.main import create_app
from app.models import Event, EventStatus, Venue
from app.repository import BY_ORGANISER, BY_STATUS_START, EventRepository


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
    return application


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
