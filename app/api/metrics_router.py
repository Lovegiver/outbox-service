from app.container.service_factory import ServiceFactory
from app.database import get_db
from fastapi import APIRouter, Depends
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