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



from tests.infrastructure.object_factory import ObjectFactory  # noqa: E402
from tests.infrastructure.probe import Probe  # noqa: E402


@pytest.fixture
def factory(
    db_connection: Connection,
) -> ObjectFactory:
    return ObjectFactory(db_connection)


@pytest.fixture
def probe(
    db_connection: Connection,
) -> Probe:
    return Probe(db_connection)



from tests.infrastructure.auth import AuthTestHelper  # noqa: E402

@pytest.fixture
def auth() -> AuthTestHelper:
    return AuthTestHelper()



from tests.infrastructure.seed import Seed  # noqa: E402

@pytest.fixture
def seed(
    factory: ObjectFactory,
) -> Seed:
    return Seed(factory)



from tests.infrastructure.assertions import TestAssertions  # noqa: E402

@pytest.fixture
def assertions(
    probe: Probe,
) -> TestAssertions:
    return TestAssertions(probe)



from tests.infrastructure.context import TestContext  # noqa: E402

@pytest.fixture
def ctx(
    client: TestClient,
    db_session: Session,
    factory: ObjectFactory,
    probe: Probe,
    auth: AuthTestHelper,
    seed: Seed,
    assertions: TestAssertions,
) -> TestContext:
    return TestContext(
        client=client,
        db_session=db_session,
        factory=factory,
        probe=probe,
        auth=auth,
        seed=seed,
        assertions=assertions,
    )



from tests.bdd.registry import StepRegistry, create_step_registry  # noqa: E402

@pytest.fixture
def step_registry() -> StepRegistry:
    return create_step_registry()

