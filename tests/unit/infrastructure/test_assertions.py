from tests.domain.record import ProjectRecord


def test_assertions_can_verify_persisted_object(
    factory,
    probe,
    assertions,
) -> None:
    project = factory.project(
        ProjectRecord(name="Hermes")
    )

    assertions.exists(
        probe.project,
        project,
    )
