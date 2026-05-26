from fastapi import FastAPI, Request

app = FastAPI(
    title="Fake BlackHole Receiver",
    version="0.1.0",
)


@app.post("/events")
async def receive_event(request: Request):
    payload = await request.json()

    print("\n=== Fake BlackHole received payload ===")
    print(payload)

    return {
        "status": "received_by_fake_blackhole",
        "received": True,
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "fake_blackhole_receiver",
    }