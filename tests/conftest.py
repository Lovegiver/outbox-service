import os
import sys
import pytest

from fastapi.testclient import TestClient
from pathlib import Path
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session
from typing import Generator


os.environ["OUTBOX_ENV"] = "test"

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from app.database import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def db_connection() -> Generator[Connection, None, None]:
    connection = engine.connect()
    transaction = connection.begin()

    try:
        yield connection
    finally:
        transaction.rollback()
        connection.close()


@pytest.fixture
def db_session(
    db_connection: Connection,
) -> Generator[Session, None, None]:
    session = Session(bind=db_connection)

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(
    db_session: Session,
) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()



from tests.probes.project_probe import ProjectProbe  # noqa: E402

@pytest.fixture
def project_probe(
    db_connection: Connection,
) -> ProjectProbe:
    """
    Provide a read-only project probe for database assertions.
    """
    return ProjectProbe(db_connection)


from tests.factories.project_factory import ProjectFactory  # noqa: E402

@pytest.fixture
def project_factory(
    db_connection: Connection,
) -> ProjectFactory:
    """
    Provide a SQL project factory for test setup.
    """
    return ProjectFactory(db_connection)


from tests.factories.event_type_factory import EventTypeFactory  # noqa: E402
from tests.probes.event_type_probe import EventTypeProbe  # noqa: E402

@pytest.fixture
def event_type_factory(
    db_connection: Connection,
) -> EventTypeFactory:
    return EventTypeFactory(db_connection)


@pytest.fixture
def event_type_probe(
    db_connection: Connection,
) -> EventTypeProbe:
    return EventTypeProbe(db_connection)


from tests.infrastructure.object_factory import ObjectFactory  # noqa: E402

@pytest.fixture
def object_factory(
    db_connection: Connection,
) -> ObjectFactory:
    return ObjectFactory(db_connection)