"""
Discord tool for smolagents - sends messages to Discord channels or DMs.
This is a simple Tool that wraps the Discord service functionality.
"""
from typing import Any, Optional
from smolagents import Tool


class DiscordSmolTool(Tool):
    """
    Discord messaging tool for sending DMs and channel messages.
    Provides simple interface to Discord service functionality.
    """
    name = "discord"
    description = (
        "Send messages to Discord channels or direct messages. "
        "Use 'dm' action to send a direct message to a user, "
        "or 'channel' action to send a message to a channel. "
        "Specify target user/channel by name (e.g., '@username' or '#channel-name') or ID."
    )
    inputs = {
        "action": {
            "type": "string",
            "enum": ["dm", "channel"],
            "description": "Action: 'dm' for direct message or 'channel' for channel message"
        },
        "target": {
            "type": "string",
            "description": "Target user (for dm) or channel (for channel). Can be name like '@user' or '#channel', or numeric ID"
        },
        "message": {
            "type": "string",
            "description": "The message text to send"
        },
        "guild_id": {
            "type": "string",
            "description": "Optional guild ID for resolving user/channel names",
            "nullable": True
        }
    }
    output_type = "string"
    
    def __init__(self, discord_service: Any):
        """
        Initialize the Discord tool.
        
        Args:
            discord_service: The Discord bot service instance (DiscordBotService)
        """
        super().__init__()
        self.discord_service = discord_service
    
    def forward(
        self,
        action: str,
        target: str,
        message: str,
        guild_id: Optional[str] = None
    ) -> str:
        """
        Send a Discord message.
        
        Args:
            action: 'dm' or 'channel'
            target: User or channel identifier
            message: Message content
            guild_id: Optional guild ID for name resolution
            
        Returns:
            Success/failure message
        """
        import asyncio
        
        try:
            # Convert guild_id to int if provided
            guild_id_int = int(guild_id) if guild_id else None
            
            # Get the event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Execute the send operation
            if action == "dm":
                # Send DM
                coro = self.discord_service.send_dm_target(
                    target=target,
                    content=message,
                    guild_id=guild_id_int
                )
                
                if loop.is_running():
                    # If loop is already running, create a task
                    future = asyncio.ensure_future(coro)
                    # Wait a bit for it to complete (non-blocking)
                    result = f"DM queued to {target}: {message[:50]}..."
                else:
                    # If loop is not running, run it
                    loop.run_until_complete(coro)
                    result = f"DM sent to {target}: {message[:50]}..."
                    
            elif action == "channel":
                # Send to channel
                coro = self.discord_service.send_channel_target(
                    target=target,
                    content=message,
                    guild_id=guild_id_int
                )
                
                if loop.is_running():
                    # If loop is already running, create a task
                    future = asyncio.ensure_future(coro)
                    # Wait a bit for it to complete (non-blocking)
                    result = f"Channel message queued to {target}: {message[:50]}..."
                else:
                    # If loop is not running, run it
                    loop.run_until_complete(coro)
                    result = f"Channel message sent to {target}: {message[:50]}..."
                    
            else:
                result = f"Error: Unknown action '{action}'. Use 'dm' or 'channel'"
            
            return result
            
        except ValueError as e:
            return f"Error: Could not resolve target '{target}': {str(e)}"
        except Exception as e:
            return f"Error sending Discord message: {str(e)}"
