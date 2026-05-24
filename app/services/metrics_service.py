from datetime import datetime

from app.repositories.metric_repository import MetricRepository


class MetricsService:

    def __init__(self, repository: MetricRepository):
        self.repository = repository

    def compute_received_events(
        self,
        period_start: datetime,
        period_end: datetime,
    ) -> int:

        results = self.repository.count_received_events(
            period_start=period_start,
            period_end=period_end,
        )

        created_count = 0

        for row in results:
            self.repository.save_metric(
                metric_code="EVENT_RECEIVED_COUNT",
                project_id=row.project_id,
                event_type_id=row.event_type_id,
                period_start=period_start,
                period_end=period_end,
                value=row.value,
            )
            created_count += 1

        return created_count