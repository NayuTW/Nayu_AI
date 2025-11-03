"""
DEPRECATED: Discord Agent Tool - A wrapper that uses ToolCallingAgent internally.

This implementation is deprecated due to causing duplicate tool calls and multiple final_answer issues.
The nested ToolCallingAgent architecture causes the inner agent to generate a final_answer,
which then becomes observations for the outer CodeAgent, causing it to generate another final_answer.

Use DiscordSmolTool instead (discord_tool_smol.py), which provides direct tool access without
the nested agent architecture.

This file is kept for reference only and should not be used in production.
"""
from typing import Optional, Any
from smolagents import Tool, ToolCallingAgent


class DiscordAgentTool(Tool):
    """
    A tool that wraps a ToolCallingAgent for Discord operations.
    This allows the main CodeAgent to delegate Discord tasks to a specialized agent.
    """
    name = "discord_agent"
    description = (
        "Send messages to Discord channels or direct messages. "
        "Specify the task in natural language, e.g., 'Send a DM to @username saying hello' "
        "or 'Post to #general channel about the update'."
    )
    inputs = {
        "task": {
            "type": "string",
            "description": "Natural language description of the Discord operation to perform"
        }
    }
    output_type = "string"
    
    def __init__(self, discord_service: Any, model: Any):
        """
        Initialize the Discord agent tool.
        
        DEPRECATED: Use DiscordSmolTool instead to avoid duplicate tool calls.
        
        Args:
            discord_service: The Discord bot service instance
            model: The LLM model to use for the ToolCallingAgent
        """
        import warnings
        warnings.warn(
            "DiscordAgentTool is deprecated and causes duplicate tool calls. "
            "Use DiscordSmolTool from discord_tool_smol.py instead.",
            DeprecationWarning,
            stacklevel=2
        )
        super().__init__()
        
        from src.agents.tools.discord_tool_smol import DiscordSmolTool
        
        # Create the Discord tool
        discord_tool = DiscordSmolTool(discord_service)
        
        # Create a ToolCallingAgent that will handle Discord operations
        self.discord_agent = ToolCallingAgent(
            tools=[discord_tool],
            model=model,
            max_steps=3,  # Discord operations are straightforward, don't need many steps
        )
    
    def forward(self, task: str) -> str:
        """
        Execute the Discord task using the internal ToolCallingAgent.
        
        Args:
            task: Natural language description of what to do
            
        Returns:
            str: Result of the Discord operation
        """
        try:
            # Run the task through the ToolCallingAgent
            result = self.discord_agent.run(task)
            
            # Extract the result text
            if isinstance(result, str):
                return result
            elif hasattr(result, 'content'):
                return result.content
            else:
                return str(result)
        except Exception as e:
            return f"Error executing Discord task: {str(e)}"
