from app.container.service_factory import ServiceFactory
from app.database import get_db
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from starlette.responses import PlainTextResponse

router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
)


def _to_prometheus_metric_name(metric_code: str) -> str:
    """
    Convert an OB1 metric code to a Prometheus-safe metric name.
    """

    return "ob1_" + metric_code.replace(".", "_").replace("-", "_")


def _render_labels(labels: dict[str, object]) -> str:
    """
    Render Prometheus labels from a JSON-compatible label dictionary.
    """

    if not labels:
        return ""

    content = ",".join(
        f'{key}="{str(value).replace(chr(34), chr(92) + chr(34))}"'
        for key, value in sorted(labels.items())
    )

    return "{" + content + "}"


def serialize_metrics(metrics):
    return [
        {
            "metric_code": metric.metric_code,
            "value": float(metric.value),
            "period_start": metric.period_start,
            "period_end": metric.period_end,
            "computed_at": metric.computed_at,
        }
        for metric in metrics
    ]


@router.get("")
def get_metrics(
        db: Session = Depends(get_db),
):
    repository = (
        ServiceFactory
        .create_system_metric_repository(db)
    )

    metrics = repository.find_all_metrics()

    return serialize_metrics(metrics)


@router.get("/latest")
def get_latest_metrics(
        db: Session = Depends(get_db),
):
    repository = (
        ServiceFactory
        .create_system_metric_repository(db)
    )

    metrics = repository.find_latest_metrics()

    return serialize_metrics(metrics)

@router.get(
    "/prometheus",
    response_class=PlainTextResponse,
)
def get_prometheus_metrics(
        db: Session = Depends(get_db),
):
    repository = (
        ServiceFactory
        .create_system_metric_repository(db)
    )

    metrics = repository.find_latest_metrics()

    lines = []

    for metric in metrics:
        metric_name = (
            "outbox_"
            + metric.metric_code
            .replace(".", "_")
        )

        lines.append(
            f"# TYPE {metric_name} gauge"
        )

        lines.append(
            f"{metric_name} {float(metric.value)}"
        )

    return "\n".join(lines) + "\n"

@router.get(
    "/event-types/{event_type_id}/prometheus-state",
    response_class=PlainTextResponse,
)
def get_prometheus_metric_state_for_event_type(
        event_type_id: int,
        db: Session = Depends(get_db),
):
    """
    Expose materialized business metric counters for one EventType.

    The endpoint reads MetricState only. It does not scan events, parse YAML,
    or recompute analytical observations during the Prometheus scrape.

    Args:
        event_type_id: EventType whose materialized counters are exposed.
        db: SQLAlchemy session injected by FastAPI.

    Returns:
        Prometheus text exposition for the selected EventType.
    """

    service = ServiceFactory.create_metric_state_aggregation_service(db)
    states = service.find_states_by_event_type(event_type_id)

    lines = []
    emitted_headers = set()

    for state in states:
        metric_name = _to_prometheus_metric_name(state.metric_code)

        if metric_name not in emitted_headers:
            lines.append(f"# TYPE {metric_name} counter")
            emitted_headers.add(metric_name)

        lines.append(
            f"{metric_name}{_render_labels(state.labels_json)} "
            f"{float(state.value)}"
        )

    return "\n".join(lines) + "\n"
