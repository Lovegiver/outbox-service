import os

from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.api.admin.api_key_router import (
    router as api_key_router,
)
from app.api.admin.dead_letter_router import (
    router as dead_letter_router
)
from app.api.admin.event_type_router import (
    router as event_type_router
)
from app.api.admin.metric_definition_router import (
    router as metric_definition_router,
)
from app.api.admin.project_api import router as admin_project_router
from app.api.admin.project_member_router import (
    router as project_member_router,
)
from app.api.admin.route_api import router as admin_route_router
from app.api.admin.schema_api import router as admin_schema_router
from app.api.auth_router import router as auth_router
from app.api.contracts_router import (
    router as contracts_router
)
from app.api.metrics_router import (
    router as metrics_router
)
from app.dependencies import (
    get_current_api_key,
    get_event_ingress_service,
)
from app.models.api_key import ApiKey
from app.api.runtime_metrics_router import (
    router as runtime_metrics_router,
)
from app.runtime.runtime_ws import router as runtime_router
from app.schemas.event_schema import EventIn, EventReceived
from app.services.event_ingress_service import EventIngressService
from app.worker import start_worker, stop_worker


@asynccontextmanager
async def lifespan(_app: FastAPI):
    worker_enabled = (
        os.getenv("OB1_ENABLE_EMBEDDED_WORKER", "true").lower()
        == "true"
    )

    if worker_enabled:
        start_worker()

    yield

    if worker_enabled:
        stop_worker()


app = FastAPI(
    title="Outbox Service",
    version="0.1.0",
    description="Event routing and delivery service",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin_project_router)
app.include_router(admin_schema_router)
app.include_router(admin_route_router)
app.include_router(event_type_router)
app.include_router(contracts_router)
app.include_router(metrics_router)
app.include_router(auth_router)
app.include_router(api_key_router)
app.include_router(dead_letter_router)
app.include_router(project_member_router)
app.include_router(metric_definition_router)
app.include_router(runtime_router)
app.include_router(runtime_metrics_router)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "outbox",
    }


@app.post(
    "/events",
    response_model=EventReceived,
)
def receive_event(
    event: EventIn,
    _: ApiKey = Depends(
        get_current_api_key
    ),
    service: EventIngressService = Depends(
        get_event_ingress_service
    ),
):
    try:
        return service.receive_event(event)

    except IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Event already exists",
        ) from exc

    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to persist event",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@app.post("/worker/process")
def process_worker():
    return {
        "status": "disabled",
        "detail": "Worker processing will be reconnected after routing/delivery services are adapted.",
    }