from jsonschema import validate

from app.repositories.schema_repository import SchemaRepository


class SchemaValidationService:

    def __init__(
        self,
        schema_repository: SchemaRepository,
    ):
        self.schema_repository = schema_repository

    def validate_payload(
        self,
        event_type_id: int,
        schema_version: str,
        payload: dict,
    ) -> None:
        schema_definition = (
            self.schema_repository.find_active_by_event_type_and_version(
                event_type_id=event_type_id,
                version=schema_version,
            )
        )

        if schema_definition is None:
            raise ValueError(
                "No active schema found for "
                f"event_type_id={event_type_id}, "
                f"schema_version={schema_version}"
            )

        validate(
            instance=payload,
            schema=schema_definition.json_schema,
        )