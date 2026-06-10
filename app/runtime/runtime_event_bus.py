import asyncio

from app.runtime.runtime_event import RuntimeEvent


class RuntimeEventBus:
    """
    In-memory asynchronous pub/sub bus for OB1 runtime events.

    The bus is process-local and designed for live admin observability.
    It is not a durable queue and must not be used for business processing.
    """

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[RuntimeEvent]] = set()

    async def publish(self, event: RuntimeEvent) -> None:
        """
        Publish a runtime event to all connected subscribers.

        Args:
            event: Runtime event to broadcast.
        """

        stale_subscribers: list[asyncio.Queue[RuntimeEvent]] = []

        for subscriber in self._subscribers:
            try:
                subscriber.put_nowait(event)
            except asyncio.QueueFull:
                stale_subscribers.append(subscriber)

        for subscriber in stale_subscribers:
            self.unsubscribe(subscriber)

    def subscribe(self) -> asyncio.Queue[RuntimeEvent]:
        """
        Register a new runtime event subscriber.

        Returns:
            Queue receiving future runtime events.
        """

        queue: asyncio.Queue[RuntimeEvent] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[RuntimeEvent]) -> None:
        """
        Remove a runtime event subscriber.

        Args:
            queue: Subscriber queue to remove.
        """

        self._subscribers.discard(queue)


runtime_event_bus = RuntimeEventBus()