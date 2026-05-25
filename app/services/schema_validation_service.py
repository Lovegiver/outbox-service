from jsonschema import ValidationError, validate

from app.repositories.schema_repository import SchemaRepository


class SchemaValidationService:
    def __init__(self, schema_repository: SchemaRepository):
        self.schema_repository = schema_repository

    def validate_payload(
        self,
        event_type_id: int,
        json_version_internal: str,
        payload: dict,
    ) -> None:
        schema_definition = (
            self.schema_repository.find_active_by_event_type_and_internal_version(
                event_type_id=event_type_id,
                json_version_internal=json_version_internal,
            )
        )

        if schema_definition is None:
            raise ValueError(
                f"No active schema found for event_type_id={event_type_id}, "
                f"json_version_internal={json_version_internal}"
            )

        try:
            validate(
                instance=payload,
                schema=schema_definition.json_schema,
            )
        except ValidationError as exc:
            raise ValueError(f"Invalid payload: {exc.message}") from exc