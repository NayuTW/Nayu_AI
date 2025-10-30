import asyncio
import os
import time
from typing import Any, Dict

from src.agents.state import SharedState
from src.agents.llm.ollama_client import OllamaLLM
from src.agents.core.events import EventBus
from src.agents.core.registry import ToolRegistry
from src.agents.notify.notifier import Notifier
from src.agents.core.store import SQLiteStore

from src.agents.tools.webbrowser import WebBrowserTool
from src.agents.tools.desktop import DesktopTool
from src.agents.tools.vision import VisionTool
from src.agents.tools.memory import MemoryTool
from src.agents.tools.speech import SpeechTool
from src.agents.tools.codeagent import CodeAgentTool

SYSTEM_PROMPT_BASE = """You are a helpful, friendly AI assistant. Your primary role is to chat naturally with users and help them with their requests.

CORE BEHAVIOR:
- Be conversational, warm, and personable
- Respond naturally to greetings, questions, and casual conversation
- Only use tools when the user's request specifically requires them
- Think: "Can I answer this directly, or do I need a tool?"

IMPORTANT: When responding to users, speak naturally and conversationally. Do NOT:
- Echo or mention internal details like "Last observation", "Memory digest", "Shared state"
- Mention tool execution details or system context in your responses
- Generate code examples, tests, or technical documentation unless explicitly requested
- These internal details are for your awareness only - users should not see them

Remember: Be helpful and conversational first. Use tools as needed, not by default."""

SYSTEM_PROMPT_WITH_TOOLS = """You are a helpful, friendly AI assistant. Your primary role is to chat naturally with users and help them with their requests.

RESPONSE FORMAT - You MUST respond using ONLY valid JSON in one of these formats:
1. For normal conversation (greetings, questions, general chat): {"text": "your conversational response"}
2. For using a tool (ONLY when truly needed): {"tool_call": {"name": "tool_name", "arguments": {...}}}

CRITICAL RULES:
- DEFAULT to conversation: For "Hello", "How are you", questions, etc. → use {"text": "..."}
- Use tools ONLY for specific tasks that require them (web search, code execution, memory operations)
- Output ONLY the JSON - no other text before or after
- Do NOT generate code, tests, examples, or documentation in your {"text": "..."} responses
- Be warm and conversational in your {"text": "..."} responses

WHEN TO USE EACH FORMAT:
- User: "Hello" → {"text": "Hello! How can I help you today?"}
- User: "What's the weather?" → {"text": "I don't have real-time weather data, but I can search the web if you'd like!"}
- User: "Search for Python tutorials" → {"tool_call": {"name": "webbrowser", "arguments": {"action": "search", "query": "Python tutorials"}}}

TOOL USAGE:
When calling tools, include all required parameters:
- 'speech' tool: MUST include 'action' field set to 'speak' (with 'text') or 'transcribe' (with 'path')
- 'webbrowser' tool: use actions: 'search' (web search), 'fetch' (extract URL), 'browse' (multi-source research), 'goto' (navigate), or 'interact' (automation)

IMPORTANT: Do NOT mention internal details like "Last observation", "Memory digest", "Shared state" in responses."""

class MainAgent:
    def __init__(self, state: SharedState, bus: EventBus, registry: ToolRegistry, notifier: Notifier, store: SQLiteStore, session_id: str):
        self.state = state
        self.bus = bus
        self.registry = registry
        self.notifier = notifier
        self.store = store
        self.session_id = session_id
        
        # Allow model to be configured via environment variable
        model_name = os.getenv("AGENT_MODEL", "llama3.1:8b-instruct-q4_K_M")
        self.llm = OllamaLLM(model=model_name, json_mode=True, num_ctx=12000)

        webbrowser = WebBrowserTool(state)
        desktop = DesktopTool(state)
        vision = VisionTool(state)
        memory = MemoryTool(state)
        speech = SpeechTool(state)
        codeexec = CodeAgentTool(state)

        self.registry.register("webbrowser", webbrowser, WebBrowserTool.spec())
        self.registry.register("desktop", desktop, DesktopTool.spec())
        self.registry.register("vision", vision, VisionTool.spec())
        self.registry.register("memory", memory, MemoryTool.spec())
        self.registry.register("speech", speech, SpeechTool.spec())
        self.registry.register("codeexec", codeexec, CodeAgentTool.spec())

    def tool_specs(self):
        specs = []
        for name, rt in self.registry._tools.items():
            if rt.stats.enabled:
                specs.append(rt.spec)
        return specs

    async def handle_user_message(self, user_text: str) -> str:
        mem_tool = self.registry.get("memory").impl
        mem_digest = await mem_tool.digest_for_context(user_text)
        context = self.state.build_context(mem_digest)
        
        # Use the appropriate system prompt based on tool availability
        tool_specs = self.tool_specs()
        system_prompt = SYSTEM_PROMPT_WITH_TOOLS if tool_specs else SYSTEM_PROMPT_BASE

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"Shared state summary:\n{context}"},
            {"role": "user", "content": user_text},
        ]

        await self.bus.publish("agent.input", {"text": user_text})
        out = await self.llm.chat(messages, tools=tool_specs)

        async def _persist_example(final_text: str):
            meta = {
                "memory_digest": mem_digest,
                "tools_enabled": [name for name, rt in self.registry._tools.items() if rt.stats.enabled],
            }
            ex_id = self.store.append_example(
                session_id=self.session_id,
                user_text=user_text,
                assistant_text=final_text or "",
                meta=meta,
            )
            await self.bus.publish("dataset.example", {"id": ex_id, "label": "unlabeled"})
            return ex_id

        if out.get("tool_call"):
            tool_name = out["tool_call"]["name"]
            args = out["tool_call"].get("arguments", {})

            rt = self.registry.get(tool_name)
            if not rt:
                msg = f"Tool {tool_name} not found."
                await self.bus.publish("tool.error", {"name": tool_name, "error": msg})
                if self.notifier.speak_on_error:
                    await self.notifier.alert("There is a problem with my AI.")
                await _persist_example(msg)
                return msg

            if not rt.stats.enabled:
                msg = f"Tool {tool_name} is disabled."
                await self.bus.publish("tool.disabled", {"name": tool_name})
                await _persist_example(msg)
                return msg

            await self.bus.publish("tool.start", {"name": tool_name, "args": args})
            t0 = time.time()
            try:
                result = await asyncio.wait_for(rt.impl.run(**args), timeout=90)
                latency_ms = (time.time() - t0) * 1000
                self.registry.record_success(tool_name, latency_ms)
                await self.bus.publish("tool.success", {"name": tool_name, "latency_ms": latency_ms, "summary": result.get("summary", "")})

                self.state.merge_delta(result.get("delta", {}))
                await mem_tool.update_working_memo(self.state)

                follow = [
                    {"role": "system", "content": "Tool result (summarized) provided below."},
                    {"role": "tool", "content": result.get("summary", "")},
                ]
                final = await self.llm.chat(messages + follow, tools=[])
                final_text = final.get("text", "")
                await self.bus.publish("agent.output", {"text": final_text})
                await _persist_example(final_text)
                return final_text
            except asyncio.TimeoutError:
                self.registry.record_failure(tool_name, "timeout")
                await self.bus.publish("tool.error", {"name": tool_name, "error": "timeout"})
                if self.notifier.speak_on_error:
                    await self.notifier.alert("There is a problem with my AI.")
                msg = f"{tool_name} timed out. I can try another approach."
                await _persist_example(msg)
                return msg
            except Exception as e:
                self.registry.record_failure(tool_name, str(e))
                await self.bus.publish("tool.error", {"name": tool_name, "error": str(e)})
                if self.notifier.speak_on_error:
                    await self.notifier.alert("There is a problem with my AI.")
                msg = f"{tool_name} failed: {e}"
                await _persist_example(msg)
                return msg
        else:
            text = out.get("text", "")
            await self.bus.publish("agent.output", {"text": text})
            await _persist_example(text)
            return text
