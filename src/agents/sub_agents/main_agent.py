"""
Main Agent: orchestrator using smolagents CodeAgent.
Manages all tool integrations and coordinates multi-step workflows.
"""
import asyncio
import inspect
import os
import time
from typing import Any, Optional

from smolagents import CodeAgent, RunResult

from src.agents.base_agent import BaseAgent, SYSTEM_PROMPT, ToolEmbedder
from src.agents.factory import AgentFactory
from src.agents.sub_agents.vision_agent import VisionAgent
from src.agents.core.events import EventBus
from src.agents.core.registry import ToolRegistry
from src.agents.core.store import SQLiteStore
from src.agents.core.output_handler import AgentOutputHandler
from src.agents.llm.litellm_model import OllamaLiteLLMModel
from src.agents.memory.session_manager import SessionManager
from src.agents.notify.notifier import Notifier
from src.agents.state import SharedState
from src.agents.tools.app_launcher_smol import AppLauncherSmolTool
from src.agents.tools.desktop_current import DesktopCurrentCapture
from src.agents.tools.discord_tool_smol import DiscordSmolTool
from src.agents.tools.desktop_smol import DesktopSmolTool
from src.agents.tools.memory_smol import MemorySmolTool
from src.agents.tools.speech_smol import SpeechSmolTool
from src.agents.tools.webbrowser import WebBrowserSmolTool
from src.agents.tools.writefile_smol import WriteFileSmolTool


class MainAgent(BaseAgent):
    """
    Main orchestrator agent using smolagents CodeAgent.
    Manages all tools and coordinates multi-step workflows.
    Functionally equivalent to the original SmolAgent.
    """
    
    def __init__(
        self,
        state: SharedState,
        bus: EventBus,
        registry: ToolRegistry,
        notifier: Notifier,
        store: SQLiteStore,
        session_id: str,
    ):
        """
        Initialize MainAgent with all standard infrastructure.
        
        Args:
            state: Shared state blackboard
            bus: Event bus for system notifications
            registry: Tool registry for management
            notifier: Notification service
            store: SQLite persistence
            session_id: Default session identifier
        """
        # Initialize parent (BaseAgent)
        super().__init__(state, bus, registry, notifier, store, session_id)

        # Set agent description
        self._set_description()
        self.output_handler = AgentOutputHandler(bus)
        
        # Initialize session manager
        self.session_manager = SessionManager(
            session_dir=".nayu_ai/sessions",
            max_messages=20,
            max_tokens=4096,
            summary_interval=5
        )
        
        # Initialize LLM model for Ollama (guard against empty env values)
        model_name_env = os.getenv("AGENT_MODEL")
        model_name = (model_name_env.strip() if model_name_env and model_name_env.strip() else "qwen3:8b-q6_K")
        num_ctx = int(os.getenv("AGENT_NUM_CTX") or "4096")
        
        self.model = OllamaLiteLLMModel(
            model_id=model_name,
            num_ctx=num_ctx,
            temperature=0.8,
            use_chat_api=True,
        )
        
        # Initialize tools (calls parent's add_tool internally)
        self._init_tools()
        
        # Initialize managed agents
        self._init_managed_agents()

        # Initialize CodeAgent with current tools
        self._rebuild_code_agent()
        
        # Initialize desktop screenshot capture
        self.desktop_capture = DesktopCurrentCapture(
            interval=2.0,
            output_dir=".cache",
            error_callback=self._handle_capture_error
        )
        self.desktop_capture.start()
        print("Desktop screenshot capture started (2-second interval)")
        
        # Register callback for ActionStep tracking
        self._register_action_step_callback()
        
        # Load tool embedder
        print("Loading tool embedder (this may take a moment on first run)...")
        self.tool_embedder = ToolEmbedder()
        print(f"Tool embedder ready. Indexed {len(self.tools)} tools.")
        
        # Register available agent types for dynamic creation
        self._register_agent_types()
    
    def _init_tools(self) -> None:
        """Initialize all smolagents-compatible tools."""
        # Desktop tool (referenced by other tools)
        desktop = None
        
        try:
            webbrowser = WebBrowserSmolTool()
            self.add_tool(webbrowser)
            self.registry.register("webbrowser", webbrowser, {
                "name": webbrowser.name,
                "description": webbrowser.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize webbrowser tool: {e}")
        
        try:
            desktop = DesktopSmolTool()
            self.add_tool(desktop)
            self.registry.register("desktop", desktop, {
                "name": desktop.name,
                "description": desktop.description
            })
            # Capture OS context for system prompt
            self.os_context = (
                f"\nSYSTEM INFO: Running on {desktop.os_info.get('description', 'Unknown OS')}. "
                f"{desktop.os_info.get('shortcuts_guide', '')}"
            )
        except Exception as e:
            print(f"Warning: Could not initialize desktop tool: {e}")
        
        try:
            if desktop is not None:
                app_launcher = AppLauncherSmolTool(desktop)
                self.add_tool(app_launcher)
                self.registry.register("launch_app", app_launcher, {
                    "name": app_launcher.name,
                    "description": app_launcher.description
                })
        except Exception as e:
            print(f"Warning: Could not initialize app_launcher tool: {e}")
        
        try:
            memory = MemorySmolTool()
            self.add_tool(memory)
            self.registry.register("memory", memory, {
                "name": memory.name,
                "description": memory.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize memory tool: {e}")
        
        try:
            speech = SpeechSmolTool()
            self.add_tool(speech)
            self.registry.register("speech", speech, {
                "name": speech.name,
                "description": speech.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize speech tool: {e}")
        
        try:
            write_file = WriteFileSmolTool(workspace_dir=".workspace")
            self.add_tool(write_file)
            self.registry.register("write_file", write_file, {
                "name": write_file.name,
                "description": write_file.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize write_file tool: {e}")
    
        try:
            discord_tool = DiscordSmolTool()
            self.add_tool(discord_tool)
            self.registry.register("discord", discord_tool, {
                "name": discord_tool.name,
                "description": discord_tool.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize discord tool: {e}")
    
    def _init_managed_agents(self) -> None:
        """Initialize all managed agents."""
        try:
            vision = VisionAgent(
                state=self.state,
                bus=self.bus,
                registry=self.registry,
                notifier=self.notifier,
                store=self.store,
                session_id=self.session_id
            )
            self._register_managed_agent(vision)  # One-liner with full setup
        except Exception as e:
            print(f"Warning: Could not initialize managed agents: {e}")
    
    def _handle_capture_error(self, error_message: str) -> None:
        """Handle desktop capture errors."""
        print(f"Desktop capture error: {error_message}")
        self.bus.emit("desktop_capture.error", {"error": error_message})
    
    def _set_description(self) -> None:
        """Set description of this agent."""
        self.agent_description = """MainAgent is the primary orchestrator for general tasks. It coordinates specialized agents and tools to fulfill user requests.

## When to Use VisionAgent

Delegate to VisionAgent when you need:
- Visual/image analysis: "What's on the screen right now?"
- Interactive web browsing: "Find information on a website"
- Screenshots and OCR: "Read text from a screenshot"
- Specific browser interactions: "Click this button and report the result"

## How to Delegate to VisionAgent

ALWAYS provide a CLEAR, SPECIFIC task description:

GOOD EXAMPLES:
✓ vision_agent(task="Navigate to GitHub, find trending Python repositories, and list the top 5")
✓ vision_agent(task="Take a screenshot, identify any error dialogs, and describe them")
✓ vision_agent(task="Go to example.com and fill out the contact form with: name='John', email='john@example.com'")
✓ vision_agent(task="Search for 'artificial intelligence' on Wikipedia and summarize the key concepts")

POOR EXAMPLES (avoid these):
✗ vision_agent(task="browse the web")
✗ vision_agent(task="take a screenshot")
✗ vision_agent(task="use the browser")

## General Capabilities

MainAgent has access to standard tools for tasks that don't require vision or browser interaction:
- launch_app(app_name): Launch desktop applications
- memory: Store and retrieve information
- webbrowser: Search the web (not interactive browsing)
- desktop: Control mouse/keyboard
- speech: Text-to-speech and transcription
- write_file: Create and edit files
- discord: Discord integration

For interactive browsing or visual tasks, always delegate to VisionAgent with a specific task description."""
    
    def _register_agent_types(self) -> None:
        """Register available agent types for dynamic creation."""
        try:
            AgentFactory.register("vision", VisionAgent)
            self.bus.emit("agent_factory.registered", {
                "agent_type": "vision",
                "description": "Vision analysis agent"
            })
        except Exception as e:
            self.bus.emit("agent_factory.error", {
                "agent_type": "vision",
                "error": str(e)
            })

    def get_managed_agents_summary(self) -> list[dict[str, Any]]:
        """Get summary of managed agents for dashboard/logging."""
        return self.get_managed_agents_info()

    def set_discord_service(self, service: Any) -> None:
        """
        Set the Discord service for the Discord tool.
        This allows late-binding of the service after agent initialization.
        """
        for tool in self.tools:
            if isinstance(tool, DiscordSmolTool):
                tool.discord = service
                print("Discord service linked to DiscordSmolTool")
                break

    def _register_action_step_callback(self) -> None:
        """Register callback to capture smolagents ActionStep data."""
        try:
            callbacks = getattr(self.agent, "step_callbacks", None)
            if callbacks:
                # CallbackRegistry in smolagents uses register() method
                if hasattr(callbacks, "register"):
                    callbacks.register(self._capture_action_step)
                elif hasattr(callbacks, "append"):
                    callbacks.append(self._capture_action_step)
        except Exception as e:
            print(f"Warning: Could not register ActionStep callback: {e}")
    
    def _capture_action_step(self, step: Any, agent: Optional[Any] = None) -> None:
        """Store the latest ActionStep and capture desktop screenshot."""
        step_dict: dict[str, Any] = {}
        try:
            if hasattr(step, "dict"):
                step_dict = step.dict()
            elif hasattr(step, "model_dump"):
                step_dict = step.model_dump()
            else:
                step_dict = vars(step) if hasattr(step, "__dict__") else {}
        except (AttributeError, TypeError, ValueError) as e:
            print(f"Warning: Failed to serialize ActionStep: {e}")
        
        if not step_dict:
            fields = ("step_number", "timing", "observations", "action_output")
            step_dict = {field: getattr(step, field, None) for field in fields}
        
        sanitized = self._ensure_jsonable(step_dict)
        self.add_action_step(sanitized)
        
        # Capture desktop screenshot instantly when a tool is used
        try:
            self.desktop_capture.capture_now()
        except Exception as e:
            self._handle_capture_error(str(e))
        
        observation = self._extract_last_observation([sanitized])
        if observation:
            self.state.last_observation = observation
    

    async def handle_user_message(
        self,
        user_text: str,
        source: str = "cli",
        external_metadata: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """
        Handle a user message using the CodeAgent with session context.
        """
        # Use provided session_id or fall back to default
        active_session_id = session_id or self.session_id
        
        # Get session context (summary, working set, recent messages)
        summary, working_set_context, recent_messages = self.session_manager.get_context(active_session_id)
        
        # Get memory context from memory tool
        try:
            mem_tool = next((t for t in self.tools if t.name == "memory"), None)
            if mem_tool:
                mem_digest = mem_tool.digest_for_context(user_text)
            else:
                mem_digest = ""
        except Exception:
            mem_digest = ""
        
        # Build context
        context = self.state.build_context(mem_digest)
        
        # Build conversation history for context
        conversation_history = ""
        if recent_messages:
            history_lines = []
            for msg in recent_messages[-10:]:  # Last 10 messages for context
                role_label = "User" if msg.role == "user" else "Assistant"
                history_lines.append(f"{role_label}: {msg.content}")
            conversation_history = "\n".join(history_lines)
        
        # Build prompt with full context including session memory
        static_prefix = f"""{SYSTEM_PROMPT}
{self.os_context}

CONTEXT:
{context}

SESSION SUMMARY:
{summary if summary else "No previous conversation summary."}

WORKING SET:
{working_set_context if working_set_context else "No active artifacts or tasks."}"""

        dynamic_suffix = f"""
RECENT CONVERSATION:
{conversation_history if conversation_history else "This is the start of the conversation."}

MESSAGE SOURCE: {source}
{f"USER_ID: {user_id}" if user_id else ""}
{f"CHANNEL_ID: {channel_id}" if channel_id else ""}

USER MESSAGE:
{user_text}

Respond naturally and use tools only if needed. You can reference previous messages and artifacts from the conversation."""
        
        full_prompt = static_prefix + dynamic_suffix

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
            "session_id": active_session_id
        })

        try:
            t0 = time.time()
            self.clear_action_steps()
            
            # Use standard agent for now (tool selection can be enabled later)
            run_kwargs = {}
            if "return_full_result" in inspect.signature(self.agent.run).parameters:
                run_kwargs["return_full_result"] = True
            run_output = await asyncio.to_thread(self.agent.run, full_prompt, **run_kwargs)
            final_answers = None
            
            latency_ms = (time.time() - t0) * 1000
            print(f"Agent response time: {latency_ms:.0f}ms")
            result = run_output.output if isinstance(run_output, RunResult) else run_output
            
            if isinstance(run_output, RunResult):
                final_answers = getattr(run_output, "final_answers", None)
                action_steps = self._sanitize_steps(run_output.steps or [])
                if action_steps:
                    self._latest_action_steps.extend(action_steps)
            if self._latest_action_steps:
                await self.bus.publish("agent.steps", {
                    "session_id": active_session_id,
                    "steps": self._latest_action_steps
                })
                last_obs = self._extract_last_observation(self._latest_action_steps)
                if last_obs:
                    self.state.last_observation = last_obs
            
            # Clean up result if it's empty or contains code
            if result is None:
                result = ""
            if not isinstance(result, str):
                result = str(result)
            if not result.strip():
                result = "I processed your request."
            extracted_final = self.output_handler.extract_final_answer_text(final_answers) if final_answers else None
            final_text = extracted_final or result
            
            # Add assistant response to session
            self.session_manager.add_message(
                session_id=active_session_id,
                role="assistant",
                content=final_text,
                metadata={"latency_ms": latency_ms}
            )
            
            # Persist the interaction for fine-tuning
            await self._persist_example(user_text, final_text, mem_digest, source, user_id, channel_id)
            
            # Publish output event
            await self.output_handler.publish_output(
                text=final_text,
                latency_ms=latency_ms,
                session_id=active_session_id,
                final_answers=final_answers,
                ensure_jsonable=self._ensure_jsonable,
            )
            
            return final_text
            
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
        channel_id: Optional[str]
    ):
        """Persist interaction for fine-tuning dataset."""
        meta = {
            "memory_digest": memory_digest,
            "tools_enabled": [name for name, rt in self.registry._tools.items() if rt.stats.enabled],
            "source": source,
            "user_id": user_id,
            "channel_id": channel_id,
        }
        ex_id = self.store.append_example(
            session_id=self.session_id,
            user_text=user_text,
            assistant_text=assistant_text or "",
            meta=meta,
        )
        await self.bus.publish("dataset.example", {"id": ex_id, "label": "unlabeled"})
        return ex_id
    
    async def handle_external_message(
        self,
        text: str,
        user_id: str,
        channel_id: str,
        source: str,
        metadata: dict[str, Any],
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
    
    def list_sessions(self) -> list[str]:
        """List all available sessions."""
        return self.session_manager.list_sessions()
    
    def update_working_set(
        self,
        session_id: Optional[str] = None,
        task_info: Optional[dict[str, Any]] = None,
        artifacts: Optional[dict[str, Any]] = None,
        env_context: Optional[dict[str, Any]] = None
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
    
    def _select_relevant_tools(self, user_text: str, max_tools: int = 6) -> list[str]:
        """
        Select relevant tools based on query similarity.
        Falls back to all tools if embedder not ready.
        
        Args:
            user_text: User query
            max_tools: Maximum tools to select
        
        Returns:
            List of relevant tool names
        """
        if self.tool_embedder is None or not self.tools:
            return [t.name for t in self.tools]
        
        try:
            tool_names = [t.name for t in self.tools]
            relevant = self.tool_embedder.select_relevant_tools(
                user_text,
                tool_names,
                max_tools=max_tools
            )
            return relevant
        except Exception as e:
            print(f"Warning: Tool selection failed, using all tools: {e}")
            return [t.name for t in self.tools]
    
    def _sanitize_steps(self, steps: list[Any]) -> list[dict[str, Any]]:
        """
        Convert ActionStep objects to JSON-serializable dicts.
        
        Args:
            steps: List of ActionStep objects from CodeAgent
        
        Returns:
            List of sanitized step dicts
        """
        sanitized = []
        for step in steps:
            step_dict: dict[str, Any] = {}
            try:
                if hasattr(step, "model_dump"):
                    step_dict = step.model_dump()
                elif hasattr(step, "dict"):
                    step_dict = step.dict()
                else:
                    step_dict = vars(step) if hasattr(step, "__dict__") else {}
            except (AttributeError, TypeError, ValueError) as e:
                print(f"Warning: Failed to serialize ActionStep: {e}")
                continue
            
            # Ensure all values are JSON-serializable
            sanitized_dict = self._ensure_jsonable(step_dict)
            sanitized.append(sanitized_dict)
        
        return sanitized
    
    def _ensure_jsonable(self, obj: Any) -> Any:
        """
        Recursively convert an object to JSON-serializable format.
        
        Args:
            obj: Object to convert
        
        Returns:
            JSON-serializable version of object
        """
        if obj is None or isinstance(obj, (str, int, float, bool)):
            return obj
        
        if isinstance(obj, dict):
            return {
                str(k): self._ensure_jsonable(v)
                for k, v in obj.items()
            }
        
        if isinstance(obj, (list, tuple)):
            return [self._ensure_jsonable(item) for item in obj]
        
        # For objects, try model_dump first, then dict, then str
        try:
            if hasattr(obj, "model_dump"):
                return self._ensure_jsonable(obj.model_dump())
            elif hasattr(obj, "dict"):
                return self._ensure_jsonable(obj.dict())
            elif hasattr(obj, "__dict__"):
                return self._ensure_jsonable(vars(obj))
            else:
                return str(obj)
        except Exception:
            return str(obj)
    
    def _extract_last_observation(self, steps: list[dict[str, Any]]) -> Optional[str]:
        """
        Extract the last observation from action steps.
        Useful for understanding what the agent last observed.
        
        Args:
            steps: List of action step dicts
        
        Returns:
            Last observation string or None
        """
        for step in reversed(steps):
            observations = step.get("observations")
            if observations:
                if isinstance(observations, list) and len(observations) > 0:
                    return str(observations[-1])
                elif isinstance(observations, str):
                    return observations
        
        return None
    
    def get_tool_status(self) -> dict[str, dict[str, Any]]:
        """
        Get status of all registered tools.
        
        Returns:
            Dict mapping tool names to status dicts with enabled/disabled state
        """
        status = {}
        for tool_name, tool_ref in self.registry._tools.items():
            try:
                status[tool_name] = {
                    "enabled": tool_ref.stats.enabled,
                    "failure_count": tool_ref.stats.failure_count,
                    "success_count": tool_ref.stats.success_count,
                    "circuit_breaker_open": tool_ref.stats.circuit_breaker_open,
                }
            except Exception as e:
                print(f"Warning: Could not get status for {tool_name}: {e}")
                status[tool_name] = {"error": str(e)}
        
        return status
    
    def enable_tool(self, tool_name: str) -> bool:
        """
        Enable a tool via the registry.
        
        Args:
            tool_name: Name of tool to enable
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.registry.enable(tool_name)
            self.bus.emit("tool.enabled", {"tool_name": tool_name})
            print(f"Tool '{tool_name}' enabled")
            return True
        except Exception as e:
            print(f"Error enabling tool '{tool_name}': {e}")
            return False
    
    def disable_tool(self, tool_name: str) -> bool:
        """
        Disable a tool via the registry.
        
        Args:
            tool_name: Name of tool to disable
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self.registry.disable(tool_name)
            self.bus.emit("tool.disabled", {"tool_name": tool_name})
            print(f"Tool '{tool_name}' disabled")
            return True
        except Exception as e:
            print(f"Error disabling tool '{tool_name}': {e}")
            return False
    
    def reset_tool_circuit_breaker(self, tool_name: str) -> bool:
        """
        Reset circuit breaker for a tool.
        
        Args:
            tool_name: Name of tool to reset
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            tool_ref = self.registry._tools.get(tool_name)
            if tool_ref:
                tool_ref.stats.reset_circuit_breaker()
                self.bus.emit("tool.circuit_breaker_reset", {"tool_name": tool_name})
                print(f"Circuit breaker reset for '{tool_name}'")
                return True
            else:
                print(f"Tool '{tool_name}' not found")
                return False
        except Exception as e:
            print(f"Error resetting circuit breaker for '{tool_name}': {e}")
            return False
    
    def get_session_context(self, session_id: Optional[str] = None) -> dict[str, Any]:
        """
        Get full context for a session (summary, working set, recent messages).
        
        Args:
            session_id: Session ID. If None, uses default.
        
        Returns:
            Dict with summary, working_set, and recent_messages
        """
        target_session = session_id or self.session_id
        summary, working_set_context, recent_messages = self.session_manager.get_context(target_session)
        
        return {
            "session_id": target_session,
            "summary": summary,
            "working_set_context": working_set_context,
            "recent_messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp.isoformat() if hasattr(msg, "timestamp") else None
                }
                for msg in (recent_messages or [])
            ],
            "message_count": len(recent_messages) if recent_messages else 0
        }
    
    def get_memory_digest(self, query: str) -> str:
        """
        Get memory digest for a specific query.
        
        Args:
            query: Query string
        
        Returns:
            Memory digest string
        """
        try:
            mem_tool = next((t for t in self.tools if t.name == "memory"), None)
            if mem_tool:
                return mem_tool.digest_for_context(query)
            else:
                return ""
        except Exception as e:
            print(f"Warning: Could not get memory digest: {e}")
            return ""
    
    def add_memory(self, key: str, value: str, tags: Optional[list[str]] = None) -> Optional[str]:
        """
        Add a memory entry via the memory tool.
        
        Args:
            key: Memory key
            value: Memory value
            tags: Optional list of tags
        
        Returns:
            Memory ID if successful, None otherwise
        """
        try:
            mem_tool = next((t for t in self.tools if t.name == "memory"), None)
            if mem_tool:
                result = mem_tool.remember(key, value, tags or [])
                if isinstance(result, dict) and result.get("status") == "success":
                    mem_id = result.get("id")
                    self.bus.emit("memory.added", {
                        "id": mem_id,
                        "key": key,
                        "tags": tags or []
                    })
                    return mem_id
            else:
                print("Memory tool not available")
        except Exception as e:
            print(f"Error adding memory: {e}")
        
        return None
    
    def recall_memory(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        """
        Recall memories matching a query.
        
        Args:
            query: Query string
            limit: Maximum results
        
        Returns:
            List of memory entries
        """
        try:
            mem_tool = next((t for t in self.tools if t.name == "memory"), None)
            if mem_tool:
                result = mem_tool.recall(query, limit=limit)
                if isinstance(result, dict) and result.get("status") == "success":
                    return result.get("memories", [])
            else:
                print("Memory tool not available")
        except Exception as e:
            print(f"Error recalling memory: {e}")
        
        return []
    
    def clear_session_memory(self, session_id: Optional[str] = None):
        """
        Clear memory for a session.
        
        Args:
            session_id: Session ID. If None, uses default.
        """
        try:
            target_session = session_id or self.session_id
            mem_tool = next((t for t in self.tools if t.name == "memory"), None)
            if mem_tool:
                mem_tool.clear_session_memory(target_session)
                self.bus.emit("memory.cleared", {"session_id": target_session})
                print(f"Memory cleared for session {target_session}")
            else:
                print("Memory tool not available")
        except Exception as e:
            print(f"Error clearing memory: {e}")
    
    async def shutdown(self):
        """
        Gracefully shutdown the agent.
        Persist final state and close resources.
        """
        print("Shutting down MainAgent...")
        
        try:
            # Stop desktop screenshot capture
            if hasattr(self, 'desktop_capture'):
                self.desktop_capture.stop()
                print("Desktop screenshot capture stopped")
            
            # Persist final state
            self.session_manager.summarize_session(self.session_id)
            
            # Emit shutdown event
            await self.bus.publish("agent.shutdown", {
                "session_id": self.session_id
            })
            
            # Close tools that have cleanup
            for tool in self.tools:
                if hasattr(tool, "cleanup"):
                    try:
                        await tool.cleanup() if inspect.iscoroutinefunction(tool.cleanup) else tool.cleanup()
                    except Exception as e:
                        print(f"Warning: Error cleaning up {tool.name}: {e}")
            
            print("MainAgent shutdown complete")
        except Exception as e:
            print(f"Error during shutdown: {e}")
