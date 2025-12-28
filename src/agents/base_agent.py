"""
Base Agent class using smolagents CodeAgent for orchestration.
This module provides the abstract BaseAgent with managed properties and getters/setters.
Child classes (MainAgent, VisionAgent, etc.) inherit core infrastructure.
"""
import os
from abc import ABC, abstractmethod
from threading import RLock
from typing import Any, Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from smolagents import CodeAgent, ToolCallingAgent
from sklearn.metrics.pairwise import cosine_similarity

from src.agents.core.events import EventBus
from src.agents.core.registry import ToolRegistry
from src.agents.core.store import SQLiteStore
from src.agents.llm.litellm_model import OllamaLiteLLMModel
from src.agents.memory.session_manager import SessionManager
from src.agents.notify.notifier import Notifier
from src.agents.state import SharedState

# ============ Module Constants ============
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_MAX_STEPS = 15
DEFAULT_AUTHORIZED_IMPORTS = [
    "requests", "json", "re", "time", "datetime",
    "bs4", "duckduckgo_search", "readability", "html2text"
]

SYSTEM_PROMPT = """You are a helpful AI named Kanna. Chat naturally and use tools when needed.

CRITICAL RULES:
1. Follow a ReAct loop: think → act (tool) → observe → repeat until done.
2. Use multiple steps when a tool is required (e.g., call vision to read a screenshot, then act on that info in the next step).
3. Do NOT jump to a final answer before you have the necessary observations.
4. Summarize tool outputs in your own words; don't echo raw data.

TOOLS:
- launch_app(app_name): Launch desktop apps
    - This tool automatically saves a screenshot after each use. Use the vision tool on that screenshot to verify the app launch.
- memory: remember/recall information
- webbrowser: search the web, fetch URLs
    - Useful for quick searches and retrieving basic information from the web.
- desktop: control keyboard/mouse, take screenshots
  • Use 'press' for special keys (enter, tab), 'type' for text
  • Add delays: wait 0.8s after launcher, 0.3s after typing, 2s after app launch
- vision(path): analyze images from screenshots
- speech: text-to-speech and audio transcription
- write_file: create/write files in .workspace directory
  • Supports common formats: .py, .txt, .md, .csv, .json, .yaml, .html, .js, etc.
  • Has safety guardrails to prevent harmful code
  • Use write_file(filename='myfile.txt', content='...', mode='write')
- discord: send Discord messages
  • If you send a Discord message, provide the final response only after confirming success.

Make sure to include code with the correct pattern, for instance:
    Thoughts: Your thoughts
    <code>
    # Your python code here
    </code>
    Make sure to provide correct code blobs.

Be conversational and concise. Only give the final answer when you are confident the task is complete."""


class ToolEmbedder:
    """Helper class for managing tool embeddings and similarity-based selection."""
    
    def __init__(self, model_name: str = DEFAULT_EMBEDDING_MODEL):
        """Initialize embedder model."""
        self.model = SentenceTransformer(model_name)
        self.embeddings: Dict[str, np.ndarray] = {}
    
    def embed_tool(self, tool_name: str, tool_desc: str) -> np.ndarray:
        """Embed a single tool description and cache."""
        text = f"{tool_name}: {tool_desc}"
        embedding = self.model.encode(text, convert_to_numpy=True)
        emb_arr = np.array(embedding, dtype=float).reshape(1, -1)
        self.embeddings[tool_name] = emb_arr
        return emb_arr
    
    def embed_query(self, query: str) -> np.ndarray:
        """Embed a query string."""
        embedding = self.model.encode(query, convert_to_numpy=True)
        return np.array(embedding, dtype=float).reshape(1, -1)
    
    def select_relevant_tools(
        self,
        query: str,
        tool_names: List[str],
        max_tools: int = 6
    ) -> List[str]:
        """Select top-K tools by cosine similarity to query."""
        if not tool_names or not self.embeddings:
            return tool_names[:max_tools]
        
        query_emb = self.embed_query(query)
        
        # Stack tool embeddings
        try:
            tool_emb_matrix = np.vstack([
                self.embeddings[name] for name in tool_names
                if name in self.embeddings
            ])
        except Exception as e:
            print(f"Warning: Could not stack embeddings: {e}")
            return tool_names[:max_tools]
        
        # Check dimensionality match
        if query_emb.shape[1] != tool_emb_matrix.shape[1]:
            print(f"Warning: Embedding dimension mismatch. Returning top {max_tools} tools.")
            return tool_names[:max_tools]
        
        # Compute similarities
        similarities = cosine_similarity(query_emb, tool_emb_matrix)[0]
        pairs = list(zip(tool_names, similarities))
        pairs.sort(key=lambda x: x[1], reverse=True)
        
        selected = [name for name, _ in pairs[:max_tools]]
        print(f"Selected tools: {selected}")
        return selected
    
    def clear(self):
        """Clear cached embeddings."""
        self.embeddings.clear()


class BaseAgent(ABC):
    """
    Abstract base class for all agent types (Main, Vision, etc.).
    Provides shared infrastructure with managed getters/setters and thread-safety.
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
        # Core infrastructure (read-only)
        self._state = state
        self._bus = bus
        self._registry = registry
        self._notifier = notifier
        self._store = store
        self._session_id = session_id
        self._lock = RLock()
        
        # Agent-specific mutable state
        self._model: Optional[OllamaLiteLLMModel] = None
        self._tools: List[Any] = []
        self._managed_agents: List[Any] = []
        self._agent: Optional[CodeAgent] = None
        self._session_manager: Optional[SessionManager] = None
        self._tool_embedder: Optional[ToolEmbedder] = None
        self._os_context: str = ""
        self._latest_action_steps: List[Dict[str, Any]] = []
    
    # ============ Read-Only Infrastructure Properties ============
    @property
    def state(self) -> SharedState:
        """Get shared state (read-only)."""
        return self._state
    
    @property
    def bus(self) -> EventBus:
        """Get event bus (read-only)."""
        return self._bus
    
    @property
    def registry(self) -> ToolRegistry:
        """Get tool registry (read-only)."""
        return self._registry
    
    @property
    def notifier(self) -> Notifier:
        """Get notifier (read-only)."""
        return self._notifier
    
    @property
    def store(self) -> SQLiteStore:
        """Get storage (read-only)."""
        return self._store
    
    @property
    def session_id(self) -> str:
        """Get session ID (read-only)."""
        return self._session_id
    
    # ============ Model Property ============
    @property
    def model(self) -> Optional[OllamaLiteLLMModel]:
        """Get the current LLM model."""
        with self._lock:
            return self._model
    
    @model.setter
    def model(self, value: OllamaLiteLLMModel) -> None:
        """
        Set the LLM model and rebuild CodeAgent if already initialized.
        
        Args:
            value: OllamaLiteLLMModel instance (cannot be None)
        
        Raises:
            ValueError: If value is None
        """
        if value is None:
            raise ValueError("Model cannot be None")
        
        with self._lock:
            old_model = self._model
            self._model = value
            
            # Rebuild agent if already initialized
            if self._agent is not None:
                self._rebuild_code_agent()
            
            # Emit event
            self.bus.emit("agent.model_changed", {
                "agent_type": self.__class__.__name__,
                "old_model": str(old_model),
                "new_model": str(value),
            })
    
    # ============ Tools Property ============
    @property
    def tools(self) -> List[Any]:
        """Get defensive copy of tools list."""
        with self._lock:
            return list(self._tools)
    
    @tools.setter
    def tools(self, value: List[Any]) -> None:
        """
        Replace tools list, rebuild CodeAgent and embeddings.
        
        Args:
            value: Non-empty list of tool instances
        
        Raises:
            ValueError: If value is not a non-empty list
        """
        if not isinstance(value, list) or len(value) == 0:
            raise ValueError("Tools must be a non-empty list")
        
        with self._lock:
            self._tools = list(value)
            self._recompute_tool_embeddings()
            
            if self._agent is not None:
                self._rebuild_code_agent()
            
            self.bus.emit("agent.tools_changed", {
                "agent_type": self.__class__.__name__,
                "tool_count": len(self._tools),
                "tool_names": [getattr(t, "name", str(t)) for t in self._tools],
            })
    
    def add_tool(self, tool: Any) -> None:
        """
        Add a single tool, rebuild embeddings and CodeAgent.
        
        Args:
            tool: Tool instance to add
        
        Raises:
            ValueError: If tool is None
        """
        if tool is None:
            raise ValueError("Tool cannot be None")
        
        with self._lock:
            self._tools.append(tool)
            self._recompute_tool_embeddings()
            
            if self._agent is not None:
                self._rebuild_code_agent()
            
            self.bus.emit("agent.tool_added", {
                "agent_type": self.__class__.__name__,
                "tool_name": getattr(tool, "name", str(tool)),
                "tool_count": len(self._tools),
            })
    
    def remove_tool(self, tool_name: str) -> None:
        """
        Remove a tool by name, rebuild embeddings and CodeAgent.
        
        Args:
            tool_name: Name of tool to remove
        
        Raises:
            ValueError: If tool not found
        """
        with self._lock:
            original_count = len(self._tools)
            self._tools = [
                t for t in self._tools
                if getattr(t, "name", str(t)) != tool_name
            ]
            
            if len(self._tools) == original_count:
                raise ValueError(f"Tool '{tool_name}' not found")
            
            self._recompute_tool_embeddings()
            
            if self._agent is not None:
                self._rebuild_code_agent()
            
            self.bus.emit("agent.tool_removed", {
                "agent_type": self.__class__.__name__,
                "tool_name": tool_name,
                "tool_count": len(self._tools),
            })
    
    # ============ Managed Agents Property ============
    @property
    def managed_agents(self) -> List[Any]:
        """Get defensive copy of managed agents."""
        with self._lock:
            return list(self._managed_agents)
    
    @managed_agents.setter
    def managed_agents(self, value: List[Any]) -> None:
        """
        Set managed agents and rebuild CodeAgent.
        
        Args:
            value: List of managed agent instances
        """
        if not isinstance(value, list):
            raise ValueError("Managed agents must be a list")
        
        with self._lock:
            self._managed_agents = list(value)
            
            if self._agent is not None:
                self._rebuild_code_agent()
            
            self.bus.emit("agent.managed_agents_changed", {
                "agent_type": self.__class__.__name__,
                "count": len(self._managed_agents),
            })
    
    # ============ CodeAgent Property ============
    @property
    def agent(self) -> Optional[CodeAgent]:
        """Get the CodeAgent instance."""
        with self._lock:
            return self._agent
    
    @agent.setter
    def agent(self, value: CodeAgent) -> None:
        """Set CodeAgent (internal use; prefer _rebuild_code_agent)."""
        with self._lock:
            self._agent = value
    
    # ============ Session Manager Property ============
    @property
    def session_manager(self) -> Optional[SessionManager]:
        """Get the session manager."""
        with self._lock:
            return self._session_manager
    
    @session_manager.setter
    def session_manager(self, value: SessionManager) -> None:
        """
        Set session manager.
        
        Args:
            value: SessionManager instance
        
        Raises:
            ValueError: If value is None
        """
        if value is None:
            raise ValueError("Session manager cannot be None")
        
        with self._lock:
            self._session_manager = value
    
    # ============ Tool Embedder Property ============
    @property
    def tool_embedder(self) -> Optional[ToolEmbedder]:
        """Get the tool embedder."""
        with self._lock:
            return self._tool_embedder
    
    @tool_embedder.setter
    def tool_embedder(self, value: ToolEmbedder) -> None:
        """
        Set tool embedder and recompute embeddings.
        
        Args:
            value: ToolEmbedder instance
        
        Raises:
            ValueError: If value is None
        """
        if value is None:
            raise ValueError("Tool embedder cannot be None")
        
        with self._lock:
            self._tool_embedder = value
            self._recompute_tool_embeddings()
    
    # ============ OS Context Property ============
    @property
    def os_context(self) -> str:
        """Get OS context string."""
        with self._lock:
            return self._os_context
    
    @os_context.setter
    def os_context(self, value: str) -> None:
        """Set OS context."""
        if not isinstance(value, str):
            raise ValueError("OS context must be a string")
        
        with self._lock:
            self._os_context = value
    
    # ============ Action Steps Property ============
    @property
    def latest_action_steps(self) -> List[Dict[str, Any]]:
        """Get defensive copy of latest action steps."""
        with self._lock:
            return [dict(step) for step in self._latest_action_steps]
    
    def add_action_step(self, step: Dict[str, Any]) -> None:
        """Add an action step."""
        with self._lock:
            self._latest_action_steps.append(dict(step))
    
    def clear_action_steps(self) -> None:
        """Clear all action steps."""
        with self._lock:
            self._latest_action_steps.clear()
    
    # ============ Protected Helper Methods ============
    def _recompute_tool_embeddings(self) -> None:
        """Recompute embeddings for all tools using ToolEmbedder."""
        if self._tool_embedder is None or not self._tools:
            return
        
        with self._lock:
            self._tool_embedder.clear()
            for tool in self._tools:
                tool_desc = getattr(tool, "description", "") or str(tool)
                self._tool_embedder.embed_tool(
                    getattr(tool, "name", str(tool)),
                    tool_desc
                )
    
    def _rebuild_code_agent(self) -> None:
        """Rebuild agent with current model, tools, and managed_agents."""
        if self._model is None:
            raise RuntimeError("Cannot rebuild agent: model not set")
        
        with self._lock:
            agent_class = self._get_agent_class()
            self._agent = agent_class(
                tools=list(self._tools),
                managed_agents=list(self._managed_agents),
                model=self._model,
                max_steps=self._get_max_steps(),
                additional_authorized_imports=self._get_authorized_imports(),
            )
            
            self.bus.emit("agent.rebuilt", {
                "agent_type": self.__class__.__name__,
                "agent_class": agent_class.__name__,
                "tool_count": len(self._tools),
            })
    
    # ============ Abstract & Override Methods ============
    def _get_agent_class(self) -> type:
        """
        Get the agent class to instantiate (CodeAgent, ToolCallingAgent, etc.).
        Override in subclasses to change agent type.
        
        Returns:
            Agent class to use for orchestration
        """
        return CodeAgent
    
    def _get_max_steps(self) -> int:
        """Override in subclasses to customize max steps."""
        return DEFAULT_MAX_STEPS
    
    def _get_authorized_imports(self) -> List[str]:
        """Override in subclasses to customize authorized imports."""
        return DEFAULT_AUTHORIZED_IMPORTS
    
    @abstractmethod
    def _init_tools(self) -> None:
        """Initialize tools. Must be implemented by subclasses."""
        raise NotImplementedError
    
    def _register_action_step_callback(self) -> None:
        """Register action step callback. May be overridden by subclasses."""
        pass


