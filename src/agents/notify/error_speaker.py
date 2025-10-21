import asyncio
from typing import Optional

from agents.core.events import EventBus
from agents.core.registry import ToolRegistry
from agents.notify.notifier import Notifier

class ErrorSpeaker:
    """
    Speaks a static line every interval while errors are active and speak_on_error+voice are enabled.
    """
    def __init__(self, bus: EventBus, registry: ToolRegistry, notifier: Notifier, line: str = "There is a problem with my AI.", interval_s: int = 10):
        self.bus = bus
        self.registry = registry
        self.notifier = notifier
        self.line = line
        self.interval_s = interval_s
        self._running = False
        self._loop_task: Optional[asyncio.Task] = None
        self._active_error = False

    async def start(self):
        if self._running: return
        self._running = True
        asyncio.create_task(self._listen())
        self._loop_task = asyncio.create_task(self._speak_loop())

    async def stop(self):
        self._running = False
        if self._loop_task:
            self._loop_task.cancel()
            self._loop_task = None

    async def _listen(self):
        q = await self.bus.subscribe()
        try:
            while self._running:
                ev = await q.get()
                if ev.type in ("tool.error",):
                    self._active_error = True
                elif ev.type in ("tool.success",):
                    self._active_error = any(rt.stats.failure_streak > 0 for rt in self.registry._tools.values())
                elif ev.type == "health.update":
                    payload = ev.payload or {}
                    if any(not v.get("ok", False) for v in payload.values()):
                        self._active_error = True
                    else:
                        self._active_error = any(rt.stats.failure_streak > 0 for rt in self.registry._tools.values())
        finally:
            await self.bus.unsubscribe(q)

    async def _speak_loop(self):
        while self._running:
            if self._active_error and self.notifier.speak_on_error and self.notifier.voice_enabled:
                await self.notifier.alert(self.line)
            await asyncio.sleep(self.interval_s)