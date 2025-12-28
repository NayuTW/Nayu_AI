import asyncio
import inspect
import os
import time
from typing import Any, Optional

from smolagents import CodeAgent, RunResult

from src.agents.llm.litellm_model import OllamaLiteLLMModel

from src.agents.base_agent import BaseAgent, SYSTEM_PROMPT, ToolEmbedder

# Import Vision Tools
from src.agents.tools.vision_smol import VisionSmolTool
from src.agents.tools.active_browser import (
    search_item_ctrl_f,
    go_back,
    close_popups,
    save_screenshot,
    start_browser,
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
            vision = VisionSmolTool()
            self.add_tool(vision)
            self.registry.register("vision", vision, {
                "name": vision.name,
                "description": vision.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize vision tool: {e}")

        try:
            search_item_tool = search_item_ctrl_f
            self.add_tool(search_item_tool)
            self.registry.register("search_item_ctrl_f", search_item_tool, {
                "name": search_item_tool.name,
                "description": search_item_tool.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize search item tool: {e}")

        try:
             start_browser_tool = start_browser
             self.add_tool(start_browser_tool)
             self.registry.register("start_browser", start_browser_tool, {
                    "name": start_browser_tool.name,
                    "description": start_browser.description
                })
        except Exception as e:
            print(f"Warning: Could not initialize active browser tool: {e}")

        try:
            go_back_tool = go_back
            self.add_tool(go_back_tool)
            self.registry.register("go_back", go_back_tool, {
                "name": go_back_tool.name,
                "description": go_back_tool.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize go back tool: {e}")

        try:
            close_popups_tool = close_popups
            self.add_tool(close_popups_tool)
            self.registry.register("close_popups", close_popups_tool, {
                "name": close_popups_tool.name,
                "description": close_popups_tool.description
            })
        except Exception as e:
            print(f"Warning: Could not initialize close popups tool: {e}")

    def _rebuild_code_agent(self) -> None:tr

# Initialize Vision Agent
vision_agent = CodeAgent(
    tools=[
        VisionSmolTool(),
        start_browser,
        go_back,
        close_popups,
        search_item_ctrl_f
        ],
    model=model,
    max_steps=20,
    additional_authorized_imports=["helium"],
    step_callbacks=[save_screenshot],
    verbosity_level=2,
)