import argparse
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4

import httpx


API_URL = os.getenv(
    "OB1_INGRESS_URL",
    "http://127.0.0.1:8000/events",
)

API_KEY = os.getenv("OB1_API_KEY")


def build_payload(event_type_id: int) -> dict:
    base_payload = {
        "source": random.choice(["Hermes agent", "BlackHole", "Runtime Simulator"]),
        "summary": f"Generated article summary {uuid4()}",
        "main_topic": random.choice(["Article analyzed", "Runtime load", "Metric extraction"]),
        "document_id": str(random.randint(1, 1_000_000)),
    }

    if event_type_id == 4:
        base_payload["duration_seconds"] = random.randint(1, 180)

    return {
        "project_id": 1,
        "event_type_id": event_type_id,
        "json_version_internal": "1.0",
        "payload": base_payload,
        "correlation_id": f"sim-{random.randint(1, 100)}",
    }


def send_event(event_type_id: int) -> tuple[int, str]:
    if not API_KEY:
        raise RuntimeError("Missing OB1_API_KEY environment variable")

    headers = {
        "X-API-Key": API_KEY,
    }

    response = httpx.post(
        API_URL,
        json=build_payload(event_type_id),
        headers=headers,
        timeout=10.0,
    )

    return response.status_code, response.text[:300]


def run_simulation(
    total: int,
    concurrency: int,
    delay_ms: int,
    event_type_ids: list[int],
) -> None:
    started_at = time.time()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = []

        for _ in range(total):
            event_type_id = random.choice(event_type_ids)

            futures.append(
                executor.submit(send_event, event_type_id)
            )

            if delay_ms > 0:
                time.sleep(delay_ms / 1000)

        status_counts: dict[int, int] = {}

        for future in as_completed(futures):
            status_code, body = future.result()
            status_counts[status_code] = status_counts.get(status_code, 0) + 1

            if status_code >= 400:
                print(f"[ERROR] status={status_code} body={body}")

    elapsed = time.time() - started_at

    print("Simulation finished")
    print(f"total={total}")
    print(f"concurrency={concurrency}")
    print(f"elapsed_seconds={elapsed:.2f}")
    print(f"status_counts={status_counts}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OB1 runtime traffic simulator",
    )

    parser.add_argument(
        "--mode",
        choices=["nominal", "burst", "slow", "failures"],
        default="nominal",
    )

    parser.add_argument(
        "--total",
        type=int,
        default=100,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.mode == "nominal":
        run_simulation(
            total=args.total,
            concurrency=5,
            delay_ms=100,
            event_type_ids=[1, 4],
        )

    if args.mode == "burst":
        run_simulation(
            total=args.total,
            concurrency=30,
            delay_ms=0,
            event_type_ids=[1, 4],
        )

    if args.mode == "slow":
        run_simulation(
            total=args.total,
            concurrency=1,
            delay_ms=1000,
            event_type_ids=[1, 4],
        )

    if args.mode == "failures":
        run_simulation(
            total=args.total,
            concurrency=10,
            delay_ms=50,
            event_type_ids=[1, 4],
        )


if __name__ == "__main__":
    main()