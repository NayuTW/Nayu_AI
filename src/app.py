"""
Main application entry point using smolagents architecture.
This is the new version that uses smolagents CodeAgent for the main orchestrator.
"""
import asyncio
import sys
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
from src.agents.tools.speech_smol import SpeechSmolTool
from src.agents.main_agent_smol import MainAgentSmol

from src.dashboard.server import init_dashboard

logger = logging.getLogger(__name__)


async def start_dashboard(bus, registry, health, store, notifier):
    """Start the FastAPI dashboard server."""
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
        respond_mode = os.getenv("DISCORD_RESPOND_MODE", "mention")
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
    """Main application entry point."""
    # Initialize core infrastructure
    state = SharedState()
    store = SQLiteStore()
    bus = EventBus(store=store)
    registry = ToolRegistry(store=store)

    # Initialize notifier
    speak_on_error = store.get_setting("speak_on_error", "1") == "1"
    voice_enabled = store.get_setting("voice_enabled", "0") == "1"

    try:
        speech_tool = SpeechSmolTool()
        notifier = Notifier(speech_tool=speech_tool, voice_enabled=voice_enabled, speak_on_error=speak_on_error)
    except Exception as e:
        logger.warning(f"Could not initialize speech tool for notifier: {e}")
        notifier = Notifier(speech_tool=None, voice_enabled=False, speak_on_error=speak_on_error)

    store.set_setting("speak_on_error", "1" if speak_on_error else "0")
    store.set_setting("voice_enabled", "1" if voice_enabled else "0")

    os.environ['OLLAMA_GPU_LAYERS'] = '40'
    os.environ['OLLAMA_FLASH_ATTENTION'] = '1'

    # Create session ID
    session_id = f"session-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    
    # Initialize main agent (smolagents CodeAgent)
    logger.info("Initializing MainAgentSmol with smolagents CodeAgent...")
    agent = MainAgentSmol(
        state=state,
        bus=bus,
        registry=registry,
        notifier=notifier,
        store=store,
        session_id=session_id
    )

    # Start health checker
    health = HealthChecker(bus=bus, interval_s=15)
    await health.start()

    # Start error speaker
    error_speaker = ErrorSpeaker(
        bus=bus,
        registry=registry,
        notifier=notifier,
        line="There is a problem with my AI.",
        interval_s=10
    )
    await error_speaker.start()

    # Start periodic database flush task
    async def periodic_flush():
        while True:
            await asyncio.sleep(5)  # Flush every 5 seconds
            try:
                store.flush()
            except Exception as e:
                logger.warning(f"Failed to flush store: {e}")
    
    flush_task = asyncio.create_task(periodic_flush())

    # Start dashboard
    asyncio.create_task(start_dashboard(bus, registry, health, store, notifier))
    
    # Start Discord bot if configured
    discord_service = await start_discord_bot(agent)

    # Add Discord tool to main agent if available
    if discord_service:
        try:
            # Add the smolagents-compatible Discord tool to the main agent
            if agent.add_discord_tool(discord_service):
                logger.info("Discord tool integrated into main agent")
            
            # Also add Discord tool to CodeAgent's allowed tools for nested execution
            try:
                from src.agents.tools.discord_smol import DiscordSendChannelTool
                codeexec_rt = agent.registry.get("codeexec")
                if codeexec_rt and hasattr(codeexec_rt.impl, "allowed_tools"):
                    codeexec_rt.impl.allowed_tools.append(DiscordSendChannelTool(discord_service))
                    logger.info("Added DiscordSendChannelTool to nested CodeAgent")
            except Exception as e:
                logger.exception("Failed to add Discord to nested CodeAgent: %s", e)
        except Exception as e:
            logger.exception("Failed to integrate Discord tool: %s", e)

    # Print startup information
    print("=" * 60)
    print("Nayu_AI Agent + Dashboard (smolagents architecture)")
    print("=" * 60)
    print(f"Dashboard: http://<vm-ip>:8008")
    if discord_service:
        print("Discord bot: RUNNING")
    print(f"Session: {session_id}")
    print()
    print("Commands:")
    print("  'voice on'       - Enable voice notifications")
    print("  'voice off'      - Disable voice notifications")
    print("  '/reset-session' - Clear conversation history")
    print("  '/sessions'      - List all sessions")
    print("  'quit'           - Exit the application")
    print("=" * 60)
    print()
    
    try:
        while True:
            try:
                user = await asyncio.to_thread(input, "You: ")
                user = user.strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting...")
                break
            except Exception as e:
                logger.warning(f"Input error: {e}")
                continue
            if not user:
                continue
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
            
            # Handle session commands
            if user.strip().lower() == "/reset-session":
                agent.reset_session()
                print(f"Session {session_id} has been reset. Conversation history cleared.")
                continue
            
            if user.strip().lower() == "/sessions":
                sessions = agent.list_sessions()
                if sessions:
                    print(f"Available sessions ({len(sessions)}):")
                    for s in sessions:
                        current = " (current)" if s == session_id else ""
                        print(f"  - {s}{current}")
                else:
                    print("No saved sessions found.")
                continue
            
            # Process user message
            resp = await agent.handle_user_message(
                user,
                source="cli",
                external_metadata={"tag": "cli"}
            )
            safe_resp = resp.replace("\r", "").replace("\x1b", "").strip()
            print(f"Agent: {safe_resp}")
            sys.stdout.flush()
            sys.stdin.flush()
            print()
            await asyncio.sleep(0.1)
    
    finally:
        # Cancel periodic flush task
        if 'flush_task' in locals():
            flush_task.cancel()
            try:
                await flush_task
            except asyncio.CancelledError:
                pass
        
        # Cleanup Discord bot on exit
        if discord_service:
            logger.info("Shutting down Discord bot...")
            await discord_service.stop()
        
        # Flush session cache and any pending database events
        logger.info("Flushing session cache and pending database events...")
        agent.session_manager.flush_cache()
        store.flush()
        store.close()


if __name__ == "__main__":
    asyncio.run(main())
