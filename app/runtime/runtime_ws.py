from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.runtime.runtime_event_bus import runtime_event_bus

router = APIRouter(prefix="/runtime", tags=["runtime"])


@router.websocket("/events")
async def runtime_events_websocket(websocket: WebSocket) -> None:
    """
    Stream real OB1 runtime events to the admin frontend.

    The endpoint observes backend activity only. It does not trigger,
    retry, orchestrate, or mutate business pipeline state.
    """

    await websocket.accept()
    queue = runtime_event_bus.subscribe()

    try:
        while True:
            event = await queue.get()
            await websocket.send_json(
                event.model_dump(mode="json")
            )

    except WebSocketDisconnect:
        runtime_event_bus.unsubscribe(queue)

    finally:
        runtime_event_bus.unsubscribe(queue)