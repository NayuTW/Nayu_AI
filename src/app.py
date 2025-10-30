import asyncio
import time
import uvicorn
import uuid
import os
import logging

from src.agents.state import SharedState
from src.agents.core.events import EventBus
from src.agents.core.registry import ToolRegistry
from src.agents.core.health import HealthChecker
from src.agents.core.store import SQLiteStore
from src.agents.notify.notifier import Notifier
from src.agents.notify.error_speaker import ErrorSpeaker
from src.agents.tools.speech import SpeechTool
from src.agents.main_agent import MainAgent

from src.dashboard.server import init_dashboard

logger = logging.getLogger(__name__)

async def start_dashboard(bus, registry, health, store, notifier):
    from src.dashboard.server import app
    init_dashboard(bus, registry, health, store, notifier)
    host = os.getenv("AGENT_DASH_HOST", "0.0.0.0")
    port = int(os.getenv("AGENT_DASH_PORT", "8008"))
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()

async def start_discord_bot(agent):
    """Start Discord bot service if DISCORD_BOT_TOKEN is set."""
    discord_token = os.getenv("DISCORD_BOT_TOKEN")
    if not discord_token:
        logger.info("DISCORD_BOT_TOKEN not set, Discord bot will not start")
        return None
    
    try:
        from src.integrations.discord_bot import DiscordBotService
        
        # Configure Discord bot
        respond_mode = os.getenv("DISCORD_RESPOND_MODE", "mention")  # passive, mention, prefix, all
        command_prefix = os.getenv("DISCORD_COMMAND_PREFIX", "!")
        read_only = os.getenv("DISCORD_READ_ONLY", "false").lower() == "true"
        
        discord_service = DiscordBotService(
            agent=agent,
            token=discord_token,
            respond_mode=respond_mode,
            command_prefix=command_prefix,
            read_only=read_only,
        )
        
        await discord_service.start()
        logger.info("Discord bot started successfully in '%s' mode", respond_mode)
        return discord_service
    except Exception as e:
        logger.exception("Failed to start Discord bot: %s", e)
        return None

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
    
    # Start Discord bot if configured
    discord_service = await start_discord_bot(agent)

    print("Agent + Dashboard running (VM) at http://<vm-ip>:8008")
    if discord_service:
        print("Discord bot is running")
    print("Type 'voice on' or 'voice off' to toggle voice; 'quit' to exit.")
    
    try:
        while True:
            user = await asyncio.to_thread(input,"You: ")
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
            # Pass source + minimal metadata so agent can distinguish CLI vs Discord
            resp = await agent.handle_user_message(user, source="cli", external_metadata={"tag": "cli"})
            print("Agent:", resp)
    finally:
        # Cleanup Discord bot on exit
        if discord_service:
            logger.info("Shutting down Discord bot...")
            await discord_service.stop()

if __name__ == "__main__":
    asyncio.run(main())
