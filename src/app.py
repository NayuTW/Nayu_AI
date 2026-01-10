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
from src.agents.core.agent_dispatcher import dispatch_to_agent
from src.agents.notify.notifier import Notifier
from src.agents.notify.error_speaker import ErrorSpeaker
from src.agents.tools.speech_smol import SpeechSmolTool
from src.agents.sub_agents.main_agent import MainAgent
from src.agents.factory import AgentFactory

from src.dashboard.server import init_dashboard

logger = logging.getLogger(__name__)


async def start_dashboard(bus, registry, health, store, notifier, agent):
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

    os.environ['OLLAMA_GPU_LAYERS'] = '40'
    os.environ['OLLAMA_FLASH_ATTENTION'] = '1'

    # Create session ID
    session_id = f"session-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    
    # Initialize main agent (smolagents CodeAgent)
    logger.info("Initializing MainAgent with smolagents CodeAgent...")
    agent = MainAgent(
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
    asyncio.create_task(start_dashboard(bus, registry, health, store, notifier, agent))
    
    # Start Discord bot if configured
    discord_service = await start_discord_bot(agent)
    if discord_service:
        agent.set_discord_service(discord_service)

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
    print("  'voice on'        - Enable voice notifications")
    print("  'voice off'       - Disable voice notifications")
    print("  '/reset-session'  - Clear conversation history")
    print("  '/sessions'       - List all sessions")
    print("  '/list-agents'    - List all agents and available types")
    print("  '/add-agent <type>' - Create a new managed agent")
    print("  '/remove-agent <name>' - Remove a managed agent")
    print("  '/delegate <parent> <child>' - Delegate an existing agent to another")
    print("  '/undelegate <parent> <child>' - Remove delegation between agents")
    print("  '@AgentName <message>' - Send a prompt directly to a specific agent (default: MainAgent)")
    print("  'quit'            - Exit the application")
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
            
            # Handle dynamic agent management commands
            if user.strip().lower().startswith("/add-agent"):
                parts = user.strip().split()
                if len(parts) < 2:
                    available = agent.get_available_agent_types()
                    print("Usage: /add-agent <type>")
                    if available:
                        print(f"Available types: {', '.join(available)}")
                    else:
                        print("No agent types available to create")
                    continue
                
                agent_type = parts[1].lower()
                if agent.create_managed_agent(agent_type):
                    print(f"✓ {agent_type} agent added successfully")
                else:
                    print(f"✗ Failed to add {agent_type} agent")
                continue
            
            if user.strip().lower().startswith("/remove-agent"):
                parts = user.strip().split()
                if len(parts) < 2:
                    agents_info = agent.get_managed_agents_summary()
                    print("Usage: /remove-agent <name>")
                    if agents_info:
                        print("Available agents:", ", ".join([a['name'] for a in agents_info]))
                    continue
                
                agent_name = parts[1]
                if agent.remove_managed_agent(agent_name):
                    print(f"✓ {agent_name} removed successfully")
                else:
                    print(f"✗ Failed to remove {agent_name}")
                continue
            
            if user.strip().lower().startswith("/delegate"):
                parts = user.strip().split()
                if len(parts) < 3:
                    print("Usage: /delegate <parent_agent> <child_agent>")
                    instances = AgentFactory.all_instances().keys()
                    print(f"Active instances: {', '.join(instances)}")
                    continue
                
                parent_name = parts[1]
                child_name = parts[2]
                
                parent = AgentFactory.get_instance(parent_name)
                if not parent:
                    print(f"✗ Parent agent '{parent_name}' not found")
                    continue
                
                if parent.delegate_agent(child_name):
                    print(f"✓ {child_name} delegated to {parent_name}")
                else:
                    print(f"✗ Failed to delegate {child_name} to {parent_name}")
                continue

            if user.strip().lower().startswith("/undelegate"):
                parts = user.strip().split()
                if len(parts) < 3:
                    print("Usage: /undelegate <parent_agent> <child_agent>")
                    continue
                
                parent_name = parts[1]
                child_name = parts[2]
                
                parent = AgentFactory.get_instance(parent_name)
                if not parent:
                    print(f"✗ Parent agent '{parent_name}' not found")
                    continue
                
                if parent.undelegate_agent(child_name):
                    print(f"✓ {child_name} removed from {parent_name}")
                else:
                    print(f"✗ Failed to undelegate {child_name} from {parent_name}")
                continue
            
            if user.strip().lower() == "/list-agents":
                agents_info = agent.get_managed_agents_summary()
                available = agent.get_available_agent_types()
                instances = AgentFactory.all_instances().keys()
                print(f"\nActive Agent Instances ({len(instances)}):")
                for name in instances:
                    print(f"  • {name}")
                
                print(f"\nManaged Agents of {agent.__class__.__name__} ({len(agents_info)}):")
                if agents_info:
                    for info in agents_info:
                        print(f"  • {info['name']}")
                else:
                    print("  (none)")
                print(f"\nAvailable Types to Create:")
                if available:
                    for agent_type in available:
                        print(f"  • {agent_type}")
                else:
                    print("  (none)")
                continue
            
            # Process user message (optionally targeting a specific agent)
            target_name = None
            text_to_send = user
            if user.startswith("@"):
                parts = user[1:].split(None, 1)
                if not parts:
                    print("Usage: @AgentName <message>")
                    continue
                target_name = parts[0]
                if len(parts) < 2 or not parts[1].strip():
                    print("Please provide a message after the agent name.")
                    continue
                text_to_send = parts[1].strip()

            target_agent = AgentFactory.resolve_instance(target_name, default=agent)
            if not target_agent:
                print(f"Agent '{target_name}' not found.")
                continue

            resp = await dispatch_to_agent(
                target_agent,
                text_to_send,
                source="cli",
                external_metadata={"tag": "cli", "target_agent": target_name or "MainAgent"}
            )
            safe_resp = resp.replace("\r", "").replace("\x1b", "").strip()
            print(f"{target_agent.__class__.__name__}: {safe_resp}")
            sys.stdout.flush()
            sys.stdin.flush()
            print()
            await asyncio.sleep(0.1)
    
    finally:
        # Best-effort shutdown cleanup
        try:
            agent.shutdown()
        except Exception:
            pass

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
