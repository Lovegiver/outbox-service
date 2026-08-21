from __future__ import annotations

import pytest

from app.models.processing_chain import ProcessingChain
from app.models.processing_plan import ProcessingPlan
from app.models.schema_definition import SchemaDefinition
from app.services.processing_chain_activation_service import (
    ProcessingChainActivationService,
)
from app.services.processing_chain_builder_service import (
    PreparedProcessingChain,
    PreparedProcessingPlan,
)
from app.services.processing_chain_errors import (
    ProcessingChainIncompleteError,
    ProcessingChainNotFoundError,
)


COMPILED = {"compiler_version": "1.0", "observations": []}


class Session:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0
        self.refreshed = []

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def flush(self):
        self.flushes += 1

    def refresh(self, value):
        self.refreshed.append(value)


class Schemas:
    def __init__(self, schema):
        self.schema = schema
        self.lock_requests = []

    def find_by_id(self, _id, *, for_update=False):
        self.lock_requests.append(for_update)
        return self.schema


class Versions:
    def __init__(self, values=None):
        self.values = values or [object()]

    def find_latest_compatible_versions(self, **_kwargs):
        return self.values


class Chains:
    def __init__(self, active=None, candidate=None):
        self.active = active
        self.candidate = candidate
        self.next_version = 1

    def find_active(self, **_kwargs):
        return self.active

    def find_next_version_number(self, **_kwargs):
        return self.next_version

    def find_by_id(self, chain_id):
        if self.candidate is not None and self.candidate.id == chain_id:
            return self.candidate
        return None


class Plans:
    def __init__(self, plans=None):
        self.plans = plans or []

    def list_by_chain_id(self, _chain_id):
        return self.plans


class Builder:
    def __init__(self, prepared, persisted=None, fail_persist=False):
        self.prepared = prepared
        self.persisted = persisted
        self.fail_persist = fail_persist
        self.persist_calls = 0

    def prepare_chain(self, **_kwargs):
        return self.prepared

    def signature_for_chain(self, _chain_id):
        return self.prepared.signature

    def persist_chain(self, **_kwargs):
        self.persist_calls += 1
        if self.fail_persist:
            raise RuntimeError("plan persistence failed")
        return self.persisted


def _schema():
    value = SchemaDefinition(
        event_type_id=7,
        json_version_internal="1",
        json_schema={"type": "object"},
    )
    value.id = 30
    return value


def _chain(chain_id: int, *, status="DRAFT", active=False, version=1):
    value = ProcessingChain(
        event_type_id=7,
        schema_definition_id=30,
        version_number=version,
        status=status,
        is_active=active,
    )
    value.id = chain_id
    return value


def _prepared():
    return PreparedProcessingChain(
        event_type_id=7,
        schema_definition_id=30,
        plans=(
            PreparedProcessingPlan(
                metric_definition_id=10,
                metric_definition_version_id=20,
                compiled_plan_json=COMPILED,
            ),
        ),
    )


def _plan(compiled=COMPILED):
    value = ProcessingPlan(
        processing_chain_id=100,
        metric_definition_id=10,
        metric_definition_version_id=20,
        position=0,
        is_active=True,
        compiled_plan_json=compiled,
    )
    value.id = 200
    return value


def _service(*, active=None, candidate=None, plans=None, fail_persist=False):
    session = Session()
    schemas = Schemas(_schema())
    chains = Chains(active=active, candidate=candidate)
    builder = Builder(
        _prepared(),
        persisted=_chain(101, version=2 if active else 1),
        fail_persist=fail_persist,
    )
    effective_plans = [_plan()] if active is not None and plans is None else plans
    service = ProcessingChainActivationService(
        db=session,  # type: ignore[arg-type]
        processing_chain_repository=chains,  # type: ignore[arg-type]
        processing_plan_repository=Plans(effective_plans),  # type: ignore[arg-type]
        metric_definition_version_repository=Versions(),  # type: ignore[arg-type]
        schema_repository=schemas,  # type: ignore[arg-type]
        processing_chain_builder_service=builder,  # type: ignore[arg-type]
    )
    return service, session, schemas, builder


def test_first_rebuild_persists_and_activates_complete_snapshot() -> None:
    service, session, schemas, builder = _service()

    chain = service.rebuild_and_activate_chain(7, 30)

    assert chain.status == "ACTIVE"
    assert chain.is_active is True
    assert builder.persist_calls == 1
    assert schemas.lock_requests == [False, True]
    assert session.commits == 1
    assert session.rollbacks == 0


def test_identical_rebuild_reuses_active_chain_without_consuming_version() -> None:
    active = _chain(100, status="ACTIVE", active=True)
    service, session, _, builder = _service(active=active)

    chain = service.rebuild_and_activate_chain(7, 30)

    assert chain is active
    assert builder.persist_calls == 0
    assert session.commits == 1


def test_changed_rebuild_retires_old_chain_atomically() -> None:
    active = _chain(100, status="ACTIVE", active=True)
    service, session, _, builder = _service(active=active)
    builder.signature_for_chain = lambda _id: ()

    new_chain = service.rebuild_and_activate_chain(7, 30)

    assert active.status == "RETIRED"
    assert active.is_active is False
    assert new_chain.status == "ACTIVE"
    assert session.commits == 1


def test_persistence_failure_rolls_back_and_leaves_old_chain_active() -> None:
    active = _chain(100, status="ACTIVE", active=True)
    service, session, _, builder = _service(
        active=active,
        fail_persist=True,
    )
    builder.signature_for_chain = lambda _id: ()

    with pytest.raises(RuntimeError, match="plan persistence failed"):
        service.rebuild_and_activate_chain(7, 30)

    assert active.status == "ACTIVE"
    assert active.is_active is True
    assert session.commits == 0
    assert session.rollbacks == 1


def test_activate_candidate_rejects_unknown_chain() -> None:
    service, session, _, _ = _service()

    with pytest.raises(ProcessingChainNotFoundError):
        service.activate_chain(7, 30, 999)

    assert session.rollbacks == 1


@pytest.mark.parametrize(
    ("status", "plans", "message"),
    [
        ("INCOMPLETE", [_plan()], "not an activatable DRAFT"),
        ("DRAFT", [], "incomplete ProcessingPlans"),
        ("DRAFT", [_plan(None)], "incomplete ProcessingPlans"),
    ],
)
def test_activate_candidate_rejects_incomplete_snapshot(status, plans, message):
    candidate = _chain(100, status=status)
    service, session, _, _ = _service(candidate=candidate, plans=plans)

    with pytest.raises(ProcessingChainIncompleteError, match=message):
        service.activate_chain(7, 30, 100)

    assert candidate.is_active is False
    assert session.rollbacks == 1


def test_activate_candidate_replaces_old_scope_only_after_validation() -> None:
    active = _chain(99, status="ACTIVE", active=True)
    candidate = _chain(100, status="DRAFT", active=False, version=2)
    service, session, _, _ = _service(
        active=active,
        candidate=candidate,
        plans=[_plan()],
    )

    activated = service.activate_chain(7, 30, 100)

    assert activated is candidate
    assert candidate.status == "ACTIVE"
    assert candidate.is_active is True
    assert active.status == "RETIRED"
    assert active.is_active is False
    assert session.commits == 1
