"""
VisionTool converted to smolagents Tool class.
Uses Ollama Vision Language Model to analyze images.
"""
import os
import base64
from typing import Optional
from smolagents import Tool

try:
    import aiohttp
    from PIL import Image
    VISION_AVAILABLE = True
except ImportError:
    VISION_AVAILABLE = False


class VisionSmolTool(Tool):
    """
    Describe images or extract text from them using a Vision Language Model.
    """
    name = "vision"
    description = (
        "Analyze an image (e.g., a screenshot) or read text from it. "
        "Provide the full path to the image file. "
        "Optionally provide a custom prompt for specific analysis tasks."
    )
    inputs = {
        "path": {
            "type": "string",
            "description": "Full path to the image file (e.g., '.cache/screenshot_1234567890.png')"
        },
        "prompt": {
            "type": "string",
            "description": "Custom prompt for image analysis",
            "nullable": True
        }
    }
    output_type = "string"
    
    def __init__(self, model_id: str = "gemma3:12b-it-q4_K_M", ollama_url: str = "http://localhost:11434", timeout: int = 120):
        super().__init__()
        if not VISION_AVAILABLE:
            raise ImportError(
                "Vision tools not available. Install with: pip install aiohttp Pillow"
            )
        
        self.model_id = model_id
        self.ollama_url = ollama_url
        self.generate_url = f"{ollama_url}/api/generate"
        self.timeout = timeout
    
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
        
        # Prepare request payload
        payload = {
            "model": self.model_id,
            "prompt": prompt,
            "images": [image_b64],
            "stream": False
        }
        
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
                asyncio.get_running_loop()
                # If we get here, we're in a running loop - not supported yet
                return "Error: Vision tool cannot be called from within an async context. Please call from sync context."
            except RuntimeError:
                # No running loop, safe to use asyncio.run()
                pass
            
            result = asyncio.run(self._analyze_image_async(path, prompt))
            return result
        
        except Exception as e:
            return f"Error analyzing image: {str(e)}"
