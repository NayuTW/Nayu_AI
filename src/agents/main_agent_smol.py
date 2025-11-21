"""
Main Agent using smolagents CodeAgent for orchestration.
This replaces the custom LLM-based orchestrator with smolagents' built-in CodeAgent.
"""
import asyncio
import numpy as np
import os
import time
from typing import Any, Dict, List, Optional

from smolagents import CodeAgent
from fastembed import TextEmbedding
from sklearn.decomposition import PCA
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
from src.agents.tools.app_launcher_smol import AppLauncherSmolTool
from src.agents.memory.session_manager import SessionManager


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
        
        # Initialize session manager
        self.session_manager = SessionManager(
            session_dir=".nayu_ai/sessions",
            max_messages=20,
            max_tokens=4096,
            summary_interval=5
        )
       
        # Initialize LiteLLM model for Ollama
        model_name = os.getenv("AGENT_MODEL", "qwen3:8b-q6_K")
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

        # Lightweight embedding model for tool selection
        print("Loading tool embedder (this may take a moment on first run)...")
        self.tool_embedder = TextEmbedding('BAAI/bge-small-en-v1.5')

        # Pre-compute tool embeddings (stored as 2D numpy arrays of shape (1, d))
        self.tool_embeddings = {}
        for tool in self.tools:
            embedding = self.tool_embedder.embed(
                f"{tool.name}: {tool.description}"
            )
            try:
                emb_arr = np.array(embedding, dtype=float).reshape(1, -1)
            except Exception:
                # Fallback: attempt to coerce to list then array
                emb_arr = np.array(list(embedding), dtype=float).reshape(1, -1)
            self.tool_embeddings[tool.name] = emb_arr
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
            embedding = self.tool_embedder.embed(
                f"{discord_tool.name}: {discord_tool.description}"
            )
            try:
                emb_arr = np.array(embedding, dtype=float).reshape(1, -1)
            except Exception:
                emb_arr = np.array(list(embedding), dtype=float).reshape(1, -1)
            self.tool_embeddings[discord_tool.name] = emb_arr
            
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
        """Select only relevant tools to reduce prompt size.

        Uses cosine similarity in the original embedding space rather than PCA.
        This avoids PCA errors when dealing with single-sample embeddings.
        """
        # Encode the user query
        try:
            query_embedding = np.array(self.tool_embedder.embed(user_text), dtype=float).reshape(1, -1)
        except Exception:
            query_embedding = np.array(list(self.tool_embedder.embed(user_text)), dtype=float).reshape(1, -1)
        
        tool_names = list(self.tool_embeddings.keys())
        if not tool_names:
            return []
        
        # Stack tool embeddings into matrix (n_tools, d)
        try:
            tool_emb_matrix = np.vstack([self.tool_embeddings[name] for name in tool_names])
        except Exception as e:
            # If embeddings shapes mismatch for any reason, fall back to returning a capped list
            print(f"Warning: Could not stack tool embeddings for similarity check: {e}")
            return tool_names[:max_tools]

        # Ensure dimensionality matches
        if query_embedding.shape[1] != tool_emb_matrix.shape[1]:
            print(
                f"Warning: Embedding dimension mismatch (query: {query_embedding.shape[1]}, "
                f"tools: {tool_emb_matrix.shape[1]}). Skipping similarity-based selection."
            )
            return tool_names[:max_tools]

        # Compute cosine similarities: result shape (1, n_tools)
        similarities = cosine_similarity(query_embedding, tool_emb_matrix)[0]

        # Pair names and scores and sort
        name_score_pairs = list(zip(tool_names, similarities))
        name_score_pairs.sort(key=lambda x: x[1], reverse=True)

        relevant = [name for name, score in name_score_pairs[:max_tools]]
        print(f"Selected tools for query '{user_text[:50]}...': {relevant}")
        return relevant

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
            
            # Use standard agent for now (tool selection can be enabled later)
            result = await asyncio.to_thread(self.agent.run, full_prompt)
            
            latency_ms = (time.time() - t0) * 1000
            print(f"Agent response time: {latency_ms:.0f}ms")
            
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
