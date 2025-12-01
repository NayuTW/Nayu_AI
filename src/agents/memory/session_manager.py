"""
Session Manager for short-term conversational memory.

This module provides session-scoped conversations with:
- Rolling context window (last N messages within token budget)
- Running summary (ultra-compact conversation summary)
- Working set memory (task and artifact notes)
- Efficient persistence (JSONL with in-memory LRU cache)
"""
import json
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A single message in the conversation."""
    role: str  # "user" or "assistant"
    content: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkingSet:
    """Working set memory for task and artifact tracking."""
    last_task: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, Any] = field(default_factory=dict)
    env_context: dict[str, Any] = field(default_factory=dict)
    
    def update_task(self, task_id: str, task_type: str, outcome: str):
        """Update the last task information."""
        self.last_task = {
            "id": task_id,
            "type": task_type,
            "outcome": outcome,
            "timestamp": time.time()
        }
    
    def update_artifact(self, key: str, value: Any):
        """Update an artifact in the working set."""
        self.artifacts[key] = value
    
    def update_env(self, key: str, value: Any):
        """Update environment context."""
        self.env_context[key] = value
    
    def to_context_string(self) -> str:
        """Convert working set to a compact context string."""
        parts = []
        if self.last_task:
            parts.append(f"Last task: {self.last_task.get('type', 'unknown')} - {self.last_task.get('outcome', 'unknown')}")
        if self.artifacts:
            artifact_strs = [f"{k}={v}" for k, v in self.artifacts.items() if v]
            if artifact_strs:
                parts.append(f"Artifacts: {', '.join(artifact_strs)}")
        if self.env_context:
            env_strs = [f"{k}={v}" for k, v in self.env_context.items() if v]
            if env_strs:
                parts.append(f"Environment: {', '.join(env_strs)}")
        return "\n".join(parts) if parts else ""


@dataclass
class SessionState:
    """State for a single session."""
    session_id: str
    messages: list[Message] = field(default_factory=list)
    summary: str = ""
    working_set: WorkingSet = field(default_factory=WorkingSet)
    last_updated: float = field(default_factory=time.time)
    turn_count: int = 0


class SessionManager:
    """
    Manages session-scoped conversations with rolling context and summaries.
    
    Features:
    - Rolling context window with configurable token budget
    - Automatic conversation summarization every N turns
    - Working set memory for task/artifact tracking
    - Efficient disk persistence with in-memory LRU cache
    """
    
    def __init__(
        self,
        session_dir: str = ".nayu_ai/sessions",
        max_messages: int = 20,
        max_tokens: int = 4096,
        summary_interval: int = 5,
        max_cache_size: int = 10
    ):
        """
        Initialize the session manager.
        
        Args:
            session_dir: Directory to store session files
            max_messages: Maximum messages to keep in rolling window
            max_tokens: Approximate token budget for rolling window
            summary_interval: Generate summary every N turns
            max_cache_size: Maximum sessions to keep in memory cache
        """
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self.summary_interval = summary_interval
        
        # LRU cache for active sessions
        self._cache: OrderedDict[str, SessionState] = OrderedDict()
        self._max_cache_size = max_cache_size
    
    def _get_session_path(self, session_id: str) -> Path:
        """Get the file path for a session."""
        # Sanitize session_id for filesystem
        safe_id = "".join(char if char.isalnum() or char in "-_" else "_" for char in session_id)
        return self.session_dir / f"{safe_id}.json"
    
    def _load_session_from_disk(self, session_id: str) -> Optional[SessionState]:
        """Load a session from disk."""
        path = self._get_session_path(session_id)
        if not path.exists():
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Reconstruct SessionState
            messages = [Message(**m) for m in data.get("messages", [])]
            working_set = WorkingSet(**data.get("working_set", {}))
            
            return SessionState(
                session_id=session_id,
                messages=messages,
                summary=data.get("summary", ""),
                working_set=working_set,
                last_updated=data.get("last_updated", time.time()),
                turn_count=data.get("turn_count", 0)
            )
        except Exception as e:
            logger.warning(f"Failed to load session {session_id}: {e}")
            return None
    
    def _save_session_to_disk(self, state: SessionState):
        """Save a session to disk."""
        path = self._get_session_path(state.session_id)
        
        try:
            # Convert to dict for JSON serialization
            data = {
                "session_id": state.session_id,
                "messages": [asdict(m) for m in state.messages],
                "summary": state.summary,
                "working_set": asdict(state.working_set),
                "last_updated": state.last_updated,
                "turn_count": state.turn_count
            }
            
            # Atomic write
            temp_path = path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.replace(path)
            
        except Exception as e:
            logger.warning(f"Failed to save session {state.session_id}: {e}")
    
    def get_session(self, session_id: str) -> SessionState:
        """
        Get or create a session state.
        
        Args:
            session_id: The session identifier
            
        Returns:
            The session state (from cache or disk, or newly created)
        """
        # Check cache first
        if session_id in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(session_id)
            return self._cache[session_id]
        
        # Try to load from disk
        state = self._load_session_from_disk(session_id)
        if state is None:
            # Create new session
            state = SessionState(session_id=session_id)
        
        # Add to cache
        self._cache[session_id] = state
        self._cache.move_to_end(session_id)
        
        # Evict oldest if cache is full
        if len(self._cache) > self._max_cache_size:
            oldest_id, oldest_state = self._cache.popitem(last=False)
            self._save_session_to_disk(oldest_state)
        
        return state
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None
    ):
        """
        Add a message to the session.
        
        Args:
            session_id: The session identifier
            role: Message role ("user" or "assistant")
            content: Message content
            metadata: Optional metadata for the message
        """
        state = self.get_session(session_id)
        
        message = Message(
            role=role,
            content=content,
            timestamp=time.time(),
            metadata=metadata or {}
        )
        
        state.messages.append(message)
        state.last_updated = time.time()
        
        if role == "user":
            state.turn_count += 1
        
        # Truncate messages if exceeding limits
        self._truncate_messages(state)
        
        # Generate summary if needed
        if state.turn_count > 0 and state.turn_count % self.summary_interval == 0:
            self._generate_summary(state)
        
        # Save to disk (write-through cache)
        self._save_session_to_disk(state)
    
    def _estimate_tokens(self, messages: list[Message]) -> int:
        """Estimate token count for messages. Rough estimate: 1 token ≈ 4 characters."""
        total_chars = sum(len(m.content) for m in messages)
        return total_chars // 4
    
    def _truncate_messages(self, state: SessionState):
        """Truncate messages to stay within token budget and message limit."""
        # Simple truncation: keep last N messages
        if len(state.messages) > self.max_messages:
            state.messages = state.messages[-self.max_messages:]
        
        # Token-based truncation (approximate)
        estimated_tokens = self._estimate_tokens(state.messages)
        
        while estimated_tokens > self.max_tokens and len(state.messages) > 5:
            # Keep at least 5 messages
            removed_msg = state.messages.pop(0)
            # Subtract the removed message's tokens for efficiency
            estimated_tokens -= len(removed_msg.content) // 4
    
    def _generate_summary(self, state: SessionState):
        """
        Generate a compact summary of the conversation.
        
        This is a simple implementation that captures recent context.
        In a production system, you might use an LLM to generate better summaries.
        """
        if len(state.messages) < 3:
            return
        
        # Extract key points from recent messages
        recent_messages = state.messages[-10:]
        
        # Simple summary: concatenate user intents
        user_messages = [m.content for m in recent_messages if m.role == "user"]
        
        if user_messages:
            # Keep summary concise
            summary_parts = []
            if state.summary:
                summary_parts.append(state.summary)
            
            # Add recent context
            summary_parts.append(f"Recent topics: {'; '.join(user_messages[-3:])}")
            
            # Limit summary length
            new_summary = " | ".join(summary_parts)
            if len(new_summary) > 512:
                # Keep only the most recent part if too long
                new_summary = summary_parts[-1]
            
            state.summary = new_summary
    
    def get_context(self, session_id: str) -> tuple[str, str, list[Message]]:
        """
        Get the full context for a session.
        
        Returns:
            Tuple of (summary, working_set_context, recent_messages)
        """
        state = self.get_session(session_id)
        
        summary = state.summary
        working_set_context = state.working_set.to_context_string()
        recent_messages = state.messages
        
        return summary, working_set_context, recent_messages
    
    def update_working_set(
        self,
        session_id: str,
        task_info: Optional[dict[str, Any]] = None,
        artifacts: Optional[dict[str, Any]] = None,
        env_context: Optional[dict[str, Any]] = None
    ):
        """
        Update the working set for a session.
        
        Args:
            session_id: The session identifier
            task_info: Task information (id, type, outcome)
            artifacts: Artifact updates
            env_context: Environment context updates
        """
        state = self.get_session(session_id)
        
        if task_info:
            state.working_set.update_task(
                task_id=task_info.get("id", ""),
                task_type=task_info.get("type", ""),
                outcome=task_info.get("outcome", "")
            )
        
        if artifacts:
            for key, value in artifacts.items():
                state.working_set.update_artifact(key, value)
        
        if env_context:
            for key, value in env_context.items():
                state.working_set.update_env(key, value)
        
        state.last_updated = time.time()
        self._save_session_to_disk(state)
    
    def reset_session(self, session_id: str):
        """
        Reset a session, clearing all history.
        
        Args:
            session_id: The session identifier
        """
        # Remove from cache
        if session_id in self._cache:
            del self._cache[session_id]
        
        # Delete from disk
        path = self._get_session_path(session_id)
        if path.exists():
            path.unlink()
    
    def list_sessions(self) -> list[str]:
        """List all available sessions."""
        return [
            p.stem for p in self.session_dir.glob("*.json")
        ]
    
    def flush_cache(self):
        """Flush all cached sessions to disk."""
        for state in self._cache.values():
            self._save_session_to_disk(state)
