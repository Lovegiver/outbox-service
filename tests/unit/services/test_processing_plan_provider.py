from types import SimpleNamespace

import pytest

from app.services.processing_plan_provider import (
    ProcessingPlanConfigurationError,
    ProcessingPlanProvider,
)


class FakeProcessingChainRepository:
    def __init__(self, active_chain) -> None:
        self.active_chain = active_chain

    def find_active(self, event_type_id: int, schema_definition_id: int):
        return self.active_chain


class FakeProcessingPlanRepository:
    def __init__(self, plans: list) -> None:
        self.plans = plans

    def list_active_by_chain_id(self, processing_chain_id: int) -> list:
        return self.plans


class FakeCompatibilityRepository:
    def __init__(self, compatible: bool = True) -> None:
        self.compatible = compatible

    def find_by_version_and_schema(self, **kwargs):
        return object() if self.compatible else None


def fake_plan(**overrides):
    values = {
        "id": 2,
        "processing_chain_id": 1,
        "metric_definition_id": 3,
        "metric_definition_version_id": 4,
        "position": 0,
        "compiled_plan_json": {"compiler_version": "1.0"},
        "metric_definition": SimpleNamespace(event_type_id=10),
        "metric_definition_version": SimpleNamespace(metric_definition_id=3),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def make_provider(active_chain, plans, *, compatible: bool = True):
    return ProcessingPlanProvider(
        processing_chain_repository=FakeProcessingChainRepository(active_chain),
        processing_plan_repository=FakeProcessingPlanRepository(plans),
        compatibility_repository=FakeCompatibilityRepository(compatible),
    )


def test_unknown_or_unconfigured_event_scope_returns_no_plan() -> None:
    provider = make_provider(None, [])

    assert provider.get_active_plans(10, 20) == []


def test_active_plan_without_compiled_payload_is_an_explicit_error() -> None:
    provider = make_provider(
        SimpleNamespace(id=1),
        [fake_plan(compiled_plan_json=None)],
    )

    with pytest.raises(ProcessingPlanConfigurationError, match="no compiled plan"):
        provider.get_active_plans(10, 20)


def test_runtime_provider_returns_persisted_compiled_plan_without_rebuilding() -> None:
    compiled_payload = {"compiler_version": "1.0", "observations": []}
    provider = make_provider(
        SimpleNamespace(id=1),
        [fake_plan(compiled_plan_json=compiled_payload)],
    )

    plans = provider.get_active_plans(10, 20)

    assert len(plans) == 1
    assert plans[0].compiled_plan_json is compiled_payload
    assert plans[0].processing_plan_id == 2


def test_active_chain_without_plans_is_an_explicit_error() -> None:
    provider = make_provider(SimpleNamespace(id=7), [])

    with pytest.raises(ProcessingPlanConfigurationError, match="no executable plans"):
        provider.get_active_snapshot(10, 20)


def test_runtime_provider_rejects_missing_schema_compatibility() -> None:
    provider = make_provider(
        SimpleNamespace(id=1),
        [fake_plan()],
        compatible=False,
    )

    with pytest.raises(ProcessingPlanConfigurationError, match="compatibility"):
        provider.get_active_snapshot(10, 20)
