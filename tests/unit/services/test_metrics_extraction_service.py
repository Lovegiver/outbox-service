from types import SimpleNamespace

from app.services.metrics_extraction_service import MetricsExtractionService

COMPILED = {
    "compiler_version": "1.0",
    "yaml_version": "1.0",
    "observations": [
        {
            "metric_code": "duration_seconds",
            "transform": "identity",
            "value": {
                "path": "$.duration_seconds",
                "json_type": "number",
                "required": True,
                "iterator_path": None,
            },
            "labels": [
                {
                    "name": "step",
                    "kind": "path",
                    "path": "$.step",
                    "json_type": "string",
                    "required": True,
                    "iterator_path": None,
                }
            ],
        }
    ],
}


def test_extract_for_plan_maps_all_runtime_trace_references() -> None:
    service = MetricsExtractionService()
    event = SimpleNamespace(
        id=3,
        project_id=1,
        event_type_id=2,
        payload={"duration_seconds": 28, "step": "extract"},
    )
    plan = SimpleNamespace(
        id=6,
        metric_definition_id=4,
        metric_definition_version_id=5,
        compiled_plan_json=COMPILED,
    )
    execution = SimpleNamespace(id=7, processing_chain_id=8)

    result = service.extract_for_plan(
        event=event,
        plan=plan,
        execution=execution,
    )

    assert len(result) == 1
    observation = result[0]
    assert observation.project_id == 1
    assert observation.event_type_id == 2
    assert observation.event_id == 3
    assert observation.metric_definition_id == 4
    assert observation.metric_definition_version_id == 5
    assert observation.processing_plan_id == 6
    assert observation.metric_plan_execution_id == 7
    assert observation.processing_chain_id == 8
    assert observation.observation_key == "observation:0:occurrence:0"
    assert observation.metric_code == "duration_seconds"
    assert observation.value == 28.0
    assert observation.dimensions_json == {"step": "extract"}
