"""
ContinuousAgentRunner - Main event loop coordinator for continuous agent operation.
"""
import asyncio
import logging
from typing import Optional, Any, Dict

from src.agents.core.events import EventBus, InterruptPriority
from src.agents.core.interrupt_manager import InterruptManager
from src.agents.core.character_state import CharacterStateMachine, CharacterState, AttentionContext

logger = logging.getLogger(__name__)


class ContinuousAgentRunner:
    """
    Coordinates continuous agent operation with event-driven input handling.
    
    Features:
    - Non-blocking input processing via queues
    - Interrupt-aware agent execution
    - Character state management
    - Idle/active state transitions
    """
    
    def __init__(
        self,
        agent,
        bus: EventBus,
        interrupt_manager: InterruptManager
    ):
        """
        Initialize the continuous agent runner.
        
        Args:
            agent: MainAgentSmol instance
            bus: EventBus for pub/sub
            interrupt_manager: InterruptManager for interrupt handling
        """
        self.agent = agent
        self.bus = bus
        self.interrupt_manager = interrupt_manager
        self.state_machine = CharacterStateMachine()
        
        self._running = False
        self._input_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._task: Optional[asyncio.Task] = None
        
        # Register interrupt handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register interrupt handlers with the interrupt manager."""
        self.interrupt_manager.register_handler(
            "user.input",
            self._handle_user_input_interrupt
        )
        self.interrupt_manager.register_handler(
            "system.stop",
            self._handle_stop_interrupt
        )
    
    async def _handle_user_input_interrupt(self, interrupt):
        """Handle user input interrupt."""
        payload = interrupt.payload
        
        # Add to input queue for processing
        try:
            await self._input_queue.put(payload)
            logger.debug(f"Queued user input from {payload.get('source')}")
        except asyncio.QueueFull:
            logger.warning("Input queue full, dropping message")
    
    async def _handle_stop_interrupt(self, interrupt):
        """Handle stop interrupt."""
        logger.info("Received stop interrupt, shutting down...")
        self._running = False
    
    async def start(self):
        """Start the continuous agent runner."""
        if self._running:
            logger.warning("ContinuousAgentRunner already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("ContinuousAgentRunner started")
        
        # Publish event
        await self.bus.publish("agent.started", {
            "state": self.state_machine.state.value
        })
    
    async def stop(self):
        """Stop the continuous agent runner."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("ContinuousAgentRunner stopped")
        
        # Publish event
        await self.bus.publish("agent.stopped", {})
    
    async def _run_loop(self):
        """Main continuous operation loop."""
        while self._running:
            try:
                # Idle state - wait for input
                if self.state_machine.is_idle():
                    # Publish idle heartbeat every 5 seconds
                    try:
                        message = await asyncio.wait_for(
                            self._input_queue.get(),
                            timeout=5.0
                        )
                        # Process the message
                        await self._process_input(message)
                    except asyncio.TimeoutError:
                        # Still idle, publish heartbeat
                        await self.bus.publish("agent.heartbeat", {
                            "state": self.state_machine.state.value,
                            "state_info": self.state_machine.get_state_info()
                        })
                        continue
                
                # If not idle, check for interrupts
                elif self.state_machine.is_busy():
                    # Check for high-priority interrupts
                    if self.bus.has_interrupt():
                        interrupt = await self.bus.get_interrupt(timeout=0.1)
                        if interrupt and interrupt.priority == InterruptPriority.HIGH:
                            logger.info(f"High priority interrupt received: {interrupt.type}")
                            self.state_machine.transition_to(CharacterState.INTERRUPTED)
                            # Handle through interrupt manager
                    
                    # Small sleep to prevent tight loop
                    await asyncio.sleep(0.1)
            
            except Exception as e:
                logger.exception(f"Error in continuous agent loop: {e}")
                await asyncio.sleep(1.0)  # Prevent tight loop on error
    
    async def _process_input(self, message: Dict[str, Any]):
        """
        Process a user input message.
        
        Args:
            message: Message dict with 'text', 'source', 'metadata'
        """
        text = message.get("text", "")
        source = message.get("source", "cli")
        metadata = message.get("metadata", {})
        user_id = metadata.get("user_id")
        channel_id = metadata.get("channel_id")
        session_id = metadata.get("session_id")
        
        # Transition to thinking state
        self.state_machine.transition_to(CharacterState.THINKING)
        
        # Push attention context
        context = AttentionContext(
            primary_task=f"Responding to: {text[:50]}...",
            source=source,
            user_id=user_id,
            channel_id=channel_id,
            session_id=session_id
        )
        self.state_machine.push_attention(context)
        
        try:
            # Publish thinking event
            await self.bus.publish("agent.thinking", {
                "text": text,
                "source": source,
                "state": self.state_machine.state.value
            })
            
            # Transition to responding state
            self.state_machine.transition_to(CharacterState.RESPONDING)
            
            # Process with agent
            response = await self.agent.handle_user_message(
                user_text=text,
                source=source,
                external_metadata=metadata,
                user_id=user_id,
                channel_id=channel_id,
                session_id=session_id
            )
            
            # Publish response complete event
            await self.bus.publish("agent.response_complete", {
                "text": text,
                "response": response,
                "source": source
            })
            
        except Exception as e:
            logger.exception(f"Error processing input: {e}")
            await self.bus.publish("agent.error", {
                "error": str(e),
                "source": source
            })
        
        finally:
            # Pop attention context
            self.state_machine.pop_attention()
            
            # Return to idle state
            self.state_machine.transition_to(CharacterState.IDLE)
    
    async def queue_input(
        self, 
        text: str, 
        source: str = "cli", 
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Queue a user input for processing.
        
        Args:
            text: Input text
            source: Source of input
            metadata: Additional metadata
        """
        message = {
            "text": text,
            "source": source,
            "metadata": metadata or {}
        }
        
        try:
            await self._input_queue.put(message)
        except asyncio.QueueFull:
            logger.warning("Input queue full, dropping message")
    
    def get_state(self) -> CharacterState:
        """Get current character state."""
        return self.state_machine.state
    
    def get_state_info(self) -> dict:
        """Get detailed state information."""
        return self.state_machine.get_state_info()
