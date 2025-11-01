"""
VisionTool converted to smolagents Tool class.
Uses a Vision Language Model to analyze images.
"""
import os
from typing import Optional
from smolagents import Tool

try:
    import torch
    from PIL import Image
    from transformers import AutoProcessor, AutoModelForImageTextToText
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
    
    def __init__(self, model_id: str = "Qwen/Qwen2-VL-2B-Instruct"):
        super().__init__()
        if not VISION_AVAILABLE:
            raise ImportError(
                "Vision tools not available. Install with: pip install torch transformers Pillow"
            )
        
        self.model_id = model_id
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = None
        self.model = None
    
    def _get_model_config(self):
        """Get device-specific model configuration."""
        is_cuda = self.device == "cuda"
        return {
            "dtype": torch.float16 if is_cuda else torch.float32,
            "load_in_4bit": is_cuda,
            "device_map": "auto",
            "trust_remote_code": True
        }
    
    def setup(self):
        """Lazy load the model on first use."""
        if self.model is None:
            try:
                self.processor = AutoProcessor.from_pretrained(self.model_id, trust_remote_code=True)
                self.model = AutoModelForImageTextToText.from_pretrained(
                    self.model_id,
                    **self._get_model_config()
                )
            except Exception as e:
                raise RuntimeError(f"Failed to load vision model: {e}")
        super().setup()
    
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
            # Load and process image
            image = Image.open(path).convert("RGB")
            inputs = self.processor(text=prompt, images=image, return_tensors="pt").to(self.device)
            
            # Generate description
            with torch.inference_mode():
                out = self.model.generate(**inputs, max_new_tokens=256)
            
            # Decode output
            decoded = self.processor.batch_decode(out, skip_special_tokens=True)
            if not decoded or len(decoded) == 0:
                return "Error: Model returned empty output"
            
            text = decoded[0]
            # Remove the prompt from the output if it's included
            if prompt in text:
                text = text.split(prompt, 1)[-1].strip()
            
            return text
        
        except Exception as e:
            return f"Error analyzing image: {str(e)}"
