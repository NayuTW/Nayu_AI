import asyncio
import json
import re
import aiohttp

class OllamaLLM:
    def __init__(self, model: str, json_mode: bool = True, num_ctx: int = 8000, temperature: float = 0.2):
        self.model = model
        self.json_mode = json_mode
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.url = "http://localhost:11434/api/chat"

    def _extract_json(self, content: str):
        """
        Extract JSON from model output, handling cases where the model includes
        explanatory text before/after the JSON structure.
        """
        # First, try parsing the entire content as JSON
        try:
            parsed = json.loads(content)
            return parsed
        except Exception:
            pass
        
        # If that fails, try to find a JSON object in the content
        # Look for patterns like {"tool_call": ...} or {"text": ...}
        # Match the outermost JSON object
        json_pattern = r'\{(?:[^{}]|(?:\{(?:[^{}]|(?:\{[^{}]*\}))*\}))*\}'
        matches = re.finditer(json_pattern, content, re.DOTALL)
        
        for match in matches:
            try:
                candidate = match.group(0)
                parsed = json.loads(candidate)
                # Check if it's a valid response (has either tool_call or text)
                if "tool_call" in parsed or "text" in parsed:
                    return parsed
            except Exception:
                continue
        
        # If no valid JSON found, return the content as text
        return {"text": content}

    async def chat(self, messages, tools=None):
        tool_spec = tools or []
        tool_str = json.dumps(tool_spec) if tool_spec else None
        sys_aug = []
        if tool_str:
            sys_aug.append({"role": "system", "content": f"You must respond with ONLY a valid JSON object, nothing else. Do not include any explanatory text before or after the JSON.\n\nTo call a tool, respond with: {{\"tool_call\": {{\"name\": \"tool_name\", \"arguments\": {{...}}}}}}\nTo reply without a tool, respond with: {{\"text\": \"your response\"}}\n\nAvailable tools (JSON Schemas):\n{tool_str}\n\nRemember: Output ONLY the JSON object, no additional text."})
        payload = {
            "model": self.model,
            "messages": sys_aug + messages,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
            "stream": False,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, json=payload, timeout=0) as resp:
                data = await resp.json()
        content = data.get("message", {}).get("content", "")
        return self._extract_json(content)