from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schema_definition import SchemaDefinition


class SchemaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, schema_definition: SchemaDefinition) -> SchemaDefinition:
        self.db.add(schema_definition)
        self.db.commit()
        self.db.refresh(schema_definition)
        return schema_definition

    def find_by_id(self, schema_definition_id: int) -> SchemaDefinition | None:
        stmt = select(SchemaDefinition).where(
            SchemaDefinition.id == schema_definition_id
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def find_active_by_event_type_and_internal_version(
        self,
        event_type_id: int,
        json_version_internal: str,
    ) -> SchemaDefinition | None:
        stmt = select(SchemaDefinition).where(
            SchemaDefinition.event_type_id == event_type_id,
            SchemaDefinition.json_version_internal == json_version_internal,
            SchemaDefinition.is_active.is_(True),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def find_active_by_event_type(
        self,
        event_type_id: int,
    ) -> SchemaDefinition | None:
        stmt = select(SchemaDefinition).where(
            SchemaDefinition.event_type_id == event_type_id,
            SchemaDefinition.is_active.is_(True),
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_event_type(self, event_type_id: int) -> list[SchemaDefinition]:
        stmt = (
            select(SchemaDefinition)
            .where(SchemaDefinition.event_type_id == event_type_id)
            .order_by(SchemaDefinition.json_version_internal)
        )
        return list(self.db.execute(stmt).scalars().all())