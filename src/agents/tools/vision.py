import torch
from typing import Dict, Any
from PIL import Image
from transformers import AutoProcessor, AutoModelForImageTextToText

class VisionTool:
    def __init__(self, state, model_id: str = "Qwen/Qwen2-VL-2B-Instruct"):
        self.state = state
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        self.model = AutoModelForImageTextToText.from_pretrained(
            model_id,
            dtype=torch.float16 if self.device == "cuda" else torch.float32,
            load_in_4bit=True if self.device == "cuda" else False,
            device_map="auto",
            trust_remote_code=True
        )

    @staticmethod
    def spec():
        return {
            "name": "vision",
            "description": "Describe an image (e.g., a screenshot) or read text from it. Requires the full path to the image file. After taking a screenshot with desktop tool, use the returned path or check state.extra['last_screenshot_path'].",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Full path to the image file (e.g., '.cache/screenshot_1234567890.png')"},
                    "prompt": {"type": "string", "description": "Custom prompt for image analysis (optional)"}
                },
                "required": ["path"]
            }
        }

    async def run(self, path: str, prompt: str = "Describe the image briefly with actionable details.") -> Dict[str, Any]:
        # Validate path parameter
        if not path or not path.strip():
            raise ValueError("path parameter is required and cannot be empty")
        
        # Check if file exists
        import os
        if not os.path.exists(path):
            raise FileNotFoundError(f"Image file not found: {path}")
        
        image = Image.open(path).convert("RGB")
        
        # Use the correct Qwen2-VL chat template format
        # The model expects messages with image and text content properly structured
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt}
                ]
            }
        ]
        
        # Apply chat template to format the conversation correctly
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        
        # Process with the formatted text and image
        inputs = self.processor(text=[text], images=[image], return_tensors="pt").to(self.device)
        
        with torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=256)
        
        # Safe decoding with validation
        decoded = self.processor.batch_decode(out, skip_special_tokens=True)
        if not decoded or len(decoded) == 0:
            text = "Unable to process image - model returned empty output"
        else:
            text = decoded[0]
            text = text.split(prompt, 1)[-1].strip() if prompt in text else text
        
        summary = f"Vision: {text[:800]}"
        delta = {"last_observation": summary}
        return {"summary": summary, "delta": delta}
