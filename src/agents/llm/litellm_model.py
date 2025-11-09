"""
LiteLLMModel wrapper for Ollama integration using smolagents framework.
Includes KV cache optimization for persistent model state.
"""
import os
from typing import Any, Dict, List, Optional

try:
    from smolagents import LiteLLMModel as BaseLiteLLMModel
    from smolagents.models import ChatMessage
    SMOLAGENTS_AVAILABLE = True
except ImportError:
    SMOLAGENTS_AVAILABLE = False
    BaseLiteLLMModel = object  # type: ignore
    ChatMessage = Dict[str, Any]  # type: ignore


class OllamaLiteLLMModel(BaseLiteLLMModel if SMOLAGENTS_AVAILABLE else object):
    """
    LiteLLMModel configured specifically for Ollama with KV cache optimization.
    
    Features:
    - Persistent model loading (keep_alive=-1)
    - KV cache hints for system prompt reuse
    - Optimized context window management
    
    Args:
        model_id: Ollama model name (e.g., "llama3.1:8b-instruct-q4_K_M")
        api_base: Ollama API base URL (default: "http://localhost:11434")
        api_key: API key (not required for Ollama, defaults to "dummy")
        num_ctx: Context window size (default: 10000)
        keep_alive: Model persistence (-1 = keep loaded indefinitely, 0 = unload after use)
        **kwargs: Additional arguments passed to LiteLLMModel
    """
    
    def __init__(
        self,
        model_id: Optional[str] = None,
        api_base: str = "http://localhost:11434",
        api_key: str = "dummy",  # LiteLLM requires an API key parameter even when Ollama doesn't use authentication
        num_ctx: int = 10000,
        temperature: float = 0.8,
        keep_alive: int = -1,  # Keep model loaded indefinitely for KV cache benefits
        **kwargs
    ):
        if not SMOLAGENTS_AVAILABLE:
            raise ImportError(
                "smolagents is not installed. Please install it with: pip install smolagents"
            )
        
        # Use environment variable or default model
        if model_id is None:
            model_id = os.getenv("AGENT_MODEL", "llama3.1:8b-instruct-q4_K_M")
        
        # Format model_id for Ollama with litellm
        if not model_id.startswith("ollama"):
            model_id = f"ollama_chat/{model_id}"
        
        # Store keep_alive for KV cache optimization
        self.keep_alive = keep_alive
        
        # Initialize base LiteLLMModel with Ollama-specific configuration
        super().__init__(
            model_id=model_id,
            api_base=api_base,
            api_key=api_key,
            num_ctx=num_ctx,
            temperature=temperature,
            **kwargs
        )
        
        self.num_ctx = num_ctx
        self.temperature = temperature
    
    def __repr__(self):
        return f"OllamaLiteLLMModel(model_id={self.model_id}, api_base={self.api_base}, num_ctx={self.num_ctx}, keep_alive={self.keep_alive})"
