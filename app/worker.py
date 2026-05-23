from app.container.service_factory import ServiceFactory
from app.database import SessionLocal
from app.services.config_service import ConfigService
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()
config_service = ConfigService()


def process_outbox() -> None:
    db = SessionLocal()

    try:
        service = ServiceFactory.create_event_service(db)

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