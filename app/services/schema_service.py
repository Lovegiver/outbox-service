from app.models.schema_definition import SchemaDefinition
from app.repositories.schema_repository import SchemaRepository


class SchemaService:

    def __init__(
        self,
        schema_repository: SchemaRepository
    ):
        self.schema_repository = schema_repository

    def create_schema(
        self,
        event_type_id: int,
        json_version_client: str | None,
        json_version_internal: str,
        json_schema: dict
    ) -> SchemaDefinition:

        schema = SchemaDefinition(
            event_type_id=event_type_id,
            json_version_client=json_version_client,
            json_version_internal=json_version_internal,
            json_schema=json_schema,
            is_active=True
        )

        return self.schema_repository.create(schema)

    def get_active_schema(
        self,
        event_type_id: int
    ) -> SchemaDefinition | None:

        return self.schema_repository.find_active_by_event_type(
            event_type_id
        )

    def disable_schema(
        self,
        schema_id: int
    ) -> SchemaDefinition:

        schema = self.schema_repository.find_by_id(schema_id)

        if schema is None:
            raise ValueError(
                f"Schema {schema_id} not found"
            )

        schema.is_active = False

        return self.schema_repository.create(schema)

    def find_active_by_project_and_event_type(
            self,
            project_name: str,
            event_type_code: str,
    ):
        return self.schema_repository.find_active_by_project_and_event_type(
            project_name=project_name,
            event_type_code=event_type_code,
        )