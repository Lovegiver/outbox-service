from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.container.service_factory import ServiceFactory
from app.database import get_db

router = APIRouter(
    prefix="/contracts",
    tags=["contracts"],
)


@router.get("/outbox-event/latest")
def get_latest_outbox_event_contract(
        db: Session = Depends(get_db),
):
    schema_service = ServiceFactory.create_schema_service(db)

    schema_definition = schema_service.find_active_by_project_and_event_type(
        project_name="OUTBOX",
        event_type_code="OUTBOX_EVENT",
    )

    if schema_definition is None:
        raise HTTPException(
            status_code=404,
            detail="Active Outbox event contract not found",
        )

    return {
        "contract_name": "outbox-event",
        "version": schema_definition.json_version_internal,
        "schema": schema_definition.json_schema,
    }