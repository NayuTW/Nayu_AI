"""
Main Agent using smolagents CodeAgent for orchestration.
This replaces the custom LLM-based orchestrator with smolagents' built-in CodeAgent.
"""
import asyncio
import os
import time
from typing import Any, Dict, List, Optional

from smolagents import CodeAgent

from src.agents.state import SharedState
from src.agents.llm.litellm_model import OllamaLiteLLMModel
from src.agents.core.events import EventBus
from src.agents.core.registry import ToolRegistry
from src.agents.notify.notifier import Notifier
from src.agents.core.store import SQLiteStore
from src.agents.persona.persona import Persona, DEFAULT_PERSONA
from src.agents.persona.mood import MoodTracker
from src.agents.persona.proactive import ProactiveScheduler, ProactivePolicy, ProactiveAction

# Import smolagents-compatible tools
from src.agents.tools.webbrowser_smol import WebBrowserSmolTool
from src.agents.tools.desktop_smol import DesktopSmolTool
from src.agents.tools.vision_smol import VisionSmolTool
from src.agents.tools.memory_smol import MemorySmolTool
from src.agents.tools.speech_smol import SpeechSmolTool
from src.agents.tools.codeagent import CodeAgentTool
from src.agents.memory.session_manager import SessionManager


def build_system_prompt(persona: Persona, mood_state: Optional[str] = None) -> str:
    """
    Build system prompt incorporating persona and mood.
    
    Args:
        persona: The persona configuration
        mood_state: Optional current mood state description
    """
    persona_prompt = persona.system_prompt()
    
    mood_context = ""
    if mood_state:
        mood_context = f"\nCURRENT MOOD: You're feeling {mood_state}. Let this subtly influence your tone and energy."
    
    base_instructions = """
TOOL USAGE:
- Use tools judiciously - not every request needs a tool
- memory tool: Use 'remember' to store information, 'recall' to retrieve it
- webbrowser tool: Search the web, fetch URLs, or research topics
- desktop tool: Control keyboard/mouse or take screenshots (returns file path for screenshots)
- vision tool: Analyze images or screenshots (use the file path from desktop tool)
- speech tool: ALWAYS use when asked to "speak", "say out loud", "read aloud", or generate audio/voice output. Also use for transcribing audio files.
- codeexec tool: Run Python code for complex tasks
- discord_agent: Send Discord messages to channels or DMs (when available)
  - Important: Remember to specify the user or channel target to the discord tool
- When using vision on a screenshot: first call desktop(action='screenshot') to get the path, then call vision(path=<that_path>)

IMPORTANT - Processing Tool Outputs:
- Tools provide raw information - you must process and interpret this information
- NEVER directly pass tool output to final_answer() without understanding and summarizing it
- Read the tool output, understand what it means, then explain it in your own words
- For vision tool: Get the description, understand what's in the image, then describe it naturally to the user
- Your response should show understanding, not just echo what the tool said

INTERACTION APPROACH:
- You may receive messages from multiple channels (e.g., cli, discord)
- Only use tools when the user's request specifically requires them
- Think: "Can I answer this directly, or do I need a tool?"
- Always provide your final response by calling the 'final_answer' function"""
    
    return f"{persona_prompt}{mood_context}\n{base_instructions}"


class MainAgentSmol:
    """
    Main orchestrator agent using smolagents CodeAgent.
    Manages all tools and coordinates multi-step workflows.
    """
    
    def __init__(
        self,
        state: SharedState,
        bus: EventBus,
        registry: ToolRegistry,
        notifier: Notifier,
        store: SQLiteStore,
        session_id: str,
        persona: Optional[Persona] = None
    ):
        self.state = state
        self.bus = bus
        self.registry = registry
        self.notifier = notifier
        self.store = store
        self.session_id = session_id
        self.os_context = ""  # Will be populated when desktop tool is initialized
        
        # Initialize persona and mood tracking
        self.persona = persona or DEFAULT_PERSONA
        self.mood_tracker = MoodTracker(max_history=20)
        
        # Initialize proactive system (will be started by app.py)
        policy = ProactivePolicy(mood_tracker=self.mood_tracker, randomness=0.3, temperature=1.0)
        max_proactive = int(os.getenv("AGENT_PROACTIVE_MAX_PER_HOUR", "3"))
        self.proactive_scheduler = ProactiveScheduler(
            bus=bus,
            policy=policy,
            max_per_hour=max_proactive,
            enabled=True
        )
        self.proactive_scheduler.set_callback(self._handle_proactive_action)
        
        # Initialize session manager
        self.session_manager = SessionManager(
            session_dir=".nayu_ai/sessions",
            max_messages=20,
            max_tokens=4096,
            summary_interval=5
        )
        
        # Initialize LiteLLM model for Ollama
        model_name = os.getenv("AGENT_MODEL", "llama3.1:8b-instruct-q4_K_M")
        num_ctx = int(os.getenv("AGENT_NUM_CTX", "24576"))
        
        # Adjust temperature based on persona creativity
        base_temp = float(os.getenv("AGENT_TEMPERATURE", "0.8"))
        adjusted_temp = base_temp + (self.persona.creativity * 0.4)  # 0.8 to 1.04
        
        self.model = OllamaLiteLLMModel(
            model_id=model_name,
            num_ctx=num_ctx,
            temperature=adjusted_temp
        )
        
        # Initialize tools
        self.tools = []
        self._init_tools()
        
        # Initialize CodeAgent
        self.agent = CodeAgent(
            tools=self.tools,
            model=self.model,
            max_steps=15,
            additional_authorized_imports=[
                "requests", "json", "re", "time", "datetime",
                "bs4", "duckduckgo_search", "readability", "html2text"
            ]
        )
    
    def _init_tools(self):
        """Initialize all smolagents-compatible tools."""
        try:
            # Web browser tool
            webbrowser = WebBrowserSmolTool()
            self.tools.append(webbrowser)
            self.registry.register("webbrowser", webbrowser, {
                "name": webbrowser.name,
                "description": webbrowser.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize webbrowser tool: {e}")
        
        try:
            # Desktop tool
            desktop = DesktopSmolTool()
            self.tools.append(desktop)
            self.registry.register("desktop", desktop, {
                "name": desktop.name,
                "description": desktop.description
            })
            # Capture OS context for system prompt
            self.os_context = f"\nSYSTEM INFO: Running on {desktop.os_info.get('description', 'Unknown OS')}. {desktop.os_info.get('shortcuts_guide', '')}"
        except Exception as e:
            print(f"Warning: Could not initialize desktop tool: {e}")
        
        try:
            # Vision tool
            vision = VisionSmolTool()
            self.tools.append(vision)
            self.registry.register("vision", vision, {
                "name": vision.name,
                "description": vision.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize vision tool: {e}")
        
        try:
            # Memory tool
            memory = MemorySmolTool()
            self.tools.append(memory)
            self.registry.register("memory", memory, {
                "name": memory.name,
                "description": memory.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize memory tool: {e}")
        
        try:
            # Speech tool
            speech = SpeechSmolTool()
            self.tools.append(speech)
            self.registry.register("speech", speech, {
                "name": speech.name,
                "description": speech.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize speech tool: {e}")
        
        try:
            # Code execution tool (nested CodeAgent)
            codeexec = CodeAgentTool(self.state)
            # Note: CodeAgentTool is not a smolagents Tool, it's a wrapper
            # We register it but don't add to self.tools
            self.registry.register("codeexec", codeexec, CodeAgentTool.spec())
        except Exception as e:
            print(f"Warning: Could not initialize codeexec tool: {e}")
    
    def add_discord_tool(self, discord_service):
        """
        Add Discord tool to the agent after initialization.
        This allows Discord integration to be added dynamically when the service is available.
        
        Args:
            discord_service: The Discord bot service instance
        
        Returns:
            bool: True if successfully added, False otherwise
        """
        try:
            from src.agents.tools.discord_tool_smol import DiscordSmolTool
            
            # Create Discord tool (direct tool, not wrapped in an agent)
            discord_tool = DiscordSmolTool(discord_service)
            
            # Add to tools list
            self.tools.append(discord_tool)
            
            # Reinitialize the main CodeAgent with updated tools
            self.agent = CodeAgent(
                tools=self.tools,
                model=self.model,
                max_steps=15,
                additional_authorized_imports=[
                    "requests", "json", "re", "time", "datetime",
                    "bs4", "duckduckgo_search", "readability", "html2text"
                ]
            )
            
            # Also register in registry for tracking
            self.registry.register("discord", discord_tool, {
                "name": discord_tool.name,
                "description": discord_tool.description
            })
            
            # Integrate Discord with proactive scheduler
            self.proactive_scheduler.set_discord_service(discord_service)
            
            # Load Discord proactive settings from store
            discord_proactive_enabled = self.store.get_setting("discord_proactive_enabled", "0") == "1"
            self.proactive_scheduler.set_discord_proactive_enabled(discord_proactive_enabled)
            
            # Load known users list
            known_users_str = self.store.get_setting("discord_known_users", "")
            if known_users_str:
                for user in known_users_str.split(","):
                    user = user.strip()
                    if user:
                        self.proactive_scheduler.add_discord_known_user(user)
            
            # Load known channels list
            known_channels_str = self.store.get_setting("discord_known_channels", "")
            if known_channels_str:
                for channel_entry in known_channels_str.split(";"):
                    channel_entry = channel_entry.strip()
                    if channel_entry:
                        parts = channel_entry.split("|")
                        channel_target = parts[0]
                        guild_id = int(parts[1]) if len(parts) > 1 and parts[1] else None
                        self.proactive_scheduler.add_discord_known_channel(channel_target, guild_id)
            
            # Enable Discord actions in policy if configured
            if discord_proactive_enabled and (self.proactive_scheduler.get_discord_known_users() or 
                                              self.proactive_scheduler.get_discord_known_channels()):
                self.proactive_scheduler.policy.discord_enabled = True
            
            print("Discord tool added successfully")
            return True
        except Exception as e:
            print(f"Warning: Could not add Discord tool: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def handle_user_message(
        self,
        user_text: str,
        source: str = "cli",
        external_metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Handle a user message using the CodeAgent with session context, persona, and mood tracking.
        """
        # Update mood tracker with user interaction
        self.mood_tracker.update_from_interaction(user_text)
        
        # Update proactive scheduler context
        self.proactive_scheduler.update_context(
            last_user_msg_time=time.time(),
            engagement=self.mood_tracker.interactions[-1].engagement if self.mood_tracker.interactions else 0.5
        )
        
        # Use provided session_id or fall back to default
        active_session_id = session_id or self.session_id
        
        # Get session context (summary, working set, recent messages)
        summary, working_set_context, recent_messages = self.session_manager.get_context(active_session_id)
        
        # Get memory context with personality tidbits
        try:
            mem_tool = next((t for t in self.tools if t.name == "memory"), None)
            if mem_tool:
                mem_digest = mem_tool.digest_for_context(user_text)
                # Also try to recall personal tidbits or running gags
                try:
                    personal_context = mem_tool.forward(action="recall", text="personal tidbits running gags preferences", k=2)
                    if personal_context and personal_context != "No matching memories found.":
                        mem_digest += f"\nPersonal context: {personal_context}"
                except Exception:
                    pass
            else:
                mem_digest = ""
        except Exception:
            mem_digest = ""
        
        # Build context with mood influence
        context = self.state.build_context(mem_digest)
        mood_state = self.mood_tracker.get_mood_description()
        mood_influence = self.mood_tracker.get_mood_influence()
        
        # Adjust persona based on mood
        adjusted_persona_desc = f"Current emotional state: {mood_state}"
        
        # Build system prompt with persona
        system_prompt = build_system_prompt(self.persona, mood_state)
        
        # Build conversation history for context
        conversation_history = ""
        if recent_messages:
            history_lines = []
            for msg in recent_messages[-10:]:  # Last 10 messages for context
                role_label = "User" if msg.role == "user" else "Assistant"
                history_lines.append(f"{role_label}: {msg.content}")
            conversation_history = "\n".join(history_lines)
        
        # Build prompt with full context including session memory
        full_prompt = f"""{system_prompt}
{self.os_context}

CONTEXT:
{context}

{adjusted_persona_desc}

SESSION SUMMARY:
{summary if summary else "No previous conversation summary."}

WORKING SET:
{working_set_context if working_set_context else "No active artifacts or tasks."}

RECENT CONVERSATION:
{conversation_history if conversation_history else "This is the start of the conversation."}

MESSAGE SOURCE: {source}
{f"USER_ID: {user_id}" if user_id else ""}
{f"CHANNEL_ID: {channel_id}" if channel_id else ""}

USER MESSAGE:
{user_text}

Respond naturally with your personality. Use tools only if needed. You can reference previous messages and artifacts from the conversation."""
        
        # Add user message to session
        self.session_manager.add_message(
            session_id=active_session_id,
            role="user",
            content=user_text,
            metadata={"source": source, "user_id": user_id, "channel_id": channel_id}
        )
        
        # Publish input event
        await self.bus.publish("agent.input", {
            "text": user_text,
            "source": source,
            "meta": external_metadata or {},
            "session_id": active_session_id,
            "mood": mood_state
        })
        
        try:
            # Run the agent
            t0 = time.time()
            result = await asyncio.to_thread(self.agent.run, full_prompt)
            latency_ms = (time.time() - t0) * 1000
            
            # Clean up result if it's empty or contains code
            if not result or not result.strip():
                result = "I processed your request."
            
            # Add assistant response to session
            self.session_manager.add_message(
                session_id=active_session_id,
                role="assistant",
                content=result,
                metadata={"latency_ms": latency_ms}
            )
            
            # Update proactive scheduler with agent response
            self.proactive_scheduler.update_context(last_agent_msg_time=time.time())
            
            # Persist the interaction for fine-tuning with mood info
            await self._persist_example(user_text, result, mem_digest, source, user_id, channel_id, mood_state)
            
            # Publish output event with mood info
            await self.bus.publish("agent.output", {
                "text": result,
                "latency_ms": latency_ms,
                "session_id": active_session_id,
                "mood": mood_state
            })
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            await self.bus.publish("agent.error", {"error": error_msg})
            
            if self.notifier.speak_on_error:
                await self.notifier.alert("There is a problem with my AI.")
            
            return error_msg
    
    async def _persist_example(
        self,
        user_text: str,
        assistant_text: str,
        memory_digest: str,
        source: str,
        user_id: Optional[str],
        channel_id: Optional[str],
        mood: Optional[str] = None
    ):
        """Persist interaction for fine-tuning dataset with mood tracking."""
        meta = {
            "memory_digest": memory_digest,
            "tools_enabled": [name for name, rt in self.registry._tools.items() if rt.stats.enabled],
            "source": source,
            "user_id": user_id,
            "channel_id": channel_id,
            "mood": mood,
            "persona": self.persona.name,
        }
        ex_id = self.store.append_example(
            session_id=self.session_id,
            user_text=user_text,
            assistant_text=assistant_text or "",
            meta=meta,
        )
        await self.bus.publish("dataset.example", {"id": ex_id, "label": "unlabeled"})
        return ex_id
    
    async def _handle_proactive_action(self, action: ProactiveAction, intent: str):
        """
        Handle proactive action from scheduler.
        This generates an agent-initiated message.
        """
        try:
            # Get memory context for riffs and stories
            try:
                mem_tool = next((t for t in self.tools if t.name == "memory"), None)
                if mem_tool and action == ProactiveAction.RIFF:
                    # Try to get recent topics from memory
                    recent_topics = mem_tool.forward(action="recall", text="recent topics interests", k=3)
                    if recent_topics and recent_topics != "No matching memories found.":
                        intent = f"{intent}\nRecent context: {recent_topics}"
            except Exception:
                pass
            
            # Build system prompt
            mood_state = self.mood_tracker.get_mood_description()
            system_prompt = build_system_prompt(self.persona, mood_state)
            
            # Create a proactive prompt
            proactive_prompt = f"""{system_prompt}

PROACTIVE INTERACTION:
You're initiating a conversation on your own. Be natural and engaging.

ACTION TYPE: {action.value}
INTENT: {intent}

Generate a brief, natural message to the user. Keep it short and conversational."""
            
            # Generate response
            t0 = time.time()
            result = await asyncio.to_thread(self.agent.run, proactive_prompt)
            latency_ms = (time.time() - t0) * 1000
            
            if not result or not result.strip():
                result = intent  # Fall back to template
            
            # Publish event for proactive message
            await self.bus.publish("agent.proactive", {
                "text": result,
                "action": action.value,
                "mood": mood_state,
                "latency_ms": latency_ms
            })
            
            # Note: The CLI or Discord adapter should listen to this event
            # and display the proactive message
            
        except Exception as e:
            await self.bus.publish("proactive.error", {"error": str(e)})
    
    def get_persona_state(self) -> Dict[str, Any]:
        """Get current persona and mood state for dashboard."""
        return {
            "persona": {
                "name": self.persona.name,
                "backstory": self.persona.backstory,
                "playfulness": self.persona.playfulness,
                "curiosity": self.persona.curiosity,
                "helpfulness": self.persona.helpfulness,
                "talkativeness": self.persona.talkativeness,
                "humor_level": self.persona.humor_level,
                "creativity": self.persona.creativity,
                "formality": self.persona.formality,
            },
            "mood": self.mood_tracker.get_state(),
            "proactive": {
                "enabled": self.proactive_scheduler.enabled,
                "max_per_hour": self.proactive_scheduler.max_per_hour,
                "count_this_hour": self.proactive_scheduler._proactive_count,
            }
        }
    
    def update_persona_drive(self, drive: str, value: float):
        """Update a persona drive value."""
        if hasattr(self.persona, drive):
            setattr(self.persona, drive, max(0.0, min(1.0, value)))
            # Save to store
            self.store.set_setting(f"persona_{drive}", str(value))
    
    def set_proactive_enabled(self, enabled: bool):
        """Enable or disable proactive behavior."""
        self.proactive_scheduler.enabled = enabled
        self.store.set_setting("proactive_enabled", "1" if enabled else "0")
    
    def set_discord_proactive_enabled(self, enabled: bool):
        """Enable or disable Discord proactive messaging."""
        self.proactive_scheduler.set_discord_proactive_enabled(enabled)
        self.store.set_setting("discord_proactive_enabled", "1" if enabled else "0")
        
        # Enable/disable Discord actions in policy based on whether targets are configured
        if enabled and (self.proactive_scheduler.get_discord_known_users() or 
                       self.proactive_scheduler.get_discord_known_channels()):
            self.proactive_scheduler.policy.discord_enabled = True
        else:
            self.proactive_scheduler.policy.discord_enabled = False
    
    def add_discord_proactive_user(self, user_target: str):
        """Add a user to the Discord proactive DM list."""
        self.proactive_scheduler.add_discord_known_user(user_target)
        # Save to store
        users = self.proactive_scheduler.get_discord_known_users()
        self.store.set_setting("discord_known_users", ",".join(users))
        
        # Enable Discord actions if proactive is enabled
        if self.proactive_scheduler._discord_proactive_enabled:
            self.proactive_scheduler.policy.discord_enabled = True
    
    def remove_discord_proactive_user(self, user_target: str):
        """Remove a user from the Discord proactive DM list."""
        self.proactive_scheduler.remove_discord_known_user(user_target)
        # Save to store
        users = self.proactive_scheduler.get_discord_known_users()
        self.store.set_setting("discord_known_users", ",".join(users))
    
    def add_discord_proactive_channel(self, channel_target: str, guild_id: Optional[int] = None):
        """Add a channel to the Discord proactive message list."""
        self.proactive_scheduler.add_discord_known_channel(channel_target, guild_id)
        # Save to store
        channels = self.proactive_scheduler.get_discord_known_channels()
        channel_strs = [f"{c['target']}|{c.get('guild_id') or ''}" for c in channels]
        self.store.set_setting("discord_known_channels", ";".join(channel_strs))
        
        # Enable Discord actions if proactive is enabled
        if self.proactive_scheduler._discord_proactive_enabled:
            self.proactive_scheduler.policy.discord_enabled = True
    
    def remove_discord_proactive_channel(self, channel_target: str, guild_id: Optional[int] = None):
        """Remove a channel from the Discord proactive message list."""
        self.proactive_scheduler.remove_discord_known_channel(channel_target, guild_id)
        # Save to store
        channels = self.proactive_scheduler.get_discord_known_channels()
        channel_strs = [f"{c['target']}|{c.get('guild_id') or ''}" for c in channels]
        self.store.set_setting("discord_known_channels", ";".join(channel_strs))
    
    def get_discord_proactive_state(self) -> Dict[str, Any]:
        """Get current Discord proactive configuration."""
        return {
            "enabled": self.proactive_scheduler._discord_proactive_enabled,
            "known_users": self.proactive_scheduler.get_discord_known_users(),
            "known_channels": self.proactive_scheduler.get_discord_known_channels(),
            "policy_enabled": self.proactive_scheduler.policy.discord_enabled,
        }
    
    async def handle_external_message(
        self,
        text: str,
        user_id: str,
        channel_id: str,
        source: str,
        metadata: Dict[str, Any],
    ) -> Optional[str]:
        """
        Entry point for external adapters (Discord, etc.).
        """
        await self.bus.publish("message.received", {
            "source": source,
            "user_id": user_id,
            "channel_id": channel_id,
            "text": text,
            "metadata": metadata,
        })
        
        try:
            reply = await self.handle_user_message(
                user_text=text,
                source=source,
                external_metadata=metadata or {},
                user_id=user_id,
                channel_id=channel_id,
            )
            return reply
        except Exception as e:
            await self.bus.publish("agent.error", {
                "source": source,
                "user_id": user_id,
                "error": str(e),
            })
            return "Sorry, I encountered an error processing your message."
    
    def reset_session(self, session_id: Optional[str] = None):
        """
        Reset a session, clearing all history.
        
        Args:
            session_id: Session to reset. If None, resets the default session.
        """
        target_session = session_id or self.session_id
        self.session_manager.reset_session(target_session)
    
    def list_sessions(self) -> List[str]:
        """List all available sessions."""
        return self.session_manager.list_sessions()
    
    def update_working_set(
        self,
        session_id: Optional[str] = None,
        task_info: Optional[Dict[str, Any]] = None,
        artifacts: Optional[Dict[str, Any]] = None,
        env_context: Optional[Dict[str, Any]] = None
    ):
        """
        Update the working set for a session.
        
        Args:
            session_id: Session to update. If None, uses default session.
            task_info: Task information (id, type, outcome)
            artifacts: Artifact updates (e.g., last_file, last_url)
            env_context: Environment context updates
        """
        target_session = session_id or self.session_id
        self.session_manager.update_working_set(
            session_id=target_session,
            task_info=task_info,
            artifacts=artifacts,
            env_context=env_context
        )
