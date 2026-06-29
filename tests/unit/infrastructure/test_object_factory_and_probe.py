from tests.domain.record import (
    EventRecord,
    EventTypeRecord,
    ProjectRecord,
    SchemaDefinitionRecord,
)


def test_factory_can_build_minimal_event_graph(
    factory,
    probe,
) -> None:
    project = factory.project(
        ProjectRecord(name="Hermes")
    )

    event_type = factory.event_type(
        EventTypeRecord(
            project=project,
            code="article.analyzed",
            name="Article analyzed",
        )
    )

    schema = factory.schema_definition(
        SchemaDefinitionRecord(
            event_type=event_type,
        )
    )

    event = factory.event(
        EventRecord(
            event_type=event_type,
            schema_definition=schema,
            payload={
                "duration_seconds": 12.3,
            },
        )
    )

    assert probe.project.exists(project)
    assert probe.event_type.exists(event_type)
    assert probe.schema_definition.exists(schema)
    assert probe.event.exists(event)