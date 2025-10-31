import asyncio
import os
import time
import json
import re
from typing import Any, Dict, Optional

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
- You may receive messages from multiple channels (e.g., cli, discord). You can reference prior messages via memory.
- Do NOT claim you lack access to external platforms; messages are delivered to you by adapters.
- When using the memory tool to remember something, include useful metadata when available (e.g., {"tag": "<source>"}).

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
- NEVER print a tool call inside {"text": "..."}; if you intend to use a tool, return ONLY the {"tool_call": {...}} JSON.

WHEN TO USE EACH FORMAT:
- User: "Hello" → {"text": "Hello! How can I help you today?"}
- User: "What's the weather?" → {"text": "I don't have real-time weather data, but I can search the web if you'd like!"}
- User: "Search for Python tutorials" → {"tool_call": {"name": "webbrowser", "arguments": {"action": "search", "query": "Python tutorials"}}}

TOOL USAGE:
When calling tools, include all required parameters:
- 'speech' tool: MUST include 'action' field set to 'speak' (with 'text') or 'transcribe' (with 'path')
- 'webbrowser' tool: use actions: 'search' (web search), 'fetch' (extract URL), 'browse' (multi-source research), 'goto' (navigate), or 'interact' (automation)
- 'memory' tool: Include useful metadata when available (e.g., {"tag": "<source>"})

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
        self.llm = OllamaLLM(model=model_name, json_mode=True, num_ctx=24576)

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

    @staticmethod
    def _extract_tool_call_from_text(text: str) -> Optional[Dict[str, Any]]:
        """
        If the model mistakenly printed a tool_call blob inside normal text,
        try to extract and parse it. Supports:
        - Bare JSON: {"tool_call": {...}}
        - Wrapped in code fences ```json ... ```
        - Extra prose before/after
        Returns a dict like {"name": "...", "arguments": {...}} or None.
        """
        if not text:
            return None
        s = text.strip()

        # Strip common code fences
        fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, flags=re.DOTALL | re.IGNORECASE)
        if fence_match:
            s = fence_match.group(1).strip()

        # Try direct parse
        def try_parse(candidate: str) -> Optional[Dict[str, Any]]:
            try:
                obj = json.loads(candidate)
                if isinstance(obj, dict) and "tool_call" in obj and isinstance(obj["tool_call"], dict):
                    name = obj["tool_call"].get("name")
                    args = obj["tool_call"].get("arguments", {})
                    if isinstance(name, str) and isinstance(args, dict):
                        return {"name": name, "arguments": args}
            except Exception:
                pass
            return None

        tc = try_parse(s)
        if tc:
            return tc

        # Locate a JSON object containing "tool_call"
        if "tool_call" in s:
            idx = s.find("tool_call")
            start = s.rfind("{", 0, idx)
            if start != -1:
                for end in range(len(s), start, -1):
                    candidate = s[start:end].strip()
                    tc = try_parse(candidate)
                    if tc:
                        return tc
        return None

    async def handle_user_message(
        self,
        user_text: str,
        source: str = "cli",
        external_metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
    ) -> str:
        mem_tool = self.registry.get("memory").impl
        mem_digest = await mem_tool.digest_for_context(user_text)
        context = self.state.build_context(mem_digest)
        
        # Use the appropriate system prompt based on tool availability
        tool_specs = self.tool_specs()
        system_prompt = SYSTEM_PROMPT_WITH_TOOLS if tool_specs else SYSTEM_PROMPT_BASE

        # Channel awareness for the model (not shown to the end user verbatim)
        channel_context = f"Message source: {source}"
        if user_id or channel_id:
            channel_context += f" (user_id={user_id or ''}, channel_id={channel_id or ''})"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"Shared state summary:\n{context}"},
            {"role": "system", "content": channel_context},
            {"role": "user", "content": user_text},
        ]

        await self.bus.publish("agent.input", {"text": user_text, "source": source, "meta": external_metadata or {}})
        out = await self.llm.chat(messages, tools=tool_specs)

        async def _persist_example(final_text: str):
            meta = {
                "memory_digest": mem_digest,
                "tools_enabled": [name for name, rt in self.registry._tools.items() if rt.stats.enabled],
                "source": source,
                "user_id": user_id,
                "channel_id": channel_id,
            }
            ex_id = self.store.append_example(
                session_id=self.session_id,
                user_text=user_text,
                assistant_text=final_text or "",
                meta=meta,
            )
            await self.bus.publish("dataset.example", {"id": ex_id, "label": "unlabeled"})
            return ex_id

        # Helper: enrich metadata for memory tool calls
        def _enrich_memory_metadata(md: Optional[Dict[str, Any]]) -> Dict[str, Any]:
            enriched = dict(md or {})
            if external_metadata:
                for k, v in external_metadata.items():
                    if v is not None and k not in enriched:
                        enriched[k] = v
            if "tag" not in enriched:
                enriched["tag"] = source
            if user_id and "user_id" not in enriched:
                enriched["user_id"] = user_id
            if channel_id and "channel_id" not in enriched:
                enriched["channel_id"] = channel_id
            return enriched

        # Heuristic fallback for memory operations when the LLM outputs empty text or doesn't tool-call
        async def _memory_fallback_if_needed(empty_text: bool) -> Optional[str]:
            lt = (user_text or "").lower()
            try:
                # Try "remember" shortcuts
                if ("remember" in lt and ("remember this" in lt or lt.startswith("remember") or "please remember" in lt or "i want you to remember" in lt)) or lt.strip() == "remember":
                    md = _enrich_memory_metadata({})
                    await self.bus.publish("tool.start", {"name": "memory", "args": {"action": "remember"}})
                    res = await mem_tool.run(action="remember", text=user_text, metadata=md)
                    await self.bus.publish("tool.success", {"name": "memory", "latency_ms": 0, "summary": res.get("summary", "")})
                    self.state.merge_delta(res.get("delta", {}))
                    await mem_tool.update_working_memo(self.state)
                    return "Got it — I’ll remember that."

                # Try "recall" shortcuts
                if ("recall" in lt) or ("do you remember" in lt) or ("what did i say" in lt) or ("what was the message" in lt):
                    await self.bus.publish("tool.start", {"name": "memory", "args": {"action": "recall"}})
                    res = await mem_tool.run(action="recall", text=user_text, k=3)
                    await self.bus.publish("tool.success", {"name": "memory", "latency_ms": 0, "summary": res.get("summary", "")})
                    self.state.merge_delta(res.get("delta", {}))
                    await mem_tool.update_working_memo(self.state)
                    digest = (res.get("delta", {}) or {}).get("memory_digest", "").strip()
                    if digest:
                        first = digest.split(" | ")[0]
                        return f"Here’s what I recall: {first}"
                    else:
                        return "I couldn’t find anything yet. Could you restate it so I can remember?"
            except Exception as e:
                # Surface a friendly error if the heuristic fallback failed
                await self.bus.publish("tool.error", {"name": "memory", "error": str(e)})
                if empty_text:
                    return "Sorry — something went wrong handling memory. Please try again."
            return None

        # Repair: if the model printed a tool_call inside text, extract and use it
        if not out.get("tool_call"):
            raw_text0 = (out.get("text", "") or "").strip()
            tc = self._extract_tool_call_from_text(raw_text0)
            if tc:
                out = {"tool_call": tc}

        if out.get("tool_call"):
            tool_name = out["tool_call"]["name"]
            args = out["tool_call"].get("arguments", {}) or {}

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

            # Enrich memory remember with non-empty metadata and source/user/channel context
            if tool_name == "memory" and (args.get("action") == "remember"):
                args["metadata"] = _enrich_memory_metadata(args.get("metadata"))

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
                final_text = (final.get("text", "") or "").strip()
                if not final_text:
                    # Fallback to tool summary if model produced an empty reply
                    final_text = result.get("summary", "") or "Done."
                await self.bus.publish("agent.output", {"text": final_text})
                await _persist_example(final_text)
                return final_text
            except asyncio.TimeoutError:
                self.registry.record_failure(tool_name, "timeout")
                await self.bus.publish("tool.error", {"name": "tool_name", "error": "timeout"})
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
            text = (out.get("text", "") or "").strip()
            if not text:
                # Heuristic fallback for empty model output, e.g., remember/recall requests
                fb = await self._memory_fallback_if_needed  # type: ignore  # prevent linter errors if IDE caches
                fb = await _memory_fallback_if_needed(empty_text=True)
                if fb:
                    await self.bus.publish("agent.output", {"text": fb})
                    await _persist_example(fb)
                    return fb
                # Generic fallback
                text = "Sorry — I didn’t catch that. Could you rephrase?"
            await self.bus.publish("agent.output", {"text": text})
            await _persist_example(text)
            return text

    async def handle_external_message(
        self,
        text: str,
        user_id: str,
        channel_id: str,
        source: str,
        metadata: Dict[str, Any],
    ) -> Optional[str]:
        """
        Entry point for external adapters (Discord, etc.).
        - Log/emit an event
        - Persist to store/memory if desired
        - Run orchestration and return a reply string (or None to skip replying)
        
        This method reuses the existing handle_user_message logic to ensure
        consistent behavior across all input sources (CLI, Discord, etc.).
        """
        # Publish event about the external message
        await self.bus.publish("message.received", {
            "source": source,
            "user_id": user_id,
            "channel_id": channel_id,
            "text": text,
            "metadata": metadata,
        })

        try:
            # Forward the raw text along with channel/source context
            reply = await self.handle_user_message(
                user_text=text,
                source=source,
                external_metadata=metadata or {},
                user_id=user_id,
                channel_id=channel_id,
            )
            return reply
        except Exception as e:
            # Log the error and return a friendly error message
            await self.bus.publish("agent.error", {
                "source": source,
                "user_id": user_id,
                "error": str(e),
            })
            return "Sorry, I encountered an error processing your message."
