"""
InterruptManager for handling interrupt priority and routing.
"""
import asyncio
import logging
from typing import Optional, Callable, Awaitable, Dict, Any

from src.agents.core.events import EventBus, InterruptEvent, InterruptPriority

logger = logging.getLogger(__name__)


class InterruptManager:
    """
    Manages interrupt handling and routing.
    
    Features:
    - Priority-based interrupt handling
    - Interrupt callbacks for different interrupt types
    - Interrupt coalescing (combine similar interrupts)
    """
    
    def __init__(self, bus: EventBus):
        """
        Initialize the interrupt manager.
        
        Args:
            bus: EventBus instance for interrupt signaling
        """
        self.bus = bus
        self._handlers: Dict[str, Callable[[InterruptEvent], Awaitable[None]]] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def register_handler(
        self, 
        interrupt_type: str, 
        handler: Callable[[InterruptEvent], Awaitable[None]]
    ):
        """
        Register a handler for a specific interrupt type.
        
        Args:
            interrupt_type: Type of interrupt to handle
            handler: Async callable to handle the interrupt
        """
        self._handlers[interrupt_type] = handler
        logger.debug(f"Registered handler for interrupt type: {interrupt_type}")
    
    async def start(self):
        """Start the interrupt manager processing loop."""
        if self._running:
            logger.warning("InterruptManager already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._process_interrupts())
        logger.info("InterruptManager started")
    
    async def stop(self):
        """Stop the interrupt manager."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("InterruptManager stopped")
    
    async def _process_interrupts(self):
        """Process interrupts in priority order."""
        while self._running:
            try:
                # Wait for next interrupt with timeout
                interrupt = await self.bus.get_interrupt(timeout=1.0)
                
                if interrupt is None:
                    continue
                
                logger.debug(
                    f"Processing interrupt: type={interrupt.type}, "
                    f"priority={interrupt.priority.name}"
                )
                
                # Route to handler if registered
                handler = self._handlers.get(interrupt.type)
                if handler:
                    try:
                        await handler(interrupt)
                    except Exception as e:
                        logger.exception(
                            f"Error in interrupt handler for {interrupt.type}: {e}"
                        )
                else:
                    logger.debug(f"No handler registered for interrupt type: {interrupt.type}")
            
            except Exception as e:
                logger.exception(f"Error in interrupt processing loop: {e}")
                await asyncio.sleep(0.1)  # Prevent tight loop on error
    
    async def signal_user_input(self, text: str, source: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Signal a user input interrupt.
        
        Args:
            text: User input text
            source: Source of input (cli, discord, etc.)
            metadata: Additional metadata
        """
        await self.bus.signal_interrupt(
            interrupt_type="user.input",
            payload={
                "text": text,
                "source": source,
                "metadata": metadata or {}
            },
            priority=InterruptPriority.NORMAL
        )
    
    async def signal_stop(self):
        """Signal a stop interrupt (high priority)."""
        await self.bus.signal_interrupt(
            interrupt_type="system.stop",
            payload={},
            priority=InterruptPriority.HIGH
        )
