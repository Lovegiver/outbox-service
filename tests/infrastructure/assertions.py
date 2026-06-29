from __future__ import annotations

from fastapi.testclient import TestClient
from httpx import Response

from tests.domain.persisted_object import PersistedObject
from tests.infrastructure.probe import Probe


class TestAssertions:
    def __init__(self, probe: Probe):
        self.probe = probe

    def exists(
        self,
        table_probe,
        persisted: PersistedObject,
    ) -> None:
        assert table_probe.exists(persisted)

    def not_exists(
        self,
        table_probe,
        persisted: PersistedObject,
    ) -> None:
        assert not table_probe.exists(persisted)

    def http_ok(self, response: Response) -> None:
        assert response.status_code == 200

    def http_created(self, response: Response) -> None:
        assert response.status_code == 201

    def http_no_content(self, response: Response) -> None:
        assert response.status_code == 204

    def http_unauthorized(self, response: Response) -> None:
        assert response.status_code == 401

    def http_forbidden(self, response: Response) -> None:
        assert response.status_code == 403

    def http_not_found(self, response: Response) -> None:
        assert response.status_code == 404