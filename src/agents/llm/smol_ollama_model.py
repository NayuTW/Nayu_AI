from typing import List, Optional
import os
import aiohttp

class SmolOllamaModel:
    """
    Minimal smolagents-compatible model wrapper for Ollama.
    """

    def __init__(self, model: Optional[str] = None, num_ctx: int = 12000, temperature: float = 0.2):
        # Use environment variable or default
        if model is None:
            model = os.getenv("AGENT_MODEL", "llama3.1:8b-instruct-q4_K_M")
        self.model = model
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.url = "http://localhost:11434/api/generate"

    async def generate(self, prompt: str, stop: Optional[List[str]] = None, max_tokens: Optional[int] = None, temperature: Optional[float] = None) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "options": {
                "temperature": self.temperature if temperature is None else temperature,
                "num_ctx": self.num_ctx,
            },
            "stream": False,
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, json=payload, timeout=0) as resp:
                data = await resp.json()
        return data.get("response", "")
