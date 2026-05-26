from sqlalchemy import select

from app.database import SessionLocal
from app.models.event_type import EventType
from app.models.project import Project
from app.models.schema_definition import SchemaDefinition


OUTBOX_PROJECT_NAME = "OUTBOX"
OUTBOX_EVENT_TYPE_CODE = "OUTBOX_EVENT"
OUTBOX_EVENT_TYPE_NAME = "Outbox Event Contract"
OUTBOX_CONTRACT_VERSION = "1.0"


OUTBOX_EVENT_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "OutboxEventRequest",
    "type": "object",
    "required": [
        "project_id",
        "event_type_id",
        "payload",
    ],
    "properties": {
        "project_id": {
            "type": "integer",
        },
        "event_type_id": {
            "type": "integer",
        },
        "json_version_client": {
            "type": ["string", "null"],
        },
        "payload": {
            "type": "object",
        },
    },
    "additionalProperties": False,
}


def get_or_create_outbox_project(db):
    statement = select(Project).where(
        Project.name == OUTBOX_PROJECT_NAME
    )

    project = db.execute(statement).scalar_one_or_none()

    if project is not None:
        return project

    project = Project(
        name=OUTBOX_PROJECT_NAME,
        description="Internal Outbox project",
        is_active=True,
    )

    db.add(project)
    db.flush()
    db.refresh(project)

    return project


def get_or_create_outbox_event_type(
        db,
        project: Project,
):
    statement = select(EventType).where(
        EventType.project_id == project.id,
        EventType.code == OUTBOX_EVENT_TYPE_CODE,
    )

    event_type = db.execute(statement).scalar_one_or_none()

    if event_type is not None:
        return event_type

    event_type = EventType(
        project_id=project.id,
        code=OUTBOX_EVENT_TYPE_CODE,
        name=OUTBOX_EVENT_TYPE_NAME,
        description="Official Outbox event ingestion contract",
        is_active=True,
    )

    db.add(event_type)
    db.flush()
    db.refresh(event_type)

    return event_type


def seed_outbox_schema(
        db,
        event_type: EventType,
):
    existing_statement = select(SchemaDefinition).where(
        SchemaDefinition.event_type_id == event_type.id,
        SchemaDefinition.json_version_internal == OUTBOX_CONTRACT_VERSION,
    )

    existing_schema = db.execute(
        existing_statement
    ).scalar_one_or_none()

    active_statement = select(SchemaDefinition).where(
        SchemaDefinition.event_type_id == event_type.id,
        SchemaDefinition.is_active.is_(True),
    )

    active_schemas = list(
        db.execute(active_statement).scalars().all()
    )

    for schema in active_schemas:
        schema.is_active = False

    if existing_schema is not None:
        existing_schema.json_schema = OUTBOX_EVENT_SCHEMA
        existing_schema.is_active = True
        db.flush()
        db.refresh(existing_schema)
        return existing_schema

    schema_definition = SchemaDefinition(
        event_type_id=event_type.id,
        json_version_client=None,
        json_version_internal=OUTBOX_CONTRACT_VERSION,
        json_schema=OUTBOX_EVENT_SCHEMA,
        is_active=True,
    )

    db.add(schema_definition)
    db.flush()
    db.refresh(schema_definition)

    return schema_definition


def main():
    db = SessionLocal()

    try:
        project = get_or_create_outbox_project(db)
        event_type = get_or_create_outbox_event_type(
            db=db,
            project=project,
        )
        schema_definition = seed_outbox_schema(
            db=db,
            event_type=event_type,
        )

        db.commit()

        print("Outbox contract seeded")
        print(f"project_id={project.id}")
        print(f"event_type_id={event_type.id}")
        print(f"schema_definition_id={schema_definition.id}")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()