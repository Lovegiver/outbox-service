from tests.domain.record import ProjectRecord
from tests.infrastructure.object_factory import ObjectFactory
from tests.probes.project_probe import ProjectProbe


def test_project_probe_returns_false_when_project_does_not_exist(
    project_probe: ProjectProbe,
) -> None:
    assert not project_probe.exists_by_name("missing-project")


def test_project_probe_returns_true_when_project_exists(
    object_factory: ObjectFactory,
    project_probe: ProjectProbe,
) -> None:
    object_factory.create_project(
        ProjectRecord(name="Hermes")
    )

    assert project_probe.exists_by_name("Hermes")