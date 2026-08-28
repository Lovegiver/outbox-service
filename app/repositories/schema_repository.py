from app.models import EventType, Project
from app.models.schema_definition import SchemaDefinition
from sqlalchemy import select
from sqlalchemy.orm import Session


class SchemaRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, schema_definition: SchemaDefinition) -> SchemaDefinition:
        self.db.add(schema_definition)
        self.db.commit()
        self.db.refresh(schema_definition)
        return schema_definition

    def find_by_id(
        self,
        schema_definition_id: int,
        *,
        for_update: bool = False,
    ) -> SchemaDefinition | None:
        stmt = select(SchemaDefinition).where(
            SchemaDefinition.id == schema_definition_id
        )
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def lock_by_ids(
        self,
        schema_definition_ids: list[int],
    ) -> list[SchemaDefinition]:
        """Lock schema rows in a deterministic order for orchestration."""
        statement = (
            select(SchemaDefinition)
            .where(SchemaDefinition.id.in_(schema_definition_ids))
            .order_by(SchemaDefinition.id.asc())
            .with_for_update()
        )
        return list(self.db.execute(statement).scalars().all())

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
        *,
        for_update: bool = False,
    ) -> SchemaDefinition | None:
        stmt = select(SchemaDefinition).where(
            SchemaDefinition.event_type_id == event_type_id,
            SchemaDefinition.is_active.is_(True),
        )
        if for_update:
            stmt = stmt.with_for_update()
        return self.db.execute(stmt).scalar_one_or_none()

    def list_by_event_type(self, event_type_id: int) -> list[SchemaDefinition]:
        stmt = (
            select(SchemaDefinition)
            .where(SchemaDefinition.event_type_id == event_type_id)
            .order_by(SchemaDefinition.json_version_internal)
        )
        return list(self.db.execute(stmt).scalars().all())

    def find_active_by_project_and_event_type(
        self,
        project_name: str,
        event_type_code: str,
    ) -> SchemaDefinition | None:
        statement = (
            select(SchemaDefinition)
            .join(EventType, SchemaDefinition.event_type_id == EventType.id)
            .join(Project, EventType.project_id == Project.id)
            .where(
                Project.name == project_name,
                EventType.code == event_type_code,
                SchemaDefinition.is_active.is_(True),
            )
        )

        return self.db.execute(statement).scalar_one_or_none()
