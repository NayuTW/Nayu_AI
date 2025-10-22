import asyncio
import socket
import aiohttp
from typing import Dict
import os

class HealthChecker:
    def __init__(self, bus, interval_s: int = 15):
        self.bus = bus
        self.interval_s = interval_s
        self._task = None
        self._running = False

    async def start(self):
        if self._task: return
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            self._task = None

    async def _loop(self):
        while self._running:
            status = await self._gather()
            await self.bus.publish("health.update", status)
            await asyncio.sleep(self.interval_s)

    async def _gather(self) -> Dict:
        status: Dict[str, Dict] = {}

        try:
            async with aiohttp.ClientSession() as s:
                async with s.get("http://localhost:11434/api/tags", timeout=5) as r:
                    ok = r.status == 200
                    status["ollama"] = {"ok": ok}
        except Exception as e:
            status["ollama"] = {"ok": False, "error": str(e)}

        try:
            ok = os.path.exists(".chroma")
            status["chromadb"] = {"ok": ok}
        except Exception as e:
            status["chromadb"] = {"ok": False, "error": str(e)}

        try:
            socket.gethostbyname("example.com")
            status["network_dns"] = {"ok": True}
        except Exception as e:
            status["network_dns"] = {"ok": False, "error": str(e)}

        return status