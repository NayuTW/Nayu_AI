import asyncio
from typing import Dict, Any
from playwright.async_api import async_playwright

class WebTool:
    def __init__(self, state):
        self.state = state
        self.browser = None
        self.page = None

    @staticmethod
    def spec():
        return {
            "name": "web",
            "description": "Browse and interact with the web.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["goto", "click_text", "type", "read", "query"]},
                    "url": {"type": "string"},
                    "text": {"type": "string"},
                    "selector": {"type": "string"},
                    "input": {"type": "string"},
                },
                "required": ["action"]
            }
        }

    async def _ensure(self):
        if self.browser is None:
            pw = await async_playwright().start()
            self.browser = await pw.chromium.launch(headless=True)
            self.page = await self.browser.new_page()

    async def run(self, action: str, url: str = "", text: str = "", selector: str = "", input: str = "") -> Dict[str, Any]:
        await self._ensure()
        summary = ""
        if action == "goto" and url:
            await self.page.goto(url)
            content = await self.page.title()
            summary = f"Opened {url} title={content}"
        elif action == "click_text" and text:
            el = await self.page.get_by_text(text).first
            await el.click()
            summary = f"Clicked text: {text}"
        elif action == "type" and selector and input:
            await self.page.fill(selector, input)
            summary = f"Typed into {selector}"
        elif action == "read":
            content = await self.page.content()
            summary = f"Page content (truncated): {content[:1000]}"
        elif action == "query" and selector:
            txt = await self.page.inner_text(selector)
            summary = f"Selector {selector} text (truncated): {txt[:1000]}"
        else:
            summary = "Invalid web action/args."
        delta = {"last_observation": summary}
        return {"summary": summary, "delta": delta}