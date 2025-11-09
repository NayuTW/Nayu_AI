"""
Main application entry point using smolagents architecture.
This is the new version that uses smolagents CodeAgent for the main orchestrator.
"""
import asyncio
import time
import uvicorn
import uuid
import os
import logging

from src.agents.state import SharedState
from src.agents.core.events import EventBus, InterruptPriority
from src.agents.core.registry import ToolRegistry
from src.agents.core.health import HealthChecker
from src.agents.core.store import SQLiteStore
from src.agents.core.interrupt_manager import InterruptManager
from src.agents.core.continuous_runner import ContinuousAgentRunner
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
    
    # Initialize interrupt manager
    interrupt_manager = InterruptManager(bus=bus)
    await interrupt_manager.start()
    
    # Initialize continuous agent runner
    continuous_runner = ContinuousAgentRunner(
        agent=agent,
        bus=bus,
        interrupt_manager=interrupt_manager
    )
    await continuous_runner.start()

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
    print("  '/state'         - Show agent state")
    print("  'quit'           - Exit the application")
    print("=" * 60)
    print()
    print("Agent running continuously. Type your message and press Enter.")
    print()
    
    # Non-blocking input loop using continuous runner
    try:
        async def input_loop():
            """Non-blocking input loop that queues messages."""
            while True:
                try:
                    user = await asyncio.to_thread(input, "You: ")
                except EOFError:
                    break
                
                if user.strip().lower() == "quit":
                    await interrupt_manager.signal_stop()
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
                
                if user.strip().lower() == "/state":
                    state_info = continuous_runner.get_state_info()
                    print(f"Agent State: {state_info['state']}")
                    print(f"Attention Depth: {state_info['attention_depth']}")
                    if state_info.get('current_attention'):
                        att = state_info['current_attention']
                        print(f"Current Task: {att.get('primary_task', 'None')}")
                    continue
                
                # Queue user input via interrupt manager
                await interrupt_manager.signal_user_input(
                    text=user,
                    source="cli",
                    metadata={"session_id": session_id}
                )
        
        # Subscribe to agent output events to display responses
        event_queue = await bus.subscribe()
        
        async def display_responses():
            """Display agent responses from event bus."""
            while True:
                try:
                    event = await event_queue.get()
                    
                    if event.type == "agent.output":
                        response = event.payload.get("text", "")
                        print(f"Agent: {response}")
                    
                    elif event.type == "agent.thinking":
                        # Optional: show thinking indicator
                        pass
                    
                    elif event.type == "agent.error":
                        error = event.payload.get("error", "Unknown error")
                        print(f"Error: {error}")
                
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.exception(f"Error in display loop: {e}")
        
        # Run both loops concurrently
        input_task = asyncio.create_task(input_loop())
        display_task = asyncio.create_task(display_responses())
        
        # Wait for input loop to complete (user types 'quit')
        await input_task
        
        # Cancel display task
        display_task.cancel()
        try:
            await display_task
        except asyncio.CancelledError:
            pass
    
    finally:
        # Stop continuous runner
        await continuous_runner.stop()
        
        # Stop interrupt manager
        await interrupt_manager.stop()
        
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
