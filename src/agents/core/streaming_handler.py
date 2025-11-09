"""
StreamingResponseHandler for managing token-by-token response streaming.
"""
import asyncio
import logging
from typing import AsyncIterator, Optional, Callable, Awaitable
from dataclasses import dataclass
import time

from src.agents.core.events import EventBus

logger = logging.getLogger(__name__)


@dataclass
class StreamChunk:
    """A chunk of streamed response."""
    content: str
    is_final: bool = False
    timestamp: float = 0.0
    metadata: dict = None
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if self.metadata is None:
            self.metadata = {}


class StreamingResponseHandler:
    """
    Handles streaming responses from LLM with interrupt support.
    
    Features:
    - Token-by-token streaming
    - Interrupt checking during stream
    - Partial response emission via EventBus
    - Buffer management for smooth display
    """
    
    def __init__(
        self, 
        bus: EventBus,
        buffer_size: int = 5,
        check_interrupt_every: int = 3
    ):
        """
        Initialize the streaming handler.
        
        Args:
            bus: EventBus for emitting stream events
            buffer_size: Number of tokens to buffer before emitting
            check_interrupt_every: Check for interrupts every N tokens
        """
        self.bus = bus
        self.buffer_size = buffer_size
        self.check_interrupt_every = check_interrupt_every
        self._buffer = []
        self._token_count = 0
        self._interrupted = False
    
    async def stream_response(
        self,
        generator: AsyncIterator[str],
        source: str = "cli",
        session_id: Optional[str] = None,
        on_interrupt: Optional[Callable[[], Awaitable[None]]] = None
    ) -> str:
        """
        Stream a response from an async generator with interrupt support.
        
        Args:
            generator: Async iterator yielding tokens
            source: Source of the request (for event routing)
            session_id: Session ID for the response
            on_interrupt: Optional callback when interrupted
            
        Returns:
            Complete response text (even if interrupted)
        """
        full_response = []
        self._buffer = []
        self._token_count = 0
        self._interrupted = False
        
        try:
            async for token in generator:
                # Check for interrupts
                if self._token_count % self.check_interrupt_every == 0:
                    if self.bus.has_interrupt():
                        self._interrupted = True
                        logger.info("Stream interrupted by user input")
                        
                        # Emit interrupt event
                        await self.bus.publish("stream.interrupted", {
                            "source": source,
                            "session_id": session_id,
                            "partial_response": "".join(full_response)
                        })
                        
                        if on_interrupt:
                            await on_interrupt()
                        
                        break
                
                # Add token to buffers
                full_response.append(token)
                self._buffer.append(token)
                self._token_count += 1
                
                # Emit buffered tokens
                if len(self._buffer) >= self.buffer_size:
                    await self._emit_chunk(source, session_id)
            
            # Emit remaining buffer
            if self._buffer:
                await self._emit_chunk(source, session_id, is_final=True)
            
            # Emit completion event
            if not self._interrupted:
                await self.bus.publish("stream.complete", {
                    "source": source,
                    "session_id": session_id,
                    "response": "".join(full_response),
                    "token_count": self._token_count
                })
        
        except Exception as e:
            logger.exception(f"Error during streaming: {e}")
            await self.bus.publish("stream.error", {
                "source": source,
                "session_id": session_id,
                "error": str(e)
            })
        
        return "".join(full_response)
    
    async def _emit_chunk(self, source: str, session_id: Optional[str], is_final: bool = False):
        """Emit buffered tokens as a stream chunk."""
        if not self._buffer:
            return
        
        chunk_text = "".join(self._buffer)
        self._buffer = []
        
        chunk = StreamChunk(
            content=chunk_text,
            is_final=is_final,
            metadata={"source": source, "session_id": session_id}
        )
        
        await self.bus.publish("stream.chunk", {
            "content": chunk.content,
            "is_final": chunk.is_final,
            "source": source,
            "session_id": session_id,
            "token_count": self._token_count
        })
    
    def was_interrupted(self) -> bool:
        """Check if the stream was interrupted."""
        return self._interrupted


async def stream_from_litellm(
    model,
    messages: list,
    **kwargs
) -> AsyncIterator[str]:
    """
    Create an async generator from LiteLLM streaming response.
    
    This is a compatibility layer for streaming with LiteLLM/Ollama.
    
    Args:
        model: LiteLLM model instance
        messages: List of message dicts
        **kwargs: Additional arguments for model call
        
    Yields:
        Token strings
    """
    try:
        # LiteLLM streaming returns chunks with delta content
        # We need to extract the text from each chunk
        
        # For now, we'll use a simple approach that works with Ollama
        # In production, you'd integrate directly with litellm's streaming API
        
        # Check if model supports streaming
        if hasattr(model, 'client'):
            # Use litellm's streaming
            import litellm
            
            response = litellm.completion(
                model=model.model_id,
                messages=messages,
                stream=True,
                api_base=getattr(model, 'api_base', None),
                **kwargs
            )
            
            for chunk in response:
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if hasattr(delta, 'content') and delta.content:
                        yield delta.content
        else:
            # Fallback: non-streaming
            # This ensures compatibility if streaming isn't available
            result = await asyncio.to_thread(
                model,
                messages,
                **kwargs
            )
            # Yield entire response at once
            if isinstance(result, str):
                yield result
            elif hasattr(result, 'content'):
                yield result.content
    
    except Exception as e:
        logger.exception(f"Error in stream_from_litellm: {e}")
        # Yield error message so something is returned
        yield f"[Streaming error: {str(e)}]"
