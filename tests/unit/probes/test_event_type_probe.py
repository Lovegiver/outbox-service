from tests.domain.persisted_object import PersistedProject
from tests.domain.record import EventTypeRecord, ProjectRecord
from tests.infrastructure.object_factory import ObjectFactory
from tests.probes.event_type_probe import EventTypeProbe


missing_project = PersistedProject(
    id=999999,
    name="Missing",
)


def test_event_type_probe_returns_false_when_event_type_does_not_exist(
    event_type_probe: EventTypeProbe,
) -> None:
    assert not event_type_probe.exists_by_project_and_code(
        project=missing_project,
        code="article.analyzed",
    )


def test_event_type_probe_returns_true_when_event_type_exists(
    object_factory: ObjectFactory,
    event_type_probe: EventTypeProbe,
) -> None:
    hermes = object_factory.create_project(
        ProjectRecord(name="Hermes")
    )

    object_factory.create_event_type(
        EventTypeRecord(
            project=hermes,
            code="article.analyzed",
            name="Article analyzed",
        )
    )

    assert event_type_probe.exists_by_project_and_code(
        project=hermes,
        code="article.analyzed",
    )