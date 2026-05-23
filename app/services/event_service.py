from uuid import UUID
from jsonschema import ValidationError
from fastapi import HTTPException

from app.core.event_status import EventStatus
from app.models import Event, EventDelivery
from app.repositories.event_repository import EventRepository
from app.services.delivery_service import DeliveryService
from app.services.routing_service import RoutingService
from app.services.schema_validation_service import SchemaValidationService

class EventService:
    def __init__(
            self,
            repository: EventRepository,
            schema_validator: SchemaValidationService,
            routing_service: RoutingService,
            delivery_service: DeliveryService,
    ):
        self.repository = repository
        self.schema_validator = schema_validator
        self.routing_service = routing_service
        self.delivery_service = delivery_service

    def receive_event(self, event_in) -> Event:
        event = Event(
            event_id=event_in.event_id,
            project=event_in.project,
            event_type=event_in.event_type,
            schema_version=event_in.schema_version,
            payload=event_in.payload,
            status=EventStatus.RECEIVED,
        )

        return self.repository.save(event)

    def rollback(self) -> None:
        self.repository.rollback()

    def validate_event(self, event_id: UUID) -> Event:
        event = self.repository.find_by_event_id(event_id)

        if event is None:
            raise HTTPException(
                status_code=404,
                detail="Event not found"
            )

        if event.status != EventStatus.RECEIVED:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot validate event with status {event.status}"
            )

        try:
            self.schema_validator.validate_payload(
                project=event.project,
                event_type=event.event_type,
                payload=event.payload,
            )
        except FileNotFoundError as exc:
            event.status = EventStatus.FAILED
            self.repository.commit()
            raise HTTPException(
                status_code=422,
                detail=str(exc)
            ) from exc
        except ValidationError as exc:
            event.status = EventStatus.FAILED
            self.repository.commit()
            raise HTTPException(
                status_code=422,
                detail=f"Payload does not match schema: {exc.message}"
            ) from exc

        event.status = EventStatus.VALIDATED
        self.repository.commit()
        return event

    def route_event(self, event_id: UUID) -> Event:
        event = self.repository.find_by_event_id(event_id)

        if event is None:
            raise HTTPException(
                status_code=404,
                detail="Event not found"
            )

        if event.status != EventStatus.VALIDATED:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot route event with status {event.status}"
            )

        destinations = self.routing_service.get_destinations(
            project=event.project
        )

        if not destinations:
            event.status = EventStatus.FAILED
            self.repository.commit()
            raise HTTPException(
                status_code=422,
                detail=f"No destination configured for project {event.project}"
            )

        for destination in destinations:
            delivery = EventDelivery(
                event_id=event.id,
                destination_name=destination["name"],
                destination_type=destination["type"],
                destination_url=destination.get("url"),
                status="PENDING",
            )
            self.repository.add_delivery(delivery)

        event.status = EventStatus.ROUTED
        self.repository.commit()
        return event

    def deliver_event(self, event_id: UUID) -> Event:
        event = self.repository.find_by_event_id(event_id)

        if event is None:
            raise HTTPException(
                status_code=404,
                detail="Event not found"
            )

        if event.status != EventStatus.ROUTED:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot deliver event with status {event.status}"
            )

        deliveries = self.repository.find_deliveries_by_event_id_and_status(
            event.id,
            "PENDING",
        )

        if not deliveries:
            raise HTTPException(
                status_code=409,
                detail="No pending delivery found"
            )

        for delivery in deliveries:
            try:
                self.delivery_service.deliver(event, delivery)
            except Exception as exc:
                delivery.status = "FAILED"
                delivery.attempt_count += 1
                delivery.last_error = str(exc)

        if all(delivery.status == "DELIVERED" for delivery in deliveries):
            event.status = EventStatus.DELIVERED
        else:
            event.status = EventStatus.FAILED

        self.repository.commit()
        return event

    def retry_event(self, event_id: UUID) -> Event:
        event = self.repository.find_by_event_id(event_id)

        if event is None:
            raise HTTPException(
                status_code=404,
                detail="Event not found"
            )

        if event.status != EventStatus.FAILED:
            raise HTTPException(
                status_code=409,
                detail=f"Cannot retry event with status {event.status}"
            )

        deliveries = self.repository.find_deliveries_by_event_id_and_status(
            event.id,
            "FAILED",
        )

        if not deliveries:
            raise HTTPException(
                status_code=409,
                detail="No failed delivery found"
            )

        for delivery in deliveries:
            try:
                self.delivery_service.deliver(event, delivery)
            except Exception as exc:
                delivery.status = "FAILED"
                delivery.attempt_count += 1
                delivery.last_error = str(exc)

        if all(delivery.status == "DELIVERED" for delivery in deliveries):
            event.status = EventStatus.DELIVERED
        else:
            event.status = EventStatus.FAILED

        self.repository.commit()
        return event

