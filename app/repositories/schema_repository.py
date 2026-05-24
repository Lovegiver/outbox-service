from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.schema_definition import SchemaDefinition


class SchemaRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        schema: SchemaDefinition,
    ) -> SchemaDefinition:
        self.db.add(schema)
        self.db.commit()
        self.db.refresh(schema)

        return schema

    def find_by_id(
        self,
        schema_id: int,
    ) -> SchemaDefinition | None:
        statement = (
            select(SchemaDefinition)
            .where(SchemaDefinition.id == schema_id)
        )

        return self.db.execute(statement).scalar_one_or_none()

    def find_active_by_event_type(
        self,
        event_type_id: int,
    ) -> list[SchemaDefinition]:
        statement = (
            select(SchemaDefinition)
            .where(
                SchemaDefinition.event_type_id == event_type_id,
                SchemaDefinition.enabled.is_(True),
            )
        )

        return list(self.db.execute(statement).scalars().all())

    def find_active_by_event_type_and_version(
        self,
        event_type_id: int,
        version: str,
    ) -> SchemaDefinition | None:
        statement = (
            select(SchemaDefinition)
            .where(
                SchemaDefinition.event_type_id == event_type_id,
                SchemaDefinition.version == version,
                SchemaDefinition.enabled.is_(True),
            )
        )

        return self.db.execute(statement).scalar_one_or_none()

    def disable(
        self,
        schema: SchemaDefinition,
    ) -> SchemaDefinition:
        schema.enabled = False

        self.db.commit()
        self.db.refresh(schema)

        return schema

    def delete(
        self,
        schema: SchemaDefinition,
    ) -> None:
        self.db.delete(schema)
        self.db.commit()