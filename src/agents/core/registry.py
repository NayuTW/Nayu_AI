import time
from dataclasses import dataclass, field
from typing import Any, Optional

@dataclass
class ToolStats:
    enabled: bool = True
    calls: int = 0
    failures: int = 0
    last_error: str = ""
    last_latency_ms: float = 0.0
    avg_latency_ms: float = 0.0
    failure_streak: int = 0
    last_update_ts: float = 0.0

@dataclass
class RegisteredTool:
    name: str
    impl: Any
    spec: dict[str, Any]
    stats: ToolStats = field(default_factory=ToolStats)
    circuit_breaker_threshold: int = 3

class ToolRegistry:
    def __init__(self, store=None):
        self._tools: dict[str, RegisteredTool] = {}
        self._store = store

    def register(self, name: str, impl: Any, spec: dict[str, Any], breaker_threshold: int = 3):
        self._tools[name] = RegisteredTool(name=name, impl=impl, spec=spec, circuit_breaker_threshold=breaker_threshold)
        self._persist(name)

    def is_enabled(self, name: str) -> bool:
        t = self._tools.get(name)
        return bool(t and t.stats.enabled)

    def enable(self, name: str, enabled: bool):
        if name in self._tools:
            t = self._tools[name]
            t.stats.enabled = enabled
            if enabled:
                t.stats.failure_streak = 0
            t.stats.last_update_ts = time.time()
            self._persist(name)

    def get(self, name: str) -> Optional[RegisteredTool]:
        return self._tools.get(name)

    def list_specs(self):
        return [t.spec for t in self._tools.values()]

    def list_status(self):
        out = []
        for t in self._tools.values():
            s = t.stats
            out.append({
                "name": t.name,
                "enabled": s.enabled,
                "calls": s.calls,
                "failures": s.failures,
                "failure_streak": s.failure_streak,
                "last_latency_ms": s.last_latency_ms,
                "avg_latency_ms": s.avg_latency_ms,
                "last_error": s.last_error,
            })
        return out

    def record_success(self, name: str, latency_ms: float):
        t = self._tools.get(name)
        if not t: return
        s = t.stats
        s.calls += 1
        s.last_latency_ms = latency_ms
        alpha = 0.2
        s.avg_latency_ms = latency_ms if s.avg_latency_ms == 0 else (alpha * latency_ms + (1 - alpha) * s.avg_latency_ms)
        s.failure_streak = 0
        s.last_update_ts = time.time()
        self._persist(name)

    def record_failure(self, name: str, error: str):
        t = self._tools.get(name)
        if not t: return
        s = t.stats
        s.calls += 1
        s.failures += 1
        s.failure_streak += 1
        s.last_error = error[:500]
        s.last_update_ts = time.time()
        if s.failure_streak >= t.circuit_breaker_threshold:
            s.enabled = False
        self._persist(name)

    def _persist(self, name: str):
        if not self._store: return
        t = self._tools.get(name)
        if not t: return
        s = t.stats
        row = {
            "tool_name": t.name,
            "enabled": s.enabled,
            "calls": s.calls,
            "failures": s.failures,
            "failure_streak": s.failure_streak,
            "last_latency_ms": s.last_latency_ms,
            "avg_latency_ms": s.avg_latency_ms,
            "last_error": s.last_error,
            "last_update_ts": s.last_update_ts,
        }
        try:
            self._store.upsert_tool_stats(row)
        except Exception:
            pass