from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any

app = FastAPI(
    title="Fake BlackHole Receiver",
    version="0.1.0",
)


class ReceivedEvent(BaseModel):
    event_id: str
    project: str
    event_type: str
    schema_version: str
    payload: dict[str, Any]


@app.post("/events")
def receive_event(event: ReceivedEvent):
    print("Fake BlackHole received event:")
    print(event.model_dump())

    return {
        "status": "received_by_fake_blackhole",
        "event_id": event.event_id,
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "fake_blackhole_receiver",
    }