import asyncio

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from app.container.service_factory import ServiceFactory
from app.core.delivery_status import DeliveryStatus
from app.core.event_status import EventStatus
from app.core.logging import logger
from app.database import SessionLocal
from app.models import EventDelivery
from app.runtime.runtime_event import RuntimeEvent
from app.runtime.runtime_event_bus import runtime_event_bus
from app.runtime.runtime_event_type import RuntimeEventType
from app.services.config_service import ConfigService

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


def route_received_events(db: Session | None = None) -> None:
    """
    Route all events currently marked as RECEIVED.

    This function is a runtime processing unit, not the scheduler itself.

    When called by the production worker, no Session is provided: the function
    opens its own transaction boundary, commits on success, rolls back on
    failure, and closes the Session.

    When called by integration or BDD tests, the caller may provide an existing
    Session. In that case, the function participates in the caller-owned
    transaction and never commits, rolls back, or closes the Session itself.

    For each received event, the function executes the secondary processing
    pipeline:

    1. metrics extraction and observation persistence;
    2. route resolution based on EventType;
    3. EventDelivery creation;
    4. Event status transition to ROUTED or UNROUTABLE.
    """

    owns_session = db is None

    if db is None:
        db = SessionLocal()

    try:
        event_ingress_service = ServiceFactory.create_event_ingress_service(db)
        route_service = ServiceFactory.create_route_service(db)
        delivery_repository = ServiceFactory.create_event_delivery_repository(db)

        events = event_ingress_service.event_repository.find_received()

        for event in events:
            observations = (
                event_ingress_service
                .metrics_extraction_service
                .extract_and_persist_for_event(event)
            )

            publish_runtime_event(
                RuntimeEvent(
                    type=RuntimeEventType.METRICS_EXTRACTED,
                    event_id=event.id,
                    event_uuid=event.event_uuid,
                    event_type_id=event.event_type_id,
                    correlation_id=event.correlation_id,
                    message="Metrics extracted",
                    payload={
                        "observation_count": len(observations),
                    },
                )
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
                event_ingress_service.event_repository.save(event)

                publish_runtime_event(
                    RuntimeEvent(
                        type=RuntimeEventType.EVENT_ROUTED,
                        event_id=event.id,
                        event_uuid=event.event_uuid,
                        event_type_id=event.event_type_id,
                        correlation_id=event.correlation_id,
                        event_status=event.status,
                        message="Event routed",
                        payload={
                            "delivery_count": len(routes),
                        },
                    )
                )

            else:
                event.status = EventStatus.UNROUTABLE
                event_ingress_service.event_repository.save(event)

                publish_runtime_event(
                    RuntimeEvent(
                        type=RuntimeEventType.EVENT_UNROUTABLE,
                        event_id=event.id,
                        event_uuid=event.event_uuid,
                        event_type_id=event.event_type_id,
                        correlation_id=event.correlation_id,
                        event_status=event.status,
                        message="Event routing failed: no active route found",
                        payload={
                            "reason": "NO_ACTIVE_ROUTE",
                        },
                    )
                )

        if owns_session:
            db.commit()

    except Exception:
        if owns_session:
            db.rollback()
            logger.exception("[OB1-worker] routing error")
            return

        raise

    finally:
        if owns_session:
            db.close()


def deliver_one_delivery(delivery_id: int, db: Session | None = None) -> None:
    """
    Execute a single EventDelivery.

    When called by production runtime code, no Session is provided and this
    function owns its transaction boundary.

    When called by BDD or integration tests, an existing Session can be
    provided so the delivery execution participates in the test transaction.
    """

    owns_session = db is None

    if db is None:
        db = SessionLocal()

    try:
        event_ingress_service = ServiceFactory.create_event_ingress_service(db)
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

        event = event_ingress_service.event_repository.get_by_id(
            delivery.event_id
        )

        if event is None:
            delivery.status = DeliveryStatus.FAILED
            delivery.last_error = f"Event not found: {delivery.event_id}"
            delivery_repository.save(delivery)
            db.commit()
            return

        publish_runtime_event(
            RuntimeEvent(
                type=RuntimeEventType.DELIVERY_STARTED,
                event_id=event.id,
                event_uuid=event.event_uuid,
                event_type_id=event.event_type_id,
                correlation_id=event.correlation_id,
                delivery_id=delivery.id,
                delivery_status=delivery.status,
                message="Delivery started",
            )
        )

        delivery_service.deliver(
            event=event,
            delivery=delivery,
        )

        delivery_repository.save(delivery)

        if owns_session:
            db.commit()

        publish_runtime_event(
            RuntimeEvent(
                type=RuntimeEventType.DELIVERY_SUCCEEDED,
                event_id=event.id,
                event_uuid=event.event_uuid,
                event_type_id=event.event_type_id,
                correlation_id=event.correlation_id,
                delivery_id=delivery.id,
                delivery_status=delivery.status,
                message="Delivery succeeded",
            )
        )

    except Exception as exc:
        if owns_session:
            db.rollback()

        persist_delivery_failure(
            delivery_id=delivery_id,
            error=exc,
            db=db if not owns_session else None,
        )

        logger.info(
            f"[OB1-worker] delivery error "
            f"delivery_id={delivery_id} "
            f"error={exc}"
        )

    finally:
        if owns_session:
            db.close()

def persist_delivery_failure(
        delivery_id: int,
        error: Exception,
        db: Session | None = None,
) -> None:
    """
    Persist the failed result of a delivery attempt.

    The function can either own its Session in production failure handling or
    participate in a caller-owned transaction during BDD/integration tests.
    """

    owns_session = db is None

    if db is None:
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

            publish_runtime_event(
                RuntimeEvent(
                    type=RuntimeEventType.DELIVERY_DEAD_LETTERED,
                    delivery_id=delivery.id,
                    delivery_status=delivery.status,
                    message="Final delivery attempt failed and moved to dead letter",
                    payload={
                        "attempt_count": delivery.attempt_count,
                        "max_attempts": max_attempts,
                        "last_error": delivery.last_error,
                        "destination_name": delivery.destination_name,
                        "destination_url": delivery.destination_url,
                        "final_attempt_failed": True,
                    },
                )
            )
        else:
            delivery.status = DeliveryStatus.FAILED

            publish_runtime_event(
                RuntimeEvent(
                    type=RuntimeEventType.DELIVERY_FAILED,
                    delivery_id=delivery.id,
                    delivery_status=delivery.status,
                    message="Delivery attempt failed",
                    payload={
                        "attempt_count": delivery.attempt_count,
                        "last_error": delivery.last_error,
                        "destination_name": delivery.destination_name,
                        "destination_url": delivery.destination_url,
                    },
                )
            )

        delivery_repository.save(delivery)
        db.commit()

    except Exception as save_exc:
        if owns_session:
            db.rollback()

        logger.info(
            f"[OB1-worker] failed to persist "
            f"delivery failure "
            f"delivery_id={delivery_id} "
            f"error={save_exc}"
        )

    finally:
        if owns_session:
            db.close()


def deliver_pending_deliveries(db: Session | None = None) -> None:
    """
    Execute all pending or retryable deliveries.

    The production worker lets this function open its own short transaction for
    selecting eligible deliveries. Tests may provide a Session so seeded
    deliveries remain visible inside the same transaction.
    """

    owns_session = db is None

    if db is None:
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
        if owns_session:
            db.close()

    for delivery_id in delivery_ids:
        deliver_one_delivery(
            delivery_id=delivery_id,
            db=db if not owns_session else None,
        )


def aggregate_prometheus_metric_state() -> None:
    """
    Aggregate analytical observations into Prometheus-ready metric state.

    MetricState and MetricCheckpoint are updated within the same database
    transaction so the aggregation is resilient to worker crashes and avoids
    both data loss and double counting.
    """

    db = SessionLocal()

    try:
        service = ServiceFactory.create_metric_state_aggregation_service(db)
        aggregated_count = service.aggregate_all_streams(limit_per_stream=1000)
        db.commit()

        if aggregated_count > 0:
            logger.info(
                f"[OB1-worker] metric_state aggregated "
                f"observation_count={aggregated_count}"
            )

    except Exception as exc:
        db.rollback()
        logger.info(f"[OB1-worker] metric_state aggregation error={exc}")

    finally:
        db.close()


def process_outbox() -> None:

    publish_runtime_event(
        RuntimeEvent(
            type=RuntimeEventType.WORKER_CYCLE_STARTED,
            message="OB1 worker cycle started",
        )
    )

    route_received_events()
    deliver_pending_deliveries()
    aggregate_prometheus_metric_state()

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

    publish_runtime_event(
        RuntimeEvent(
            type=RuntimeEventType.WORKER_CYCLE_FINISHED,
            message="OB1 worker cycle finished",
        )
    )


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


def publish_runtime_event(event: RuntimeEvent) -> None:
    """
    Publish a runtime event from synchronous worker code.

    The worker currently runs in a synchronous APScheduler context,
    therefore runtime publication must bootstrap its own event loop.
    """

    asyncio.run(
        runtime_event_bus.publish(event)
    )