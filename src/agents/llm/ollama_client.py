import asyncio
import json
import re
from typing import Optional
from string import Template
import aiohttp

# System prompt for tool-calling mode using Template to safely substitute tools
# This avoids KeyError when the prompt contains literal JSON braces like {"tool_call"}
TOOL_CALLING_PROMPT_TEMPLATE = Template("""You are a helpful AI assistant. You can chat naturally with users AND use tools when needed.

RESPONSE FORMAT:
You must respond with a valid JSON object using ONE of these two formats:

1. For normal conversation (when no tool is needed):
{"text": "Your natural, conversational response here"}

2. For using a tool (when the user's request requires specific capabilities):
{"tool_call": {"name": "tool_name", "arguments": {...}}}

WHEN TO USE TOOLS:
- Only use tools when the user explicitly asks for something that requires them (web search, code execution, memory lookup, etc.)
- For greetings, questions, or general chat, just respond with {"text": "..."}
- Think: Does this REQUIRE a tool, or can I just chat?

AVAILABLE TOOLS:
$tools

IMPORTANT:
- Output ONLY the JSON object, no other text before or after
- Do not write code examples, tests, or documentation unless explicitly asked
- Be conversational and friendly when just chatting
- Use tools only when necessary for the task

def format_tool_calling_prompt(tools: str) -> str:
    """
    Safely format the tool-calling prompt by substituting the tools string.
    Uses string.Template to avoid interpreting literal JSON braces as format placeholders.
    
    Args:
        tools: JSON string containing the tool specifications
        
    Returns:
        Formatted prompt string with tools injected
    """
    return TOOL_CALLING_PROMPT_TEMPLATE.substitute(tools=tools)

class OllamaLLM:
    def __init__(self, model: str, json_mode: bool = True, num_ctx: int = 8000, temperature: float = 0.2):
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
        tool_spec = tools or []
        tool_str = json.dumps(tool_spec) if tool_spec else None
        sys_aug = []
        if tool_str:
            sys_aug.append({"role": "system", "content": format_tool_calling_prompt(tool_str)})
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