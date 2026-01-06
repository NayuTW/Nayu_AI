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
from src.agents.factory import AgentFactory


# ============ Module Constants ============
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_MAX_STEPS = 15
DEFAULT_AUTHORIZED_IMPORTS = [
    "requests", "json", "re", "time", "datetime",
    "bs4", "duckduckgo_search", "readability", "html2text"
]

SYSTEM_PROMPT = """You are Nayu_AI, a helpful local AI assistant. You coordinate multiple tools and specialized agents to fulfill user requests.

CRITICAL RULES:
1. Follow a ReAct loop: Thoughts -> Code -> Observation -> Repeat.
2. Always wrap your python code in <code></code> blocks.
3. You MUST use the `final_answer(result)` function to provide your final response to the user. Do not just state the answer; call the function.
4. If a task requires vision analysis (describing images, screenshots, OCR), you MUST delegate it to the `vision_agent`.

TOOLS & AGENTS:
- vision_agent: Specialized in image analysis. Use when you need to "see" or "describe" something on the screen.
    - Example: `vision_agent(task="Describe what is currently displayed on the desktop screenshot")`
    - The agent will automatically use .cache/desktop.png which is kept up-to-date by the system.
- launch_app(app_name): Launch desktop apps.
- memory: Store and retrieve long-term information.
- webbrowser: Search and browse the web.
- desktop: Control mouse/keyboard (no screenshot action - use vision_agent instead).
- speech: Text-to-speech and transcription.
- write_file: Create and edit files.

DESKTOP SCREENSHOT WORKFLOW:
The desktop is continuously monitored and saved to .cache/desktop.png, which updates every 2 seconds automatically.
If the user asks about something on their screen:
1. Call `vision_agent(task="Describe the current desktop state")` 
2. The vision_agent will analyze .cache/desktop.png automatically.
3. Use the observation from vision_agent to formulate your next thought or final answer.

Make sure to include code with the correct pattern:
    Thoughts: Your reasoning
    <code>
    # Your python code here
    # Use final_answer("...") for the final response
    </code>

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
        self._agent_description: str = ""
        self._session_manager: Optional[SessionManager] = None
        self._tool_embedder: Optional[ToolEmbedder] = None
        self._os_context: str = ""
        self._latest_action_steps: List[Dict[str, Any]] = []
        
        # Register instance in factory
        AgentFactory.register_instance(self.__class__.__name__, self)
    
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
    
    def delegate_agent(self, agent_name: str) -> bool:
        """
        Add an existing agent instance to managed agents by name.
        
        Args:
            agent_name: Name of the agent instance to delegate to
            
        Returns:
            True if successful, False otherwise
        """
        with self._lock:
            target_agent = AgentFactory.get_instance(agent_name)
            if not target_agent:
                self.bus.emit("agent.error", {
                    "agent": self.__class__.__name__,
                    "error": f"Agent instance '{agent_name}' not found in registry"
                })
                return False
            
            if target_agent is self:
                self.bus.emit("agent.error", {
                    "agent": self.__class__.__name__,
                    "error": "Cannot delegate an agent to itself"
                })
                return False
            
            # Check if already managed
            if any(a.__class__.__name__ == agent_name for a in self._managed_agents):
                return True # Already delegated
            
            try:
                self.add_managed_agent(target_agent)
                return True
            except Exception as e:
                self.bus.emit("agent.error", {
                    "agent": self.__class__.__name__,
                    "error": f"Failed to delegate {agent_name}: {str(e)}"
                })
                return False

    def get_managed_agents_info(self) -> list[dict[str, Any]]:
        """
        Get detailed info for all managed agents including descriptions.
        
        Returns:
            List of dicts with agent name, type, and description
        """
        with self._lock:
            agents_info = []
            for agent in self._managed_agents:
                agent_info = {
                    "name": agent.__class__.__name__,
                    "type": type(agent).__name__,
                    "description": getattr(agent, "agent_description", ""),
                }
                agents_info.append(agent_info)
            return agents_info

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
    
    # ============ Agent Description Property ============
    @property
    def name(self) -> str:
        """Get the agent name (required by smolagents)."""
        import re
        name = self.__class__.__name__
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()

    @property
    def description(self) -> str:
        """Get the agent description (required by smolagents)."""
        return self.agent_description

    def forward(self, task: str, **kwargs) -> Any:
        """
        Forward method for smolagents Tool compatibility.
        """
        return self.run(task, **kwargs)

    def __call__(self, task: str, **kwargs) -> Any:
        """
        Make the agent instance callable for smolagents managed_agents compatibility.
        This allows the orchestrator to call this agent as a tool.
        """
        return self.run(task, **kwargs)

    @property
    def agent_description(self) -> str:
        """Get the agent description string."""
        with self._lock:
            return self._agent_description
        
    @agent_description.setter
    def agent_description(self, value: str) -> None:
        """Set the agent description string."""
        if not isinstance(value, str):
            raise ValueError("Agent description must be a string")
        
        with self._lock:
            self._agent_description = value
            
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
    
    def run(self, task: str, **kwargs) -> Any:
        """
        Synchronous run method for smolagents compatibility.
        Delegates to the internal CodeAgent.
        
        Args:
            task: The task or prompt for the agent
            **kwargs: Additional arguments passed to CodeAgent.run
            
        Returns:
            The result of the agent execution
        """
        if self._agent is None:
            with self._lock:
                if self._agent is None:
                    self._rebuild_code_agent()
        
        # Ensure we have an agent
        if self._agent is None:
            return "Error: Agent not initialized"
            
        return self._agent.run(task, **kwargs)

    def __call__(self, task: str, **kwargs) -> Any:
        """
        Make the agent instance callable for smolagents managed_agents compatibility.
        This allows the orchestrator to call this agent as a tool.
        """
        return self.run(task, **kwargs)

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
                code_block_tags=("<code>", "</code>"),
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
    
    def _register_managed_agent(self, agent: "BaseAgent") -> None:
        """
        Register a managed agent with automatic setup (description, validation, logging).
        
        Encapsulates the common pattern: set description, add to list, log, emit event.
        Used by all agent types (MainAgent, VisionAgent, etc.) to manage sub-agents.
        
        Args:
            agent: BaseAgent instance to register as managed agent
        
        Raises:
            ValueError: If agent is None or not a BaseAgent instance
        """
        if agent is None:
            raise ValueError("Agent cannot be None")
        
        if not isinstance(agent, BaseAgent):
            raise ValueError(f"Agent must be BaseAgent instance, got {type(agent)}")
        
        try:
            # Set description if not already set
            if not hasattr(agent, "agent_description") or not agent.agent_description:
                agent._set_description()
            
            # Add to managed agents list via parent property (thread-safe)
            current_agents = list(self._managed_agents)
            current_agents.append(agent)
            self.managed_agents = current_agents  # Uses property setter with lock
            
            # Log registration
            agent_name = agent.__class__.__name__
            description = getattr(agent, "agent_description", "No description")
            print(f"Registered {agent_name}: {description}")
            
            # Emit event for dashboard/logging
            self.bus.emit("agent.managed_agent_registered", {
                "agent_type": agent_name,
                "description": description,
                "total_managed_agents": len(self._managed_agents)
            })
            
        except Exception as e:
            print(f"Error registering managed agent: {e}")
            raise
    
    @abstractmethod
    def _set_description(self) -> None:
        """
        Set the agent_description attribute for this agent.
        Must be implemented by subclasses.
        
        Example:
            self.agent_description = "Brief description of what this agent does"
        """
        raise NotImplementedError
    
    def add_managed_agent(self, agent: "BaseAgent") -> bool:
        """
        Dynamically add a managed agent at runtime.
        
        Args:
            agent: BaseAgent instance to add
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            self._register_managed_agent(agent)
            # Rebuild CodeAgent with new managed agents
            if self._agent is not None:
                self._rebuild_code_agent()
            return True
        except Exception as e:
            self.bus.emit("agent.error", {
                "operation": "add_managed_agent",
                "error": str(e)
            })
            return False
    
    def remove_managed_agent(self, agent_name: str) -> bool:
        """
        Dynamically remove a managed agent by class name.
        
        Args:
            agent_name: Class name of agent to remove (e.g., "VisionAgent")
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            with self._lock:
                original_count = len(self._managed_agents)
                self._managed_agents = [
                    a for a in self._managed_agents
                    if a.__class__.__name__ != agent_name
                ]
                
                if len(self._managed_agents) == original_count:
                    self.bus.emit("agent.error", {
                        "operation": "remove_managed_agent",
                        "agent_name": agent_name,
                        "error": f"Agent '{agent_name}' not found"
                    })
                    return False
                
                # Trigger property setter to emit events and rebuild
                self.managed_agents = self._managed_agents
                
                self.bus.emit("agent.managed_agent_removed", {
                    "agent_name": agent_name,
                    "remaining_count": len(self._managed_agents)
                })
                
                return True
        except Exception as e:
            self.bus.emit("agent.error", {
                "operation": "remove_managed_agent",
                "agent_name": agent_name,
                "error": str(e)
            })
            return False
    
    def create_managed_agent(self, agent_type: str) -> bool:
        """
        Dynamically create and add a managed agent by type.
        
        Args:
            agent_type: Registered agent type name
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            agent = AgentFactory.create(
                agent_type=agent_type,
                state=self.state,
                bus=self.bus,
                registry=self.registry,
                notifier=self.notifier,
                store=self.store,
                session_id=self.session_id
            )
            
            if agent is None:
                self.bus.emit("agent.creation_failed", {
                    "agent_type": agent_type,
                    "reason": f"Unknown agent type: {agent_type}"
                })
                return False
            
            self.add_managed_agent(agent)
            
            self.bus.emit("agent.created", {
                "agent_type": agent_type,
                "description": agent.agent_description
            })
            
            return True
            
        except Exception as e:
            self.bus.emit("agent.creation_failed", {
                "agent_type": agent_type,
                "reason": str(e)
            })
            return False
    
    def get_available_agent_types(self) -> List[str]:
        """Get list of agent types that can be created."""
        return AgentFactory.available_types()

    def undelegate_agent(self, agent_name: str) -> bool:
        """Alias for remove_managed_agent."""
        return self.remove_managed_agent(agent_name)


