from app.metrics_engine.extractor import MetricSample


def render_prometheus(samples: list[MetricSample]) -> str:
    lines: list[str] = []

    emitted_headers: set[str] = set()

    for sample in samples:
        if sample.name not in emitted_headers:
            lines.append(f"# HELP {sample.name} {sample.help}")
            lines.append(f"# TYPE {sample.name} {sample.type}")
            emitted_headers.add(sample.name)

        labels = ",".join(
            f'{key}="{value}"'
            for key, value in sample.labels.items()
        )

        if labels:
            lines.append(f"{sample.name}{{{labels}}} {sample.value}")
        else:
            lines.append(f"{sample.name} {sample.value}")

    return "\n".join(lines) + "\n"