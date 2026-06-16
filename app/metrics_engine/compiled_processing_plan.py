from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CompiledProcessingPlan:
    """
    Runtime-ready analytical processing plan.
    """

    processing_chain_id: int
    metric_definition_id: int
    metric_definition_version_id: int
    compiled_plan_json: dict