import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.core.agent_dispatcher import dispatch_to_agent
from src.agents.core.events import EventBus
from src.agents.factory import AgentFactory


class DummyAgent:
    def __init__(self):
        self.bus = EventBus()
        self.session_id = "test-session"
        AgentFactory.register_instance(self.__class__.__name__, self)

    def run(self, task: str):
        return f"echo:{task}"


class HandlerAgent(DummyAgent):
    async def handle_user_message(self, user_text: str, source: str = "cli", external_metadata=None):
        self.last = (user_text, source, external_metadata)
        return f"handled:{user_text}"


@pytest.fixture
def dummy_agent():
    agent = DummyAgent()
    yield agent
    AgentFactory.unregister_instance("DummyAgent")


@pytest.fixture
def handler_agent():
    agent = HandlerAgent()
    yield agent
    AgentFactory.unregister_instance("HandlerAgent")


@pytest.mark.asyncio
async def test_dispatch_fallback_publishes_events(dummy_agent):
    q = await dummy_agent.bus.subscribe()

    result = await dispatch_to_agent(dummy_agent, "hello", source="cli")

    assert result == "echo:hello"
    input_event = await asyncio.wait_for(q.get(), timeout=1)
    output_event = await asyncio.wait_for(q.get(), timeout=1)

    assert input_event.type == "agent.input"
    assert input_event.payload["agent"] == "DummyAgent"
    assert output_event.type == "agent.output"
    assert output_event.payload["text"] == "echo:hello"
    assert output_event.payload["agent"] == "DummyAgent"


def test_resolve_instance_accepts_short_name(dummy_agent):
    resolved = AgentFactory.resolve_instance("dummy")
    assert resolved is dummy_agent


@pytest.mark.asyncio
async def test_dispatch_prefers_agent_handler(handler_agent):
    result = await dispatch_to_agent(handler_agent, "task please", source="dashboard")
    assert result == "handled:task please"
    assert handler_agent.last[0] == "task please"
