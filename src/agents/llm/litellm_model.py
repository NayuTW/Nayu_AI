"""
LiteLLMModel wrapper for Ollama integration using smolagents framework.
"""
import os
from typing import Any, Optional
import litellm

try:
    from smolagents import LiteLLMModel as BaseLiteLLMModel
    from smolagents.models import ChatMessage
    SMOLAGENTS_AVAILABLE = True
except ImportError:
    SMOLAGENTS_AVAILABLE = False
    BaseLiteLLMModel = object  # type: ignore
    ChatMessage = dict[str, Any]  # type: ignore


class OllamaLiteLLMModel(BaseLiteLLMModel if SMOLAGENTS_AVAILABLE else object):
    """
    LiteLLMModel configured specifically for Ollama.
    
    Args:
        model_id: Ollama model name (e.g., "llama3.1:8b-instruct-q4_K_M")
        api_base: Ollama API base URL (default: "http://localhost:11434")
        api_key: API key (not required for Ollama, defaults to "dummy")
        num_ctx: Context window size (default: 24576)
        **kwargs: Additional arguments passed to LiteLLMModel
    """
    
    def __call__(self, messages, stream=False, **kwargs):
        """Call the model using litellm.completion with explicit Ollama routing."""
        # Ensure model is set
        if not self.model_id:
            raise ValueError("model_id not set on OllamaLiteLLMModel")
        
        # Set up LiteLLM for Ollama
        # Extract any temp override or use instance settings
        api_base = kwargs.pop("api_base", self.api_base)
        
        completion_kwargs = {
            "model": self.model_id,
            "messages": messages,
            "api_base": api_base,
            "stream": stream,
        }
        
        # Add optional params if set
        if hasattr(self, "num_ctx") and self.num_ctx:
            completion_kwargs["num_ctx"] = self.num_ctx
        if hasattr(self, "temperature") and self.temperature is not None:
            completion_kwargs["temperature"] = self.temperature
        
        # Merge in any additional kwargs (but don't override our essentials)
        for k, v in kwargs.items():
            if k not in completion_kwargs:
                completion_kwargs[k] = v
        
        # Call litellm synchronously
        return litellm.completion(**completion_kwargs)

    def __init__(
        self,
        model_id: Optional[str] = None,
        api_base: str = "http://localhost:11434",
        api_key: str = "dummy",  # LiteLLM requires an API key parameter even when Ollama doesn't use authentication
        num_ctx: int = 4096,
        temperature: float = 0.6,
        use_chat_api: Optional[bool] = None,
        **kwargs
    ):
        if not SMOLAGENTS_AVAILABLE:
            raise ImportError(
                "smolagents is not installed. Please install it with: pip install smolagents"
            )

        # Allow env override for chat vs completion routing (default True)
        if use_chat_api is None:
            env_chat = os.getenv("OLLAMA_USE_CHAT", "true").lower()
            use_chat_api = env_chat in ("1", "true", "yes", "y")
        
        # Use environment variable or default model, guard against empty values
        if not model_id or not str(model_id).strip():
            env_model = os.getenv("AGENT_MODEL")
            model_id = (env_model.strip() if env_model and env_model.strip() else "qwen2:7b-instruct-q5_K_M")

        # Normalize model_id for LiteLLM + Ollama
        # LiteLLM supports either completion (ollama/) or chat (ollama_chat/) endpoints.
        if use_chat_api:
            if model_id.startswith("ollama_chat/"):
                normalized_model = model_id
            elif model_id.startswith("ollama/"):
                normalized_model = model_id.replace("ollama/", "ollama_chat/", 1)
            else:
                normalized_model = f"ollama_chat/{model_id}"
        else:
            if model_id.startswith("ollama/"):
                normalized_model = model_id
            elif model_id.startswith("ollama_chat/"):
                normalized_model = model_id.replace("ollama_chat/", "ollama/", 1)
            else:
                normalized_model = f"ollama/{model_id}"
        
        # Initialize base LiteLLMModel with NORMALIZED model_id
        # Pass normalized model to parent to prevent caching issues
        super().__init__(
            model_id=normalized_model,
            api_base=api_base,
            api_key=api_key,
            num_ctx=num_ctx,
            temperature=temperature,
            **kwargs
        )
        
        # Store locally for access in __call__
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.api_base = api_base
        self.use_chat_api = use_chat_api
    
    def __repr__(self):
        return f"OllamaLiteLLMModel(model_id={self.model_id}, num_ctx={self.num_ctx})"
