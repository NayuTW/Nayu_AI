import io
import textwrap
import time
from multiprocessing import Process, Queue
from typing import Any, Dict, List, Optional
import sys

from smolagents import CodeAgent, Tool

from src.agents.llm.smol_ollama_model import SmolOllamaModel
from src.agents.tools.md_browser import MarkdownBrowserTool
from src.agents.sandbox.guardrails import GuardedEnv

class GetUrlTool(Tool):
    name = "get_url"
    description = "Fetch the HTML of a URL and return text. Prefer using md_browser.fetch/browse for content extraction."
    inputs = {"url": {"type": "string", "description": "URL to fetch"}}
    outputs = {"text": {"type": "string", "description": "Raw HTML text (truncated)"}}
    output_type = "string"

    def forward(self, url: str) -> Dict[str, str]:
        import requests
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}
        r = requests.get(url, headers=headers, timeout=20)
        r.raise_for_status()
        txt = r.text
        return {"text": txt[:100000]}

class WriteFileTool(Tool):
    name = "write_file"
    description = "Write content to a file within the ./workspace directory."
    inputs = {"path": {"type": "string", "description": "path of the file that will be written to"}, "content": {"type": "string", "description": "content that will be written to the file"}}
    outputs = {"path": {"type": "string"}}
    output_type = "string"

    def forward(self, path: str, content: str) -> Dict[str, str]:
        import os
        safe_root = "./workspace"
        os.makedirs(safe_root, exist_ok=True)
        full = os.path.abspath(os.path.join(safe_root, path))
        assert full.startswith(os.path.abspath(safe_root)), "Path outside workspace"
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)
        return {"path": full}

class CodeAgentTool:
    """
    smolagents CodeAgent wrapper as a tool, with guardrails.
    """
    def __init__(
        self,
        state,
        allowed_tools: Optional[List[Tool]] = None,
        model: Optional[SmolOllamaModel] = None,
        max_steps: int = 12,
        system_prompt: Optional[str] = None,
        allowed_imports: Optional[List[str]] = None,
        allow_open_readonly: bool = False,
        open_read_roots: Optional[List[str]] = None,
        network_allowed_callers: Optional[List[str]] = None,
        step_limit: int = 4000,
        print_line_limit: int = 200,
        print_byte_limit: int = 200_000,
        cpu_time_s: Optional[int] = None,
        mem_limit_mb: Optional[int] = None,
    ):
        self.state = state
        self.model = model or SmolOllamaModel()
        self.allowed_tools = allowed_tools or [
            MarkdownBrowserTool(),
            GetUrlTool(),
            WriteFileTool(),
        ]
        sys_prompt = system_prompt or textwrap.dedent("""
            You are a focused Python agent that solves the user's GOAL using the provided tools.
            Prefer md_browser for web research and return concise summaries with citations.
            Keep loops short. End by printing a brief final summary.
        """)
        self.agent = CodeAgent(
            tools=self.allowed_tools,
            model=self.model,
            max_steps=max_steps,
        )
        self.guard_allowed_imports = set(allowed_imports or [
            "math","re","json","time","datetime","statistics","itertools","functools","collections","typing","hashlib","base64","html","urllib",
            "requests","bs4","duckduckgo_search","readability","html2text","selenium","lxml",
        ])
        self.guard_allow_open_readonly = allow_open_readonly
        self.guard_open_read_roots = open_read_roots or ["./workspace"]
        self.guard_network_allowed_callers = network_allowed_callers or ["agents.tools.md_browser"]
        self.guard_step_limit = step_limit
        self.guard_print_line_limit = print_line_limit
        self.guard_print_byte_limit = print_byte_limit
        self.guard_cpu_time_s = cpu_time_s
        self.guard_mem_limit_mb = mem_limit_mb

    @staticmethod
    def spec():
        return {
            "name": "codeexec",
            "description": "Run a focused Python automation/program using a CodeAgent (guardrails enforced).",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {"type": "string"},
                    "hints": {"type": "string"},
                    "timeout_s": {"type": "number", "default": 60},
                },
                "required": ["goal"],
            },
        }

    async def run(self, goal: str, hints: str = "", timeout_s: int = 60) -> Dict[str, Any]:
        q: Queue = Queue()

        def _worker(prompt: str, hints_: str, q_: Queue):
            with GuardedEnv(
                allowed_imports=sorted(self.guard_allowed_imports),
                allow_open_readonly=self.guard_allow_open_readonly,
                open_read_roots=self.guard_open_read_roots,
                network_allowed_callers=self.guard_network_allowed_callers,
                step_limit=self.guard_step_limit,
                print_line_limit=self.guard_print_line_limit,
                print_byte_limit=self.guard_print_byte_limit,
                cpu_time_s=self.guard_cpu_time_s,
                mem_limit_mb=self.guard_mem_limit_mb,
            ):
                try:
                    start = time.time()
                    final_prompt_body = prompt if not hints_ else f"{prompt}\n\nHints/Constraints:\n{hints_}"
                    final_prompt = (self.sys_prompt + "\n\n" + final_prompt_body) if self.sys_prompt else final_prompt_body
                    result = self.agent.run(final_prompt)
                    elapsed = time.time() - start
                    q_.put({"ok": True, "result": (result or "").strip(), "elapsed": elapsed})
                except Exception as e:
                    q_.put({"ok": False, "error": str(e)})

        p = Process(target=_worker, args=(goal, hints, q))
        p.start()
        p.join(timeout_s)
        if p.is_alive():
            p.kill()
            summary = f"CodeAgent timed out after {timeout_s}s for goal: {goal[:200]}"
            return {"summary": summary, "delta": {"last_observation": summary}}

        if q.empty():
            summary = "CodeAgent finished but produced no output."
            return {"summary": summary, "delta": {"last_observation": summary}}

        out = q.get()
        if not out.get("ok"):
            summary = f"CodeAgent error: {out.get('error', 'unknown error')}"
            return {"summary": summary, "delta": {"last_observation": summary}}

        result = out.get("result", "")
        elapsed = out.get("elapsed", 0.0)
        summary = f"CodeAgent completed in {elapsed:.1f}s. Result: {result[:600]}"
        delta = {"last_observation": f"CodeAgent: {result[:600]}"}
        return {"summary": summary, "delta": delta}
