from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompiledProcessingPlan:
    """
    Runtime-ready analytical processing plan.
    """

    processing_chain_id: int
    processing_plan_id: int
    metric_definition_id: int
    metric_definition_version_id: int
    position: int
    compiled_plan_json: dict


@dataclass(frozen=True)
class CompiledProcessingSnapshot:
    """Exact immutable ProcessingChain selected for one Event."""

    processing_chain_id: int
    plans: tuple[CompiledProcessingPlan, ...]
