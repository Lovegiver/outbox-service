from app.container.service_factory import ServiceFactory
from app.database import get_db
from app.metrics_engine.prometheus_renderer import (
    PROMETHEUS_CONTENT_TYPE,
    PrometheusRenderingError,
)
from app.services.prometheus_metric_state_service import (
    PrometheusMetricStateStructureError,
    PrometheusProjectNotFoundError,
)
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from starlette.responses import PlainTextResponse

router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
)


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
    "/projects/{project_id}/prometheus-state",
    response_class=PlainTextResponse,
)
def get_prometheus_metric_state_for_project(
        project_id: int,
        db: Session = Depends(get_db),
):
    """
    Expose all materialized business metric counters for one Project.

    The endpoint reads MetricState only. It does not scan events, parse YAML,
    or recompute analytical observations during the Prometheus scrape.

    Args:
        project_id: Project whose materialized counters are exposed.
        db: SQLAlchemy session injected by FastAPI.

    Returns:
        Prometheus text exposition for the selected Project.
    """

    service = ServiceFactory.create_prometheus_metric_state_service(db)

    try:
        document = service.render_project(project_id=project_id)
    except PrometheusProjectNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except (PrometheusRenderingError, PrometheusMetricStateStructureError) as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    return PlainTextResponse(
        content=document,
        media_type=PROMETHEUS_CONTENT_TYPE,
    )
