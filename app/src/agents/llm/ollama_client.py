import asyncio
import json
import aiohttp

class OllamaLLM:
    def __init__(self, model: str, json_mode: bool = True, num_ctx: int = 8000, temperature: float = 0.2):
        self.model = model
        self.json_mode = json_mode
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.url = "http://localhost:11434/api/chat"

    async def chat(self, messages, tools=None):
        tool_spec = tools or []
        tool_str = json.dumps(tool_spec) if tool_spec else None
        sys_aug = []
        if tool_str:
            sys_aug.append({"role": "system", "content": f"You can call tools by responding with a JSON object {{\"tool_call\": {{\"name\": \"...\", \"arguments\": {{...}}}}}} that strictly follows these JSON Schemas:\n{tool_str}\nIf not calling a tool, reply with {{\"text\": \"...\"}}."})
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
        try:
            parsed = json.loads(content)
            return parsed
        except Exception:
            return {"text": content}