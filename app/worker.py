from app.container.service_factory import ServiceFactory
from app.core.delivery_status import DeliveryStatus
from app.core.event_status import EventStatus
from app.core.logging import logger
from app.database import SessionLocal
from app.models import EventDelivery
from app.services.config_service import ConfigService
from apscheduler.schedulers.background import BackgroundScheduler

"""
Background worker responsible for executing the secondary Outbox pipeline.

This worker processes events that have already been durably persisted
with the RECEIVED status.

The worker is intentionally decoupled from the HTTP ingestion layer.
Its responsibility is to execute asynchronous and potentially expensive
operations such as:

- metrics extraction;
- routing resolution;
- delivery creation;
- delivery execution;
- retry handling;
- dead-letter management.

This separation guarantees that event ingestion remains fast,
transactionally short, and resilient.

The worker therefore acts as the execution engine of the Outbox runtime
pipeline, independently from the ingress mechanism used to persist events
(FastAPI, Kafka, Redis Streams, etc.).
"""

scheduler = BackgroundScheduler()
config_service = ConfigService()


def route_received_events() -> None:
    """
    Process all events currently marked as RECEIVED.

    For each received event, the worker executes the secondary processing pipeline:

    1. metrics extraction and observation persistence;
    2. route resolution based on EventType;
    3. delivery creation;
    4. event status transition to ROUTED.

    All operations executed for a given event are committed together
    within the processing transaction boundary.

    The ingestion transaction is intentionally separated from this
    processing phase in order to keep event reception fast, durable,
    and resilient.
    """

    db = SessionLocal()

    try:
        event_service = ServiceFactory.create_event_service(db)
        route_service = ServiceFactory.create_route_service(db)
        delivery_repository = ServiceFactory.create_event_delivery_repository(db)

        events = event_service.event_repository.find_received()

        for event in events:
            event_service.metrics_extraction_service.extract_and_persist_for_event(
                event
            )
            routes = route_service.route_repository.find_by_event_type(
                event.event_type_id
            )

            for route in routes:
                delivery = EventDelivery(
                    event_id=event.id,
                    destination_name=route.destination_name,
                    destination_type="webhook",
                    destination_url=route.destination_url,
                    status=DeliveryStatus.PENDING,
                )

                delivery_repository.create(delivery)

            if routes:
                event.status = EventStatus.ROUTED
                event_service.event_repository.save(event)

        db.commit()

    except Exception as exc:
        db.rollback()
        logger.info(f"[OB1-worker] routing error={exc}")

    finally:
        db.close()


def deliver_one_delivery(delivery_id: int) -> None:
    db = SessionLocal()

    try:
        event_service = ServiceFactory.create_event_service(db)
        delivery_repository = (
            ServiceFactory.create_event_delivery_repository(db)
        )
        delivery_service = ServiceFactory.delivery_service

        delivery = delivery_repository.find_by_id(delivery_id)

        if delivery is None:
            logger.info(
                f"[OB1-worker] delivery not found "
                f"delivery_id={delivery_id}"
            )
            return

        event = event_service.event_repository.get_by_id(
            delivery.event_id
        )

        if event is None:
            delivery.status = DeliveryStatus.FAILED
            delivery.last_error = f"Event not found: {delivery.event_id}"
            delivery_repository.save(delivery)
            db.commit()
            return

        delivery_service.deliver(
            event=event,
            delivery=delivery,
        )

        delivery_repository.save(delivery)
        db.commit()

    except Exception as exc:
        db.rollback()
        persist_delivery_failure(
            delivery_id=delivery_id,
            error=exc,
        )

        logger.info(
            f"[OB1-worker] delivery error "
            f"delivery_id={delivery_id} "
            f"error={exc}"
        )

    finally:
        db.close()

def persist_delivery_failure(
        delivery_id: int,
        error: Exception,
) -> None:
    db = SessionLocal()

    try:
        delivery_repository = (
            ServiceFactory.create_event_delivery_repository(db)
        )

        delivery = delivery_repository.find_by_id(delivery_id)

        if delivery is None:
            return

        delivery.attempt_count += 1
        delivery.last_error = str(error)[:1000]

        max_attempts = config_service.get_max_delivery_attempts()

        if delivery.attempt_count >= max_attempts:
            delivery.status = DeliveryStatus.DEAD_LETTER
        else:
            delivery.status = DeliveryStatus.FAILED

        delivery_repository.save(delivery)
        db.commit()

    except Exception as save_exc:
        db.rollback()

        logger.info(
            f"[OB1-worker] failed to persist "
            f"delivery failure "
            f"delivery_id={delivery_id} "
            f"error={save_exc}"
        )

    finally:
        db.close()


def deliver_pending_deliveries() -> None:
    db = SessionLocal()

    try:
        delivery_repository = ServiceFactory.create_event_delivery_repository(db)
        max_attempts = config_service.get_max_delivery_attempts()

        deliveries = delivery_repository.find_pending_and_retryable(
            max_attempts=max_attempts,
        )

        delivery_ids = [
            delivery.id
            for delivery in deliveries
        ]

    finally:
        db.close()

    for delivery_id in delivery_ids:
        deliver_one_delivery(delivery_id)


def process_outbox() -> None:
    logger.info("[OB1-worker] cycle started")

    route_received_events()
    deliver_pending_deliveries()

    db = SessionLocal()

    try:
        metric_repository = (
            ServiceFactory
            .create_system_metric_repository(db)
        )

        metric_repository.update_dead_letter_metric()
        metric_repository.update_delivered_metric()
        metric_repository.update_retry_metric()
        metric_repository.update_event_routed_metric()

        db.commit()

    except Exception as exc:
        db.rollback()

        logger.info(
            f"[OB1-worker] metric update error={exc}"
        )

    finally:
        db.close()

    logger.info("[OB1-worker] cycle finished")


def start_worker() -> None:
    interval = config_service.get_worker_interval_seconds()

    scheduler.add_job(
        process_outbox,
        trigger="interval",
        seconds=interval,
        id="outbox_worker",
        replace_existing=True,
    )

    logger.info(f"[OB1-worker] interval={interval}s")

    scheduler.start()
    logger.info("[OB1-worker] started")


def stop_worker() -> None:
    scheduler.shutdown()
    logger.info("[OB1-worker] stopped")