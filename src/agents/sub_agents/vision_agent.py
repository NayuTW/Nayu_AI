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

    def _set_description(self) -> None:
        """Set description of agent"""
        self.agent_description = """This agent is specialized in tasks that require image analysis. It can analyze the live desktop screenshot kept in .cache/desktop.png as well as other provided images. Use this agent when you need to describe what is currently displayed on the screen or analyze any visual content."""
