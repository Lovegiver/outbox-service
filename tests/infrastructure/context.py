from __future__ import annotations

from dataclasses import dataclass
from fastapi.testclient import TestClient
from httpx import Response
from sqlalchemy.orm import Session
from typing import Optional

from tests.infrastructure.assertions import TestAssertions
from tests.infrastructure.auth import AuthTestHelper
from tests.infrastructure.object_factory import ObjectFactory
from tests.infrastructure.probe import Probe
from tests.infrastructure.seed import Seed


@dataclass
class TestContext:
    __test__ = False

    client: TestClient
    db_session: Session
    factory: ObjectFactory
    probe: Probe
    auth: AuthTestHelper
    seed: Seed
    assertions: TestAssertions
    last_response: Optional[Response] = None
    request_headers: Optional[dict] = None
