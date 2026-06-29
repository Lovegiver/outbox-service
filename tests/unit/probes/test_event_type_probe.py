from tests.domain.persisted_object import PersistedProject
from tests.domain.record import EventTypeRecord, ProjectRecord
from tests.infrastructure.object_factory import ObjectFactory
from tests.infrastructure.probe import Probe


missing_project = PersistedProject(
    id=999999,
    name="Missing",
)


def test_event_type_probe_returns_false_when_event_type_does_not_exist(
    probe: Probe,
) -> None:
    assert not probe.event_type.exists_by_project_and_code(
        project=missing_project,
        code="article.analyzed",
    )


def test_event_type_probe_returns_true_when_event_type_exists(
    factory: ObjectFactory,
    probe: Probe,
) -> None:
    hermes = factory.project(
        ProjectRecord(name="Hermes")
    )

    factory.event_type(
        EventTypeRecord(
            project=hermes,
            code="article.analyzed",
            name="Article analyzed",
        )
    )

    assert probe.event_type.exists_by_project_and_code(
        project=hermes,
        code="article.analyzed",
    )