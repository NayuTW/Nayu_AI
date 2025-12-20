import asyncio
import sys
import types

import numpy as np
import pytest
from smolagents import ActionStep, RunResult
from smolagents.memory import Timing


class _DummySentenceTransformer:
    def __init__(self, *args, **kwargs):
        pass

    def encode(self, text):
        return np.zeros(3)


sys.modules["sentence_transformers"] = types.SimpleNamespace(SentenceTransformer=_DummySentenceTransformer)
pairwise_module = types.SimpleNamespace(cosine_similarity=lambda a, b: np.array([[1.0]]))
sys.modules["sklearn"] = types.SimpleNamespace(metrics=types.SimpleNamespace(pairwise=pairwise_module))
sys.modules["sklearn.metrics"] = types.SimpleNamespace(pairwise=pairwise_module)
sys.modules["sklearn.metrics.pairwise"] = pairwise_module
sys.modules["litellm"] = types.SimpleNamespace(completion=lambda **_kwargs: None)


class _DummyTool:
    def __init__(self, *args, **kwargs):
        self.name = kwargs.get("name", "dummy")
        self.description = ""
        self.os_info = {}

    @staticmethod
    def spec():
        return {}


sys.modules["src.agents.tools.webbrowser_smol"] = types.SimpleNamespace(WebBrowserSmolTool=_DummyTool)
sys.modules["src.agents.tools.desktop_smol"] = types.SimpleNamespace(DesktopSmolTool=_DummyTool)
sys.modules["src.agents.tools.vision_smol"] = types.SimpleNamespace(VisionSmolTool=_DummyTool)
sys.modules["src.agents.tools.memory_smol"] = types.SimpleNamespace(MemorySmolTool=_DummyTool)
sys.modules["src.agents.tools.speech_smol"] = types.SimpleNamespace(SpeechSmolTool=_DummyTool)
sys.modules["src.agents.tools.codeagent"] = types.SimpleNamespace(CodeAgentTool=_DummyTool)
sys.modules["src.agents.tools.app_launcher_smol"] = types.SimpleNamespace(AppLauncherSmolTool=_DummyTool)

from src.agents.main_agent_smol import MainAgentSmol
from src.agents.state import SharedState
from src.agents.core.events import EventBus
from src.agents.core.registry import ToolRegistry
from src.agents.notify.notifier import Notifier
from src.agents.memory.session_manager import SessionManager


class DummyStore:
    def __init__(self):
        self.events = []
        self.examples = []

    def append_event(self, type_, payload, ts=None):
        self.events.append({"type": type_, "payload": payload, "ts": ts})

    def append_example(self, **kwargs):
        self.examples.append(kwargs)
        return len(self.examples)

    def upsert_tool_stats(self, stats):
        return stats

    def flush(self):
        return None


class DummyEmbedder:
    def encode(self, text):
        return np.zeros(3)


class DummyCallbacks:
    def __init__(self):
        self._callbacks = []

    def register(self, step_cls, callback):
        self._callbacks.append((step_cls, callback))


class FakeAgent:
    def __init__(self, run_result):
        self.run_result = run_result
        self.step_callbacks = DummyCallbacks()

    def run(self, *_args, **_kwargs):
        for step_cls, callback in self.step_callbacks._callbacks:
            step = step_cls(step_number=1, timing=Timing(0, 0), observations="obs from callback")
            callback(step, agent=self)
        return self.run_result


def test_handle_user_message_collects_action_steps():
    store = DummyStore()
    bus = EventBus(store=store)
    registry = ToolRegistry(store=store)
    notifier = Notifier(speech_tool=None, voice_enabled=False, speak_on_error=False)

    agent = MainAgentSmol.__new__(MainAgentSmol)
    agent.state = SharedState()
    agent.bus = bus
    agent.registry = registry
    agent.notifier = notifier
    agent.store = store
    agent.session_id = "test-session"
    agent.os_context = ""
    agent.tool_embedder = DummyEmbedder()
    agent.tool_embeddings = {"dummy": agent.tool_embedder.encode("dummy")}
    agent.tools = []
    agent.session_manager = SessionManager(max_messages=5, summary_interval=100)
    agent._latest_action_steps = []

    run_result = RunResult(
        output="final answer",
        state="success",
        steps=[{"step_number": 1, "observations": "obs from result"}],
        token_usage=None,
        timing=Timing(0, 0),
    )
    agent.agent = FakeAgent(run_result)
    agent._register_action_step_callback()

    response = asyncio.run(agent.handle_user_message("hello", source="test"))

    assert response == "final answer"
    assert agent._latest_action_steps, "Action steps should be recorded"
    assert agent.state.last_observation == "obs from result"
    step_events = [e for e in store.events if e["type"] == "agent.steps"]
    assert step_events, "agent.steps event should be published"
