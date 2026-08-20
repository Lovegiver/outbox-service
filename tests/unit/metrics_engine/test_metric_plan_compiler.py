from copy import deepcopy

from app.metrics_engine.metric_plan_compiler import compile_metric_yaml_to_json
from app.metrics_engine.metric_yaml_validator import validate_metric_yaml


JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "amount": {"type": "number"},
        "country": {"type": "string"},
        "region": {"type": "string"},
        "discount": {"type": "number"},
    },
    "required": ["amount", "country", "region"],
}


def test_compile_metric_yaml_to_a_deterministic_complete_plan() -> None:
    metric_yaml = {
        "version": "1.0",
        "observations": [
            {
                "code": "revenue_total",
                "transform": "identity",
                "value_path": "$.discount",
                "labels": {
                    "region": "$.region",
                    "country": "$.country",
                },
            }
        ],
    }
    original = deepcopy(metric_yaml)
    validated = validate_metric_yaml(metric_yaml, JSON_SCHEMA)

    first = compile_metric_yaml_to_json(validated)
    second = compile_metric_yaml_to_json(validated)

    assert first == second
    assert metric_yaml == original
    assert first["compiler_version"] == "1.0"
    assert first["yaml_version"] == "1.0"
    observation = first["observations"][0]
    assert observation["metric_code"] == "revenue_total"
    assert observation["transform"] == "identity"
    assert observation["value"] == {
        "path": "$.discount",
        "json_type": "number",
        "required": False,
        "iterator_path": None,
    }
    assert [label["name"] for label in observation["labels"]] == [
        "country",
        "region",
    ]


def test_compile_constant_without_a_value_path() -> None:
    validated = validate_metric_yaml(
        {
            "version": "1.0",
            "observations": [
                {
                    "code": "products_sold_total",
                    "transform": "constant",
                }
            ],
        },
        JSON_SCHEMA,
    )

    compiled = compile_metric_yaml_to_json(validated)

    assert compiled["observations"][0]["value"] == {
        "path": "",
        "json_type": "constant",
        "required": True,
        "iterator_path": None,
    }
