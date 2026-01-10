"""
Agent Factory for dynamic agent instantiation.
Provides pattern for registering and creating agent types at runtime.
"""
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.core.events import EventBus
    from src.agents.core.registry import ToolRegistry
    from src.agents.core.store import SQLiteStore
    from src.agents.notify.notifier import Notifier
    from src.agents.state import SharedState


class AgentFactory:
    """Factory for dynamically creating agent instances."""
    
    _registry: Dict[str, type] = {}
    _instances: Dict[str, Any] = {}
    
    @classmethod
    def register(cls, agent_type: str, agent_class: type) -> None:
        """
        Register an agent type for factory creation.
        
        Args:
            agent_type: Unique identifier for agent type (e.g., "vision", "code")
            agent_class: BaseAgent subclass to instantiate
        """
        cls._registry[agent_type] = agent_class
    
    @classmethod
    def register_instance(cls, name: str, instance: Any) -> None:
        """
        Register an active agent instance.
        
        Args:
            name: Unique name for the instance
            instance: Agent instance
        """
        cls._instances[name] = instance
    
    @classmethod
    def unregister_instance(cls, name: str) -> None:
        """Unregister an agent instance."""
        if name in cls._instances:
            del cls._instances[name]
    
    @classmethod
    def get_instance(cls, name: str) -> Optional[Any]:
        """Get an agent instance by name."""
        return cls._instances.get(name)
    
    @classmethod
    def resolve_instance(cls, identifier: Optional[str], default: Optional[Any] = None) -> Optional[Any]:
        """
        Resolve an agent instance by identifier (case-insensitive).

        Supports class names with or without the 'Agent' suffix.
        """
        if identifier is None or (isinstance(identifier, str) and not identifier.strip()):
            return default

        ident = str(identifier).strip().lower()
        for name, instance in cls._instances.items():
            class_name = instance.__class__.__name__
            class_lower = class_name.lower()
            candidates = {name.lower(), class_lower}
            if class_lower.endswith("agent"):
                candidates.add(class_lower[:-5])
            if ident in candidates:
                return instance

        if default and ident in ("main", "mainagent", "main_agent"):
            return default

        return None
    
    @classmethod
    def all_instances(cls) -> Dict[str, Any]:
        """Get all registered agent instances."""
        return dict(cls._instances)
    
    @classmethod
    def available_types(cls) -> List[str]:
        """Get list of available agent types."""
        return list(cls._registry.keys())
    
    @classmethod
    def create(
        cls,
        agent_type: str,
        state: "SharedState",
        bus: "EventBus",
        registry: "ToolRegistry",
        notifier: "Notifier",
        store: "SQLiteStore",
        session_id: str,
    ) -> Optional[Any]:
        """
        Create an agent instance by type.
        
        Args:
            agent_type: Registered agent type name
            state: Shared state blackboard
            bus: Event bus
            registry: Tool registry
            notifier: Notifier service
            store: SQLite store
            session_id: Session identifier
        
        Returns:
            BaseAgent instance or None if type not found
        
        Raises:
            RuntimeError: If instantiation fails
        """
        if agent_type not in cls._registry:
            return None
        
        agent_class = cls._registry[agent_type]
        try:
            agent = agent_class(
                state=state,
                bus=bus,
                registry=registry,
                notifier=notifier,
                store=store,
                session_id=session_id
            )
            return agent
        except Exception as e:
            raise RuntimeError(f"Failed to instantiate {agent_type}: {e}")
