from __future__ import annotations

from dataclasses import dataclass

from fastapi.testclient import TestClient

from tests.infrastructure.assertions import TestAssertions
from tests.infrastructure.auth import AuthTestHelper
from tests.infrastructure.object_factory import ObjectFactory
from tests.infrastructure.probe import Probe
from tests.infrastructure.seed import Seed


@dataclass(frozen=True)
class TestContext:
    client: TestClient
    factory: ObjectFactory
    probe: Probe
    auth: AuthTestHelper
    seed: Seed
    assertions: TestAssertions