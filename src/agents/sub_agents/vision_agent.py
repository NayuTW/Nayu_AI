import asyncio
import inspect
import os
import time
from typing import Any, Optional

from smolagents import CodeAgent, RunResult

from src.agents.llm.litellm_model import OllamaLiteLLMModel

from src.agents.notify.notifier import Notifier
from src.agents.state import SharedState
from src.agents.core.events import EventBus
from src.agents.core.registry import ToolRegistry
from src.agents.core.store import SQLiteStore
from src.agents.base_agent import BaseAgent, SYSTEM_PROMPT, ToolEmbedder

# Import Vision Tools
from src.agents.tools.vision_smol import VisionSmolTool
from src.agents.tools.active_browser import (
    search_item_ctrl_f,
    go_back,
    close_popups,
    start_browser,
    scroll_down,
    scroll_up,
    click_element,
    click_link,
    get_current_url,
    init_browser_tools,
    go_to_url,
    HELIUM_INSTRUCTIONS
)

class VisionAgent(BaseAgent):
    """
    Vision Agent using smolagents CodeAgent with Vision Tool and Browser Tools.
    Capable of analyzing images and interacting with web pages.
    """
    def __init__(
            self,
            state: SharedState,
            bus: EventBus,
            registry: ToolRegistry,
            notifier: Notifier,
            store: SQLiteStore,
            session_id: str,
        ):
            super().__init__(state, bus, registry, notifier, store, session_id)

            # Initialize LLM Model for Ollama
            model_name = os.getenv("VISION_AGENT_MODEL", "gemma3:12b-it-q4_K_M")
            num_ctx = int(os.getenv("VISION_AGENT_NUM_CTX", "8192"))

            self.model = OllamaLiteLLMModel(
                model_id=model_name,
                num_ctx=num_ctx,
                temperature=0.8
            )
            # Initialize tools (calls parent's add_tool internally)
            self._init_tools()
            
            # Initialize CodeAgent with current tools
            self._rebuild_code_agent()
            
            # Register callback for ActionStep tracking
            self._register_action_step_callback()

    def _init_tools(self) -> None:
        """Initialize all smolagents-compatible tools."""
        try:
            # Pass self as agent to allow vision tool to use the same model
            vision = VisionSmolTool(agent=self)
            self.add_tool(vision)
            self.registry.register("vision", vision, {
                "name": vision.name,
                "description": vision.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize vision tool: {e}")
        
        # Add all active browser tools
        browser_tools = [
            start_browser,
            go_to_url,
            click_element,
            click_link,
            search_item_ctrl_f,
            scroll_down,
            scroll_up,
            go_back,
            close_popups,
            get_current_url
        ]
        
        for tool_func in browser_tools:
            try:
                self.add_tool(tool_func)
                self.registry.register(tool_func.name, tool_func, {
                    "name": tool_func.name,
                    "description": tool_func.description
                })
            except Exception as e:
                print(f"Warning: Could not initialize {getattr(tool_func, 'name', 'unknown')} tool: {e}")
        
        # Initialize browser tools with reference to this agent
        init_browser_tools(self)

    def _set_description(self) -> None:
        """Set description of agent"""
        self.agent_description = f"""VisionAgent is specialized in image analysis and interactive web browsing. When delegated a task, you should:

## How to Use This Agent

Callers should provide SPECIFIC, CLEAR TASK DESCRIPTIONS that explain exactly what you need to do. Don't wait for vague requests - ask clarifying questions if needed.

Examples of good task descriptions:
- "Navigate to GitHub, search for 'awesome-python', and list the top 5 repositories"
- "Go to weather.com, find the current temperature in New York, and report it back"
- "Take a screenshot of the desktop, analyze what's visible, and describe any error messages"

## Capabilities

1. **Image Analysis**: 
   - Analyze the live desktop screenshot at .cache/desktop.png
   - Describe visual content, identify UI elements, perform OCR
   - Extract information from screenshots

2. **Interactive Web Browsing**:
   - Navigate to websites and interact with them
   - Click buttons and links by their visible text
   - Search for text on pages and jump to occurrences
   - Scroll, go back, and close pop-ups
   - Extract and report information from web pages

## Available Browser Tools

- start_browser(): Open Chrome for web browsing
- go_to_url(url): Navigate to a website (e.g., "https://github.com")
- click_element(text): Click buttons/elements by visible text
- click_link(text): Click links by their text
- search_item_ctrl_f(text): Find and focus on text on the current page
- scroll_down(num_pixels): Scroll down (default 1200 = one viewport)
- scroll_up(num_pixels): Scroll up (default 1200 = one viewport)
- go_back(): Navigate to previous page
- close_popups(): Close modal windows/pop-ups
- get_current_url(): Check the current page URL

## Important Notes

- **Desktop Screenshot**: Automatically updates every 2 seconds and instantly after actions
- **Always describe what you're doing**: Use vision analysis after each action to verify success
- **Be specific with clicks**: Use search_item_ctrl_f first to locate elements if clicking fails
- **No logins**: Cannot perform authentication/login workflows for security
- **One task at a time**: Complete the current task before asking for the next

## How MainAgent Should Delegate Tasks

When MainAgent delegates to you, it MUST provide a clear task description:

GOOD: `vision_agent(task="Navigate to GitHub trending, filter by Python, and describe the top repositories")`
GOOD: `vision_agent(task="Analyze the current desktop screenshot and report what windows are open")`
GOOD: `vision_agent(task="Search Wikipedia for 'Artificial Intelligence' and summarize the key points")`

BAD: `vision_agent(task="browse the web")`
BAD: `vision_agent(task="use the browser")`
BAD: `vision_agent(task="do something visual")`

{HELIUM_INSTRUCTIONS}

Use this agent when you need visual analysis, screen descriptions, OCR, or interactive web browsing with specific goals."""
