def test_seed_can_create_minimal_event_graph(seed, probe) -> None:
    graph = seed.minimal_event_graph()

    assert probe.project.exists(graph.project)
    assert probe.event_type.exists(graph.event_type)
    assert probe.schema_definition.exists(graph.schema_definition)
    assert probe.event.exists(graph.event)


def test_seed_can_create_project_owner(seed, probe) -> None:
    owner = seed.project_owner()

    assert probe.project.exists(owner.project)
    assert probe.user_account.exists(owner.user)
    assert probe.project_member.exists(owner.membership)