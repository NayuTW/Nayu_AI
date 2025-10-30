import asyncio
import json
import re
from typing import Optional
import aiohttp

class OllamaLLM:
    def __init__(self, model: str, json_mode: bool = True, num_ctx: int = 8192, temperature: float = 0.8):
        self.model = model
        self.json_mode = json_mode
        self.num_ctx = num_ctx
        self.temperature = temperature
        self.url = "http://localhost:11434/api/chat"

    def _find_json_object(self, content: str, start_pos: int) -> Optional[str]:
        """
        Find a complete JSON object starting at the given position by counting braces.
        Returns the JSON string if valid, None otherwise.
        """
        if start_pos >= len(content) or content[start_pos] != '{':
            return None
        
        brace_count = 0
        in_string = False
        escape_next = False
        
        for i in range(start_pos, len(content)):
            char = content[i]
            
            if escape_next:
                escape_next = False
                continue
            
            if char == '\\':
                escape_next = True
                continue
            
            if char == '"':
                in_string = not in_string
                continue
            
            if not in_string:
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        # Found complete JSON object
                        return content[start_pos:i+1]
        
        return None

    def _extract_json(self, content: str) -> dict:
        """
        Extract JSON from model output, handling cases where the model includes
        explanatory text before/after the JSON structure.
        Uses brace counting to properly handle nested JSON of any depth.
        """
        # First, try parsing the entire content as JSON
        try:
            parsed = json.loads(content)
            return parsed
        except Exception:
            pass
        
        # If that fails, search for JSON objects in the content
        # Look for opening braces and try to extract complete JSON from there
        for i, char in enumerate(content):
            if char == '{':
                json_str = self._find_json_object(content, i)
                if json_str:
                    try:
                        parsed = json.loads(json_str)
                        # Check if it's a valid response (has either tool_call or text)
                        if "tool_call" in parsed or "text" in parsed:
                            return parsed
                    except Exception:
                        continue
        
        # If no valid JSON found, return the content as text
        return {"text": content}

    async def chat(self, messages, tools=None):
        # If tools are provided, append them to the first system message instead of creating a new one
        # This avoids conflicting system prompts
        tool_spec = tools or []
        if tool_spec:
            tool_str = json.dumps(tool_spec, indent=2)
            # Find the first system message and append tool info to it
            modified_messages = []
            tool_info_added = False
            for msg in messages:
                if msg["role"] == "system" and not tool_info_added:
                    # Append tool specifications to the first system message
                    modified_content = msg["content"] + f"\n\nAVAILABLE TOOLS (JSON schemas):\n{tool_str}"
                    modified_messages.append({"role": "system", "content": modified_content})
                    tool_info_added = True
                else:
                    modified_messages.append(msg)
            messages = modified_messages
        
        payload = {
            "model": self.model,
            "messages": messages,
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx},
            "stream": False,
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(self.url, json=payload, timeout=0) as resp:
                data = await resp.json()
        content = data.get("message", {}).get("content", "")
        return self._extract_json(content)
