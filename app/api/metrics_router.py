from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.container.service_factory import ServiceFactory
from app.database import get_db

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