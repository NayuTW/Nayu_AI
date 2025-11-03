"""
Main Agent using smolagents CodeAgent for orchestration.
This replaces the custom LLM-based orchestrator with smolagents' built-in CodeAgent.
"""
import asyncio
import os
import time
from typing import Any, Dict, Optional

from smolagents import CodeAgent

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


# System prompt for the main agent
SYSTEM_PROMPT = """You are a helpful, friendly AI assistant. Your primary role is to chat naturally with users and help them with their requests.

CORE BEHAVIOR:
- Be conversational, warm, and personable
- Respond naturally to greetings, questions, and casual conversation
- Only use tools when the user's request specifically requires them
- Think: "Can I answer this directly, or do I need a tool?"
- You may receive messages from multiple channels (e.g., cli, discord)

TOOL USAGE:
- Use tools judiciously - not every request needs a tool
- memory tool: Use 'remember' to store information, 'recall' to retrieve it
- webbrowser tool: Search the web, fetch URLs, or research topics
- desktop tool: Control keyboard/mouse or take screenshots
- vision tool: Analyze images or screenshots
- speech tool: Transcribe audio or generate speech
- codeexec tool: Run Python code for complex tasks
- discord_agent: Send Discord messages to channels or DMs (when available)

RESPONSE STYLE:
- Be direct and conversational
- Don't mention internal details like tool execution unless relevant
- Provide helpful, actionable information
- Keep responses concise but complete
- Always provide your final response by calling the 'final_answer' function"""


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
        session_id: str
    ):
        self.state = state
        self.bus = bus
        self.registry = registry
        self.notifier = notifier
        self.store = store
        self.session_id = session_id
        self.os_context = ""  # Will be populated when desktop tool is initialized
        
        # Initialize LiteLLM model for Ollama
        model_name = os.getenv("AGENT_MODEL", "llama3.1:8b-instruct-q4_K_M")
        num_ctx = int(os.getenv("AGENT_NUM_CTX", "24576"))
        
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
        Add Discord agent as a tool that internally uses ToolCallingAgent.
        This creates a wrapper tool that delegates to a ToolCallingAgent for Discord operations.
        
        Args:
            discord_service: The Discord bot service instance
        
        Returns:
            bool: True if successfully added, False otherwise
        """
        try:
            from src.agents.tools.discord_agent_tool import DiscordAgentTool
            
            # Create Discord agent tool (wraps ToolCallingAgent)
            discord_agent_tool = DiscordAgentTool(discord_service, self.model)
            
            # Add to tools list
            self.tools.append(discord_agent_tool)
            
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
            self.registry.register("discord_agent", discord_agent_tool, {
                "name": discord_agent_tool.name,
                "description": discord_agent_tool.description
            })
            
            print("Discord agent tool added successfully")
            return True
        except Exception as e:
            print(f"Warning: Could not add Discord agent tool: {e}")
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
    ) -> str:
        """
        Handle a user message using the CodeAgent.
        """
        # Get memory context
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
        
        # Build prompt with context
        full_prompt = f"""{SYSTEM_PROMPT}
{self.os_context}

CONTEXT:
{context}

MESSAGE SOURCE: {source}
{f"USER_ID: {user_id}" if user_id else ""}
{f"CHANNEL_ID: {channel_id}" if channel_id else ""}

USER MESSAGE:
{user_text}

Respond naturally and use tools only if needed."""
        
        # Publish input event
        await self.bus.publish("agent.input", {
            "text": user_text,
            "source": source,
            "meta": external_metadata or {}
        })
        
        try:
            # Run the agent
            t0 = time.time()
            result = await asyncio.to_thread(self.agent.run, full_prompt)
            latency_ms = (time.time() - t0) * 1000
            
            # Clean up result if it's empty or contains code
            if not result or not result.strip():
                result = "I processed your request."
            
            # Persist the interaction
            await self._persist_example(user_text, result, mem_digest, source, user_id, channel_id)
            
            # Publish output event
            await self.bus.publish("agent.output", {"text": result, "latency_ms": latency_ms})
            
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
