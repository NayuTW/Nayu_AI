import asyncio
import time
import uvicorn
import uuid
import os

from agents.state import SharedState
from agents.core.events import EventBus
from agents.core.registry import ToolRegistry
from agents.core.health import HealthChecker
from agents.core.store import SQLiteStore
from agents.notify.notifier import Notifier
from agents.notify.error_speaker import ErrorSpeaker
from agents.tools.speech import SpeechTool
from agents.main_agent import MainAgent

from dashboard.server import init_dashboard

async def start_dashboard(bus, registry, health, store, notifier):
    from dashboard.server import app
    init_dashboard(bus, registry, health, store, notifier)
    host = os.getenv("AGENT_DASH_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_DASH_PORT", "8008"))
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()

async def main():
    state = SharedState()
    store = SQLiteStore()
    bus = EventBus(store=store)
    registry = ToolRegistry(store=store)

    speak_on_error = store.get_setting("speak_on_error", "1") == "1"
    voice_enabled = store.get_setting("voice_enabled", "0") == "1"

    speech_tool = SpeechTool(state)
    notifier = Notifier(speech_tool=speech_tool, voice_enabled=voice_enabled, speak_on_error=speak_on_error)

    store.set_setting("speak_on_error", "1" if speak_on_error else "0")
    store.set_setting("voice_enabled", "1" if voice_enabled else "0")

    session_id = f"session-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    agent = MainAgent(state=state, bus=bus, registry=registry, notifier=notifier, store=store, session_id=session_id)

    health = HealthChecker(bus=bus, interval_s=15)
    await health.start()

    error_speaker = ErrorSpeaker(bus=bus, registry=registry, notifier=notifier, line="There is a problem with my AI.", interval_s=10)
    await error_speaker.start()

    asyncio.create_task(start_dashboard(bus, registry, health, store, notifier))

    print("Agent + Dashboard running (VM) at http://<vm-ip>:8008")
    print("Type 'voice on' or 'voice off' to toggle voice; 'quit' to exit.")
    while True:
        user = input("You: ")
        if user.strip().lower() == "quit":
            break
        if user.strip().lower() == "voice on":
            notifier.set_voice(True)
            store.set_setting("voice_enabled", "1")
            print("Voice enabled.")
            continue
        if user.strip().lower() == "voice off":
            notifier.set_voice(False)
            store.set_setting("voice_enabled", "0")
            print("Voice disabled.")
            continue
        resp = await agent.handle_user_message(user)
        print("Agent:", resp)

if __name__ == "__main__":
    asyncio.run(main())