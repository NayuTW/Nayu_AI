from dataclasses import dataclass, field
from typing import Any

@dataclass
class SharedState:
    goals: str = ""
    plan: str = ""
    last_observation: str = ""
    memory_digest: str = ""
    open_tasks: str = ""
    scratchpad: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def build_context(self, memory_digest: str) -> str:
        return (
            f"Goals: {self.goals}\n"
            f"Plan: {self.plan}\n"
            f"Open tasks: {self.open_tasks}\n"
            f"Last observation: {self.last_observation}\n"
            f"Scratchpad: {self.scratchpad}\n"
            f"Memory digest: {memory_digest}\n"
        )

    def merge_delta(self, delta: dict[str, Any]):
        for k, v in delta.items():
            if hasattr(self, k) and isinstance(getattr(self, k), str):
                setattr(self, k, v)
            else:
                self.extra[k] = v