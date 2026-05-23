from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.repositories.event_repository import EventRepository
from app.services.config_service import ConfigService
from app.services.delivery_service import DeliveryService
from app.services.event_service import EventService
from app.services.routing_service import RoutingService
from app.services.schema_validation_service import SchemaValidationService


scheduler = BackgroundScheduler()
config_service = ConfigService()


def process_outbox() -> None:
    db = SessionLocal()

    try:
        repository = EventRepository(db)
        service = EventService(
            repository=repository,
            schema_validator=SchemaValidationService(),
            routing_service=RoutingService(),
            delivery_service=DeliveryService(),
            config_service=ConfigService(),
        )

        result = service.process_pending_work()
        print(f"[outbox-worker] processed={result}")

    except Exception as exc:
        db.rollback()
        print(f"[outbox-worker] error={exc}")

    finally:
        db.close()


def start_worker() -> None:
    interval = config_service.get_worker_interval_seconds()

    scheduler.add_job(
        process_outbox,
        trigger="interval",
        seconds=interval,
        id="outbox_worker",
        replace_existing=True,
    )

    print(
        f"[outbox-worker] interval={interval}s"
    )

    scheduler.start()
    print("[outbox-worker] started")


def stop_worker() -> None:
    scheduler.shutdown()
    print("[outbox-worker] stopped")