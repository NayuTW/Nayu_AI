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


async def start_dashboard(bus, registry, health, store, notifier, agent=None):
    """Start the FastAPI dashboard server."""
    from src.dashboard.server import app
    init_dashboard(bus, registry, health, store, notifier, agent)
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
    
    # Initialize main agent (smolagents CodeAgent) with persona
    logger.info("Initializing MainAgentSmol with smolagents CodeAgent and persona system...")
    
    # Load persona from store if available
    from src.agents.persona.persona import Persona, DEFAULT_PERSONA
    try:
        persona_data = {}
        for key in ['name', 'playfulness', 'curiosity', 'helpfulness', 'talkativeness', 'humor_level', 'creativity', 'formality']:
            val = store.get_setting(f"persona_{key}")
            if val:
                try:
                    persona_data[key] = float(val) if key != 'name' else val
                except ValueError:
                    pass
        
        if persona_data:
            # Create persona with stored settings
            persona = Persona(**{**DEFAULT_PERSONA.to_dict(), **persona_data})
        else:
            persona = DEFAULT_PERSONA
    except Exception as e:
        logger.warning(f"Could not load persona settings: {e}")
        persona = DEFAULT_PERSONA
    
    agent = MainAgentSmol(
        state=state,
        bus=bus,
        registry=registry,
        notifier=notifier,
        store=store,
        session_id=session_id,
        persona=persona
    )

    # Start proactive scheduler
    proactive_enabled = store.get_setting("proactive_enabled", "1") == "1"
    agent.proactive_scheduler.enabled = proactive_enabled
    await agent.proactive_scheduler.start()
    logger.info(f"Proactive scheduler started (enabled={proactive_enabled})")

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

    # Start dashboard with agent for persona access
    asyncio.create_task(start_dashboard(bus, registry, health, store, notifier, agent))
    
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

    # Subscribe to proactive events for CLI display
    async def proactive_listener():
        """Listen for proactive messages and display them in CLI."""
        event_queue = await bus.subscribe()
        while True:
            try:
                event = await event_queue.get()
                if event.type == "agent.proactive":
                    print(f"\n{agent.persona.name}: {event.payload.get('text', '')}")
                    print("You: ", end="", flush=True)
            except Exception as e:
                logger.exception(f"Error in proactive listener: {e}")
    
    proactive_task = asyncio.create_task(proactive_listener())

    # Print startup information
    print("=" * 60)
    print("Nayu_AI Agent + Dashboard (with Character System)")
    print("=" * 60)
    print(f"Dashboard: http://<vm-ip>:8008")
    if discord_service:
        print("Discord bot: RUNNING")
        discord_proactive_state = agent.get_discord_proactive_state()
        print(f"Discord proactive: {'ON' if discord_proactive_state['enabled'] else 'OFF'}")
    print(f"Session: {session_id}")
    print(f"Persona: {agent.persona.name} (proactive: {'ON' if proactive_enabled else 'OFF'})")
    print()
    print("Commands:")
    print("  'voice on'       - Enable voice notifications")
    print("  'voice off'      - Disable voice notifications")
    print("  'proactive on'   - Enable proactive behavior")
    print("  'proactive off'  - Disable proactive behavior")
    if discord_service:
        print("  'discord proactive on'      - Enable Discord proactive messaging")
        print("  'discord proactive off'     - Disable Discord proactive messaging")
        print("  'discord add user <target>' - Add user to proactive DM list")
        print("  'discord rm user <target>'  - Remove user from proactive DM list")
        print("  'discord add channel <target> [guild_id]' - Add channel to proactive list")
        print("  'discord rm channel <target> [guild_id]'  - Remove channel from proactive list")
        print("  'discord list'   - Show Discord proactive configuration")
    print("  '/mood'          - Show current mood state")
    print("  '/persona'       - Show persona details")
    print("  '/reset-session' - Clear conversation history")
    print("  '/sessions'      - List all sessions")
    print("  'quit'           - Exit the application")
    print("=" * 60)
    print()
    
    try:
        while True:
            try:
                user = await asyncio.to_thread(input, "You: ")
            except EOFError:
                break
            
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
            
            if user.strip().lower() == "proactive on":
                agent.set_proactive_enabled(True)
                print("Proactive behavior enabled.")
                continue
            
            if user.strip().lower() == "proactive off":
                agent.set_proactive_enabled(False)
                print("Proactive behavior disabled.")
                continue
            
            # Discord proactive commands
            if discord_service:
                if user.strip().lower() == "discord proactive on":
                    agent.set_discord_proactive_enabled(True)
                    print("Discord proactive messaging enabled.")
                    continue
                
                if user.strip().lower() == "discord proactive off":
                    agent.set_discord_proactive_enabled(False)
                    print("Discord proactive messaging disabled.")
                    continue
                
                if user.strip().lower().startswith("discord add user "):
                    target = user.strip()[17:].strip()
                    if target:
                        agent.add_discord_proactive_user(target)
                        print(f"Added user '{target}' to Discord proactive DM list.")
                    else:
                        print("Error: Please provide a user target (e.g., '@username' or user ID)")
                    continue
                
                if user.strip().lower().startswith("discord rm user "):
                    target = user.strip()[16:].strip()
                    if target:
                        agent.remove_discord_proactive_user(target)
                        print(f"Removed user '{target}' from Discord proactive DM list.")
                    else:
                        print("Error: Please provide a user target")
                    continue
                
                if user.strip().lower().startswith("discord add channel "):
                    parts = user.strip()[20:].strip().split()
                    if parts:
                        channel_target = parts[0]
                        guild_id = None
                        if len(parts) > 1 and parts[1]:
                            try:
                                guild_id = int(parts[1])
                            except ValueError:
                                print(f"Error: Invalid guild ID '{parts[1]}'. Must be a number.")
                                continue
                        agent.add_discord_proactive_channel(channel_target, guild_id)
                        print(f"Added channel '{channel_target}' to Discord proactive list.")
                    else:
                        print("Error: Please provide a channel target (e.g., '#general' or channel ID)")
                    continue
                
                if user.strip().lower().startswith("discord rm channel "):
                    parts = user.strip()[19:].strip().split()
                    if parts:
                        channel_target = parts[0]
                        guild_id = None
                        if len(parts) > 1 and parts[1]:
                            try:
                                guild_id = int(parts[1])
                            except ValueError:
                                print(f"Error: Invalid guild ID '{parts[1]}'. Must be a number.")
                                continue
                        agent.remove_discord_proactive_channel(channel_target, guild_id)
                        print(f"Removed channel '{channel_target}' from Discord proactive list.")
                    else:
                        print("Error: Please provide a channel target")
                    continue
                
                if user.strip().lower() == "discord list":
                    discord_state = agent.get_discord_proactive_state()
                    print("Discord Proactive Configuration:")
                    print(f"  Enabled: {discord_state['enabled']}")
                    print(f"  Policy Enabled: {discord_state['policy_enabled']}")
                    print(f"  Known Users ({len(discord_state['known_users'])}):")
                    for u in discord_state['known_users']:
                        print(f"    - {u}")
                    print(f"  Known Channels ({len(discord_state['known_channels'])}):")
                    for c in discord_state['known_channels']:
                        guild_info = f" (guild: {c.get('guild_id')})" if c.get('guild_id') else ""
                        print(f"    - {c['target']}{guild_info}")
                    continue
            
            if user.strip().lower() == "/mood":
                mood_state = agent.mood_tracker.get_state()
                print(f"Current mood: {mood_state['mood_description']}")
                print(f"Recent sentiment: {mood_state['recent_sentiment']}")
                print(f"Recent engagement: {mood_state['recent_engagement']}")
                continue
            
            if user.strip().lower() == "/persona":
                persona_state = agent.get_persona_state()
                p = persona_state['persona']
                print(f"Persona: {p['name']}")
                print(f"  Playfulness: {p['playfulness']:.1f}")
                print(f"  Curiosity: {p['curiosity']:.1f}")
                print(f"  Helpfulness: {p['helpfulness']:.1f}")
                print(f"  Talkativeness: {p['talkativeness']:.1f}")
                print(f"  Humor: {p['humor_level']:.1f}")
                print(f"Mood: {persona_state['mood']['mood_description']}")
                continue
            
            # Handle session commands
            if user.strip().lower() == "/reset-session":
                # Note: reset_session method doesn't exist in current implementation
                # We'll just note this for now
                print(f"Session reset not implemented yet.")
                continue
            
            if user.strip().lower() == "/sessions":
                # Note: list_sessions method doesn't exist in current implementation
                print("Session listing not implemented yet.")
                continue
            
            # Process user message
            resp = await agent.handle_user_message(
                user,
                source="cli",
                external_metadata={"tag": "cli"}
            )
            print(f"Agent: {resp}")
    
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
