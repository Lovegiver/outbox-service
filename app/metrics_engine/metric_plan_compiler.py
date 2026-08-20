from app.metrics_engine.metric_yaml_validator import (
    ValidatedMetricYaml,
)


def compile_metric_yaml_to_json(
    validated_metric_yaml: ValidatedMetricYaml,
) -> dict[str, object]:
    """Compile validated metric YAML into a deterministic runtime document."""
    return {
        "compiler_version": "1.0",
        "yaml_version": validated_metric_yaml.version,
        "observations": [
            {
                "metric_code": observation.code,
                "transform": observation.transform,
                "value": {
                    "path": observation.value_path.path,
                    "json_type": observation.value_path.json_type,
                    "required": observation.value_path.required,
                    "iterator_path": observation.value_path.iterator_path,
                },
                "labels": [
                    {
                        "name": label_name,
                        "kind": "index" if label_path == "$index" else "path",
                        "path": None if label_path == "$index" else label_path.path,
                        "json_type": None if label_path == "$index" else label_path.json_type,
                        "required": None if label_path == "$index" else label_path.required,
                        "iterator_path": (
                            None
                            if label_path == "$index"
                            else label_path.iterator_path
                        ),
                    }
                    for label_name, label_path in sorted(
                        observation.labels.items()
                    )
                ],
            }
            for observation in validated_metric_yaml.observations
        ],
    }
