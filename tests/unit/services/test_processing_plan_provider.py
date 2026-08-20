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


def test_unknown_or_unconfigured_event_scope_returns_no_plan() -> None:
    provider = ProcessingPlanProvider(
        processing_chain_repository=FakeProcessingChainRepository(None),
        processing_plan_repository=FakeProcessingPlanRepository([]),
    )

    assert provider.get_active_plans(10, 20) == []


def test_active_plan_without_compiled_payload_is_an_explicit_error() -> None:
    provider = ProcessingPlanProvider(
        processing_chain_repository=FakeProcessingChainRepository(
            SimpleNamespace(id=1)
        ),
        processing_plan_repository=FakeProcessingPlanRepository(
            [
                SimpleNamespace(
                    id=2,
                    metric_definition_id=3,
                    metric_definition_version_id=4,
                    compiled_plan_json=None,
                )
            ]
        ),
    )

    with pytest.raises(ProcessingPlanConfigurationError, match="no compiled plan"):
        provider.get_active_plans(10, 20)


def test_runtime_provider_returns_persisted_compiled_plan_without_rebuilding() -> None:
    compiled_payload = {"observations": [{"code": "orders_total"}]}
    provider = ProcessingPlanProvider(
        processing_chain_repository=FakeProcessingChainRepository(
            SimpleNamespace(id=1)
        ),
        processing_plan_repository=FakeProcessingPlanRepository(
            [
                SimpleNamespace(
                    id=2,
                    metric_definition_id=3,
                    metric_definition_version_id=4,
                    compiled_plan_json=compiled_payload,
                )
            ]
        ),
    )

    plans = provider.get_active_plans(10, 20)

    assert len(plans) == 1
    assert plans[0].compiled_plan_json is compiled_payload
