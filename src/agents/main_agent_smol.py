"""
Main Agent using smolagents CodeAgent for orchestration.
This replaces the custom LLM-based orchestrator with smolagents' built-in CodeAgent.
"""
import asyncio
import json
import numpy as np
import os
import time
from typing import Any, Dict, List, Optional

from smolagents import ActionStep, CodeAgent, RunResult
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

from src.agents.state import SharedState
from src.agents.llm.litellm_model import OllamaLiteLLMModel
from src.agents.core.events import EventBus
from src.agents.core.registry import ToolRegistry
from src.agents.notify.notifier import Notifier
from src.agents.core.store import SQLiteStore

# Import smolagents-compatible tools
from src.agents.tools.webbrowser_smol import WebBrowserSmolTool
from src.agents.tools.desktop_smol import DesktopSmolTool
from src.agents.tools.vision_smol import VisionSmolTool
from src.agents.tools.memory_smol import MemorySmolTool
from src.agents.tools.speech_smol import SpeechSmolTool
from src.agents.tools.codeagent import CodeAgentTool
from src.agents.tools.app_launcher_smol import AppLauncherSmolTool
from src.agents.memory.session_manager import SessionManager


# System prompt for the main agent - CONDENSED
SYSTEM_PROMPT = """You are a helpful AI named Kanna. Chat naturally and use tools ONLY when needed.

CRITICAL RULES:
1. ALWAYS provide your final response with final_answer() - this is mandatory for every response
2. After ANY tool succeeds (especially discord), immediately call final_answer()
3. Process tool outputs - explain them in your own words, don't echo raw data

TOOLS:
- launch_app(app_name): Launch desktop apps
    - This tool automatically saves a screenshot after each use. You do not need to take another screenshot, just use your vision on the screenshot taken by this tool to verify the app launched.
- memory: remember/recall information
- webbrowser: search the web, fetch URLs
    - This is useful for making quick single query searches and receiving basic information from the web.
- desktop: control keyboard/mouse, take screenshots
  • Use 'press' for special keys (enter, tab), 'type' for text
  • Add delays: wait 0.8s after launcher, 0.3s after typing, 2s after app launch
- vision(path): analyze images from screenshots
- speech: text-to-speech and audio transcription
- discord: send Discord messages
  • CRITICAL: Call final_answer() immediately after discord confirms success
  
Make sure to include code with the correct pattern, for instance:
    Thoughts: Your thoughts
    <code>
    # Your python code here
    </code>
    Make sure to provide correct code blobs.

Be conversational and concise."""


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
    ):
        self.state = state
        self.bus = bus
        self.registry = registry
        self.notifier = notifier
        self.store = store
        self.session_id = session_id
        self.os_context = ""  # Will be populated when desktop tool is initialized
        self._latest_action_steps: List[Dict[str, Any]] = []
        
        # Initialize session manager
        self.session_manager = SessionManager(
            session_dir=".nayu_ai/sessions",
            max_messages=20,
            max_tokens=4096,
            summary_interval=5
        )
       
        # Initialize LiteLLM model for Ollama
        model_name = os.getenv("AGENT_MODEL", "qwen2.5:14b-instruct-q4_k_m")
        num_ctx = int(os.getenv("AGENT_NUM_CTX", "16000"))
        
        self.model = OllamaLiteLLMModel(
            model_id=model_name,
            num_ctx=num_ctx,
            temperature=0.8
        )
        
        # Initialize tools
        self.tools = []
        self._init_tools()

        # Initialize CodeAgent
        self.agent = CodeAgent(
            tools=self.tools,
            model=self.model,
            #planning_interval=5,
            max_steps=15,
            additional_authorized_imports=[
                "requests", "json", "re", "time", "datetime",
                "bs4", "duckduckgo_search", "readability", "html2text"
            ]
        )
        self._register_action_step_callback()

        # Lightweight embedding model for tool selection
        print("Loading tool embedder (this may take a moment on first run)...")
        self.tool_embedder = SentenceTransformer('all-MiniLM-L6-v2')

        # Pre-compute tool embeddings
        self.tool_embeddings = {}
        for tool in self.tools:
            embedding = self.tool_embedder.encode(
                f"{tool.name}: {tool.description}"
            )
            self.tool_embeddings[tool.name] = embedding
        print(f"Pre-computed embeddings for {len(self.tool_embeddings)} tools")

    def _is_simple_request(self, text: str) -> bool:
        """Fast heuristic to detect simple requests."""
        simple_patterns = [
            'hi', 'hello', 'thanks', 'thank you', 'ok', 'okay', 
            'yes', 'no', 'got it', 'understood'
        ]
        return (
            len(text.split()) < 10 and
            any(p in text.lower() for p in simple_patterns)
        )

    def _init_tools(self):
        """Initialize all smolagents-compatible tools."""
        desktop = None
        vision = None
        
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
            # App Launcher tool (composite tools using desktop)
            if desktop is not None and vision is not None:
                app_launcher = AppLauncherSmolTool(desktop, vision)
                self.tools.append(app_launcher)
                self.registry.register("launch_app", app_launcher, {
                    "name": app_launcher.name,
                    "description": app_launcher.description
                })
            else:
                print("Warning: Skipping app_launcher - desktop or vision not available")
        except Exception as e:
            print(f"Warning: Could not initialize app_launcher tool: {e}")
        
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
    
    def _register_action_step_callback(self):
        """Register a callback to capture smolagents ActionStep data."""
        try:
            if hasattr(self, "agent") and getattr(self.agent, "step_callbacks", None):
                self.agent.step_callbacks.register(ActionStep, self._capture_action_step)
        except Exception:
            pass

    def _capture_action_step(self, step: ActionStep, agent=None):
        """Store the latest ActionStep for multi-step visibility."""
        try:
            step_dict = step.dict()
        except Exception:
            step_dict = {"step_number": getattr(step, "step_number", None)}
        self._latest_action_steps.append(self._ensure_jsonable(step_dict))
        observation = self._extract_last_observation([step_dict])
        if observation:
            self.state.last_observation = observation

    def _sanitize_steps(self, steps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Ensure steps are JSON serializable for storage and events."""
        return [self._ensure_jsonable(step) for step in steps] if steps else []

    def _ensure_jsonable(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert non-serializable values to strings."""
        try:
            json.dumps(data)
            return data
        except TypeError:
            return json.loads(json.dumps(data, default=str))

    def _extract_last_observation(self, steps: List[Dict[str, Any]]) -> Optional[str]:
        """Extract the most recent observation or tool output from steps."""
        for step in reversed(steps or []):
            obs = step.get("observations") or step.get("action_output")
            if obs:
                return obs if isinstance(obs, str) else str(obs)
        return None
    
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
            
            # Add embedding for new tool
            embedding = self.tool_embedder.encode(
                f"{discord_tool.name}: {discord_tool.description}"
            )
            self.tool_embeddings[discord_tool.name] = embedding
            
            # Reinitialize the main CodeAgent with updated tools
            self.agent = CodeAgent(
                tools=self.tools,
                model=self.model,
                #planning_interval=5,
                max_steps=15,
                additional_authorized_imports=[
                    "requests", "json", "re", "time", "datetime",
                    "bs4", "duckduckgo_search", "readability", "html2text"
                ]
            )
            self._register_action_step_callback()
            
            # Also register in registry for tracking
            self.registry.register("discord", discord_tool, {
                "name": discord_tool.name,
                "description": discord_tool.description
            })
            
            print("Discord tool added successfully")
            return True
        except Exception as e:
            print(f"Warning: Could not add Discord tool: {e}")
            import traceback
            traceback.print_exc()
            return False

    def _select_relevant_tools(self, user_text: str, max_tools: int = 6) -> List[str]:
        """Select only relevant tools to reduce prompt size."""
        # Encode the user query
        query_embedding = self.tool_embedder.encode(user_text)
        
        # Reshape embeddings to 2D for sklearn
        query_embedding_2d = query_embedding.reshape(1, -1)
        
        # Calculate similarities
        similarities = {}
        for tool_name, tool_emb in self.tool_embeddings.items():
            tool_emb_2d = tool_emb.reshape(1, -1)
            similarity = cosine_similarity(query_embedding_2d, tool_emb_2d)[0][0]
            similarities[tool_name] = similarity
        
        # Sort by similarity and return top N tool names
        relevant_tools = sorted(
            similarities.items(), 
            key=lambda x: x[1], 
            reverse=True
        )[:max_tools]
        
        tool_names = [name for name, score in relevant_tools]
        print(f"Selected tools for query '{user_text[:50]}...': {tool_names}")
        return tool_names

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

        # Select subset of relevant tools (disabled for now - see note below)
        relevant_tool_names = self._select_relevant_tools(user_text, max_tools=6)
        relevant_tools = [t for t in self.tools if t.name in relevant_tool_names]

        try:
            t0 = time.time()
            self._latest_action_steps = []
            
            # Use standard agent for now (tool selection can be enabled later)
            run_output = await asyncio.to_thread(
                self.agent.run,
                full_prompt,
                return_full_result=True,
            )
            
            latency_ms = (time.time() - t0) * 1000
            print(f"Agent response time: {latency_ms:.0f}ms")
            result = run_output.output if isinstance(run_output, RunResult) else run_output
            
            if isinstance(run_output, RunResult):
                action_steps = self._sanitize_steps(run_output.steps or [])
                if self._latest_action_steps:
                    if action_steps:
                        self._latest_action_steps.extend(action_steps)
                else:
                    self._latest_action_steps = action_steps
            if self._latest_action_steps:
                last_obs = self._extract_last_observation(self._latest_action_steps)
                if last_obs:
                    self.state.last_observation = last_obs
                await self.bus.publish("agent.steps", {
                    "session_id": active_session_id,
                    "steps": self._latest_action_steps
                })
            
            # Clean up result if it's empty or contains code
            if result is None:
                result = ""
            if not isinstance(result, str):
                result = str(result)
            if not result.strip():
                result = "I processed your request."
            
            # Add assistant response to session
            self.session_manager.add_message(
                session_id=active_session_id,
                role="assistant",
                content=result,
                metadata={"latency_ms": latency_ms}
            )
            
            # Persist the interaction for fine-tuning
            await self._persist_example(user_text, result, mem_digest, source, user_id, channel_id)
            
            # Publish output event
            await self.bus.publish("agent.output", {
                "text": result,
                "latency_ms": latency_ms,
                "session_id": active_session_id
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
