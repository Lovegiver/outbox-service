from tests.domain.record import ProjectRecord
from tests.infrastructure.object_factory import ObjectFactory
from tests.infrastructure.probe import Probe


def test_project_probe_returns_false_when_project_does_not_exist(
    probe: Probe,
) -> None:
    assert not probe.project.exists_by_name("missing-project")


def test_project_probe_returns_true_when_project_exists(
    factory: ObjectFactory,
    probe: Probe,
) -> None:
    factory.project(
        ProjectRecord(name="Hermes")
    )

    assert probe.project.exists_by_name("Hermes")