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
        name: str,
        version: str,
        json_schema: dict
    ) -> SchemaDefinition:

        schema = SchemaDefinition(
            event_type_id=event_type_id,
            name=name,
            version=version,
            json_schema=json_schema,
            enabled=True
        )

        return self.schema_repository.create(schema)

    def get_active_schemas(
        self,
        event_type_id: int
    ) -> list[SchemaDefinition]:

        return self.schema_repository.find_active_by_event_type(
            event_type_id
        )

    def disable_schema(
        self,
        schema_id: int
    ) -> SchemaDefinition:

        schema = self.schema_repository.find_by_id(
            schema_id
        )

        if schema is None:
            raise ValueError(
                f"Schema {schema_id} not found"
            )

        return self.schema_repository.disable(
            schema
        )