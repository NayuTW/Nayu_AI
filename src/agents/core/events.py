import asyncio
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional

class InterruptPriority(IntEnum):
    """Priority levels for interrupts."""
    HIGH = 3      # Emergency stops, critical errors
    NORMAL = 2    # User input, new messages
    BACKGROUND = 1  # Low-priority notifications

@dataclass
class Event:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=lambda: time.time())

@dataclass
class InterruptEvent:
    """An interrupt event with priority."""
    type: str
    payload: Dict[str, Any]
    priority: InterruptPriority
    ts: float = field(default_factory=lambda: time.time())

class EventBus:
    def __init__(self, store=None):
        self._subscribers: List[asyncio.Queue] = []
        self._lock = asyncio.Lock()
        self._store = store  # Optional SQLiteStore
        
        # Interrupt handling
        self._interrupt_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._interrupt_flag = asyncio.Event()

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=1000)
        async with self._lock:
            self._subscribers.append(q)
        return q

    async def unsubscribe(self, q: asyncio.Queue):
        async with self._lock:
            if q in self._subscribers:
                self._subscribers.remove(q)

    async def publish(self, event_type: str, payload: Dict[str, Any]):
        ev = Event(type=event_type, payload=payload)
        if self._store:
            try:
                self._store.append_event(ev.type, ev.payload, ts=ev.ts)
            except Exception:
                pass
        # Avoid creating a new list on every publish
        async with self._lock:
            subscribers = self._subscribers.copy()
        for q in subscribers:
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                pass
    
    async def signal_interrupt(
        self, 
        interrupt_type: str, 
        payload: Dict[str, Any], 
        priority: InterruptPriority = InterruptPriority.NORMAL
    ):
        """
        Signal an interrupt to the agent.
        
        Args:
            interrupt_type: Type of interrupt (e.g., "user.input", "system.stop")
            payload: Interrupt data
            priority: Priority level of the interrupt
        """
        interrupt = InterruptEvent(
            type=interrupt_type,
            payload=payload,
            priority=priority
        )
        
        try:
            self._interrupt_queue.put_nowait(interrupt)
            self._interrupt_flag.set()
            
            # Also publish as regular event for logging
            await self.publish(f"interrupt.{interrupt_type}", {
                **payload,
                "priority": priority.name
            })
        except asyncio.QueueFull:
            # If queue is full, drop lowest priority interrupts
            pass
    
    async def get_interrupt(self, timeout: Optional[float] = None) -> Optional[InterruptEvent]:
        """
        Get the next interrupt from the queue.
        
        Args:
            timeout: Maximum time to wait for interrupt (None = wait indefinitely)
            
        Returns:
            Next interrupt event or None if timeout
        """
        try:
            if timeout:
                return await asyncio.wait_for(self._interrupt_queue.get(), timeout=timeout)
            else:
                return await self._interrupt_queue.get()
        except asyncio.TimeoutError:
            return None
    
    def has_interrupt(self) -> bool:
        """Check if there's a pending interrupt without blocking."""
        return not self._interrupt_queue.empty()
    
    def clear_interrupt_flag(self):
        """Clear the interrupt flag."""
        self._interrupt_flag.clear()
    
    def is_interrupt_signaled(self) -> bool:
        """Check if an interrupt has been signaled."""
        return self._interrupt_flag.is_set()