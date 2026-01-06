"""
VisionTool converted to smolagents Tool class.
Uses Ollama Vision Language Model to analyze images.
"""
import os
import base64
from typing import Optional, Any
from smolagents import Tool

import aiohttp
from PIL import Image


class VisionSmolTool(Tool):
    """
    Analyze images or read text from them using a Vision Language Model.
    """
    name = "vision"
    description = (
        "Analyze an image or read text from it. "
        "Common usage: Provide the path to .cache/desktop.png to analyze the current desktop state. "
        "Optionally provide a custom prompt for specific analysis tasks. "
        "Input the full path to the image file."
    )
    inputs = {
        "path": {
            "type": "string",
            "description": "Full path to the image file (e.g., '.cache/desktop.png')"
        },
        "prompt": {
            "type": "string",
            "description": "Custom prompt for image analysis",
            "nullable": True
        }
    }
    output_type = "string"

    def __init__(self, agent: Optional[Any] = None, model_id: str = "gemma3:4b", api_base: str = "http://localhost:11434", timeout: int = 60):
        super().__init__()
        self.agent = agent
        self.model_id = model_id
        self.api_base = api_base
        self.generate_url = f"{api_base}/api/generate"
        self.timeout = timeout

    def forward(self, path: str, prompt: Optional[str] = None) -> str:
        """Analyze the image and return description."""
        
        # Validate path
        if not path or not path.strip():
            return "Error: path parameter is required and cannot be empty"
        
        # Check if file exists
        if not os.path.exists(path):
            return f"Error: Image file not found at path: {path}"
        
        # Default prompt
        if prompt is None:
            prompt = "Describe the image briefly with actionable details."
        
        try:
            # Validate it's a valid image by opening it
            Image.open(path).convert("RGB")
            
            # Run async analysis in sync context
            import asyncio
            try:
                # Check if we're in an existing event loop
                loop = asyncio.get_running_loop()
                
                # If we are in a loop, we can't use asyncio.run().
                # Since forward() is sync, we must run the coroutine in a separate thread
                # to avoid blocking the loop or causing "asyncio.run() cannot be called from a running event loop"
                import threading
                result_container = []
                exception_container = []
                
                def run_in_new_loop():
                    try:
                        res = asyncio.run(self._analyze_image_async(path, prompt))
                        result_container.append(res)
                    except Exception as e:
                        exception_container.append(e)
                
                thread = threading.Thread(target=run_in_new_loop)
                thread.start()
                thread.join()
                
                if exception_container:
                    raise exception_container[0]
                return result_container[0]
                
            except RuntimeError:
                # No running loop, safe to use asyncio.run()
                return asyncio.run(self._analyze_image_async(path, prompt))
        
        except Exception as e:
            return f"Error analyzing image: {str(e)}"
   
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode("utf-8")
    
    def setup(self):
        """Setup method for smolagents Tool compatibility."""
        super().setup()
    
    async def _analyze_image_async(self, path: str, prompt: str) -> str:
        """Async helper to analyze image with Ollama."""
        # Encode image to base64
        image_b64 = self._encode_image(path)
        
        # Determine model and num_ctx from agent if available
        model_id = self.model_id
        num_ctx = None
        
        if self.agent and hasattr(self.agent, "model") and self.agent.model:
            # Get model_id from agent's model
            # OllamaLiteLLMModel stores it as 'ollama_chat/model_name'
            raw_model_id = getattr(self.agent.model, "model_id", "")
            if raw_model_id.startswith("ollama_chat/"):
                model_id = raw_model_id.replace("ollama_chat/", "")
            elif raw_model_id:
                model_id = raw_model_id
            
            num_ctx = getattr(self.agent.model, "num_ctx", None)
        
        # Prepare request payload
        payload = {
            "model": model_id,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False
        }
        
        # Add options if num_ctx is available
        if num_ctx:
            payload["options"] = {"num_ctx": num_ctx}
        
        # Make request to Ollama
        async with aiohttp.ClientSession() as session:
            async with session.post(self.generate_url, json=payload, timeout=aiohttp.ClientTimeout(total=self.timeout)) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    raise RuntimeError(f"Ollama API error (status {resp.status}): {error_text}")
                
                data = await resp.json()
                response_text = data.get("response", "")
                
                if not response_text:
                    raise RuntimeError("Ollama returned empty response")
                
                return response_text