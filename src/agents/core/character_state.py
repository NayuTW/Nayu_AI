"""
Character state machine for tracking agent presence and attention.
"""
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional
import time


class CharacterState(Enum):
    """States representing the character's current activity."""
    IDLE = "idle"              # Waiting for input, passive observation
    THINKING = "thinking"       # Processing input, deciding action
    RESPONDING = "responding"   # Generating response
    INTERRUPTED = "interrupted" # Response was interrupted
    TOOL_USE = "tool_use"      # Executing a tool


@dataclass
class AttentionContext:
    """Context for what the character is currently focused on."""
    primary_task: str = ""
    source: str = "cli"
    user_id: Optional[str] = None
    channel_id: Optional[str] = None
    session_id: Optional[str] = None
    started_at: float = field(default_factory=time.time)
    
    def to_dict(self):
        return {
            "primary_task": self.primary_task,
            "source": self.source,
            "user_id": self.user_id,
            "channel_id": self.channel_id,
            "session_id": self.session_id,
            "started_at": self.started_at
        }


class CharacterStateMachine:
    """
    Manages the character's state and attention stack.
    
    Features:
    - State tracking (IDLE, THINKING, RESPONDING, etc.)
    - Attention stack for nested contexts
    - State transition history
    """
    
    def __init__(self):
        self.state = CharacterState.IDLE
        self._attention_stack: List[AttentionContext] = []
        self._state_history: List[tuple] = []  # (state, timestamp)
    
    def transition_to(self, new_state: CharacterState):
        """
        Transition to a new state.
        
        Args:
            new_state: The state to transition to
        """
        old_state = self.state
        self.state = new_state
        self._state_history.append((new_state, time.time()))
        
        # Keep only recent history (last 20 transitions)
        if len(self._state_history) > 20:
            self._state_history = self._state_history[-20:]
    
    def push_attention(self, context: AttentionContext):
        """
        Push a new attention context onto the stack.
        
        Args:
            context: The attention context to focus on
        """
        self._attention_stack.append(context)
    
    def pop_attention(self) -> Optional[AttentionContext]:
        """
        Pop the current attention context from the stack.
        
        Returns:
            The popped context or None if stack is empty
        """
        if self._attention_stack:
            return self._attention_stack.pop()
        return None
    
    def current_attention(self) -> Optional[AttentionContext]:
        """
        Get the current attention context without popping.
        
        Returns:
            Current attention context or None if idle
        """
        if self._attention_stack:
            return self._attention_stack[-1]
        return None
    
    def is_idle(self) -> bool:
        """Check if character is idle."""
        return self.state == CharacterState.IDLE
    
    def is_busy(self) -> bool:
        """Check if character is busy (not idle)."""
        return self.state != CharacterState.IDLE
    
    def get_state_info(self) -> dict:
        """
        Get current state information.
        
        Returns:
            Dictionary with state information
        """
        current_attention = self.current_attention()
        return {
            "state": self.state.value,
            "attention_depth": len(self._attention_stack),
            "current_attention": current_attention.to_dict() if current_attention else None,
            "recent_history": [
                {"state": s.value, "ts": ts} 
                for s, ts in self._state_history[-5:]
            ]
        }
