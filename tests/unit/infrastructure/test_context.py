def test_context_exposes_test_infrastructure(ctx) -> None:
    graph = ctx.seed.minimal_event_graph()

    ctx.assertions.exists(
        ctx.probe.project,
        graph.project,
    )

    ctx.assertions.exists(
        ctx.probe.event_type,
        graph.event_type,
    )

    ctx.assertions.exists(
        ctx.probe.schema_definition,
        graph.schema_definition,
    )

    ctx.assertions.exists(
        ctx.probe.event,
        graph.event,
    )