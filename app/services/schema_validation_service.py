import json
from pathlib import Path

from jsonschema import ValidationError, validate


class SchemaValidationService:
    def validate_payload(
            self,
            project: str,
            event_type: str,
            payload: dict
    ) -> None:
        schema_path = self._resolve_schema_path(project, event_type)

        if not schema_path.exists():
            raise FileNotFoundError(
                f"No schema found for project={project}, event_type={event_type}"
            )

        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        validate(
            instance=payload,
            schema=schema
        )

    def _resolve_schema_path(self, project: str, event_type: str) -> Path:
        safe_project = project.lower()
        safe_event_type = event_type.lower().replace(".", "_")

        return Path("schemas") / safe_project / f"{safe_event_type}.schema.json"