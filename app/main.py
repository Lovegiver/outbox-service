from contextlib import asynccontextmanager
from uuid import UUID

from app.dependencies import get_event_service
from app.schemas.event_schema import EventIn, EventReceived
from app.services.event_service import EventService
from app.worker import start_worker, stop_worker
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_worker()
    yield
    stop_worker()

app = FastAPI(
    title="Outbox Service",
    version="0.1.0",
    description="Event routing and delivery service",
    lifespan=lifespan,
)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "outbox",
    }


@app.post("/events", response_model=EventReceived)
def receive_event(
        event: EventIn,
        service: EventService = Depends(get_event_service)
):
    try:
        service.receive_event(event)

    except IntegrityError as exc:
        service.rollback()
        raise HTTPException(
            status_code=409,
            detail="Event already exists"
        ) from exc

    except SQLAlchemyError as exc:
        service.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to persist event"
        ) from exc

    return EventReceived(
        status="received",
        event=event,
    )

@app.post("/events/{event_id}/validate")
def validate_event(
        event_id: UUID,
        service: EventService = Depends(get_event_service)
):
    try:
        event = service.validate_event(event_id)
        return {
            "status": "validated",
            "event_id": event.event_id,
            "event_status": event.status,
        }

    except SQLAlchemyError as exc:
        service.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to validate event"
        ) from exc

@app.post("/events/{event_id}/route")
def route_event(
        event_id: UUID,
        service: EventService = Depends(get_event_service)
):
    try:
        event = service.route_event(event_id)
        return {
            "status": "routed",
            "event_id": event.event_id,
            "event_status": event.status,
        }

    except SQLAlchemyError as exc:
        service.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to route event"
        ) from exc

@app.post("/events/{event_id}/deliver")
def deliver_event(
        event_id: UUID,
        service: EventService = Depends(get_event_service)
):
    try:
        event = service.deliver_event(event_id)
        return {
            "status": "delivery_processed",
            "event_id": event.event_id,
            "event_status": event.status,
        }

    except SQLAlchemyError as exc:
        service.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to deliver event"
        ) from exc

@app.post("/events/{event_id}/retry")
def retry_event(
        event_id: UUID,
        service: EventService = Depends(get_event_service)
):
    try:
        event = service.retry_event(event_id)
        return {
            "status": "retry_processed",
            "event_id": event.event_id,
            "event_status": event.status,
        }

    except SQLAlchemyError as exc:
        service.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to retry event"
        ) from exc

@app.post("/events/{event_id}/dead-letter")
def mark_event_as_dead_letter(
        event_id: UUID,
        service: EventService = Depends(get_event_service)
):
    try:
        event = service.mark_exhausted_deliveries_as_dead_letter(event_id)
        return {
            "status": "dead_letter_processed",
            "event_id": event.event_id,
            "event_status": event.status,
        }

    except SQLAlchemyError as exc:
        service.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to process dead letter"
        ) from exc

@app.post("/worker/process")
def process_worker(
        service: EventService = Depends(get_event_service)
):
    try:
        return service.process_pending_work()

    except SQLAlchemyError as exc:
        service.rollback()
        raise HTTPException(
            status_code=500,
            detail="Failed to process worker"
        ) from exc