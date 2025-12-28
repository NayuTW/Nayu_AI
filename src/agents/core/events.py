import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class Event:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=lambda: time.time())

class EventBus:
    def __init__(self, store=None):
        self._subscribers: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        self._store = store  # Optional SQLiteStore

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        async with self._lock:
            self._subscribers.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue):
        async with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    async def publish(self, event_type: str, payload: Dict[str, Any]):
        ev = Event(type=event_type, payload=payload)
        if self._store:
            try:
                self._store.append_event(ev.type, ev.payload, ts=ev.ts)
            except Exception:
                pass
        # Avoid creating a new list on every publish
        async with self._lock:
            subscribers = self._subscribers.copy()
        for q in subscribers:
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                pass

    def emit(self, event_type: str, payload: Any = None):
        """
        Synchronous wrapper for publish. 
        Uses asyncio.create_task to publish the event without blocking.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.publish(event_type, payload))
        except RuntimeError:
            # No running loop, just ignore or log
            pass
