import torch
from typing import Dict, Any
from PIL import Image
from transformers import AutoProcessor, AutoModelForCausalLM

class VisionTool:
    def __init__(self, state, model_id: str = "Qwen/Qwen2-VL-2B-Instruct"):
        self.state = state
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.processor = AutoProcessor.from_pretrained(model_id, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            load_in_4bit=True if self.device == "cuda" else False,
            device_map="auto",
            trust_remote_code=True
        )

    @staticmethod
    def spec():
        return {
            "name": "vision",
            "description": "Describe an image (e.g., a screenshot) or read text from it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "prompt": {"type": "string"}
                },
                "required": ["path"]
            }
        }

    async def run(self, path: str, prompt: str = "Describe the image briefly with actionable details.") -> Dict[str, Any]:
        image = Image.open(path).convert("RGB")
        inputs = self.processor(text=prompt, images=image, return_tensors="pt").to(self.device)
        with torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=256)
        text = self.processor.batch_decode(out, skip_special_tokens=True)[0]
        text = text.split(prompt, 1)[-1].strip() if prompt in text else text
        summary = f"Vision: {text[:800]}"
        delta = {"last_observation": summary}
        return {"summary": summary, "delta": delta}