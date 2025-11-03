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
    
    # Timeout for Discord operations (seconds)
    TIMEOUT = 10.0
    
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
        import concurrent.futures
        
        try:
            # Convert guild_id to int if provided
            guild_id_int = int(guild_id) if guild_id else None
            
            # Build the coroutine based on action
            if action == "dm":
                coro = self.discord_service.send_dm_target(
                    target=target,
                    content=message,
                    guild_id=guild_id_int
                )
                action_desc = "DM"
            elif action == "channel":
                coro = self.discord_service.send_channel_target(
                    target=target,
                    content=message,
                    guild_id=guild_id_int
                )
                action_desc = "Channel message"
            else:
                return f"Error: Unknown action '{action}'. Use 'dm' or 'channel'"
            
            # Execute the coroutine
            # The Discord bot runs in its own event loop. We need to schedule the
            # coroutine in that loop from the agent's thread.
            bot = self.discord_service.bot
            if bot and hasattr(bot, 'loop') and bot.loop and bot.loop.is_running():
                # Schedule in the bot's event loop from this thread and wait for completion
                future = asyncio.run_coroutine_threadsafe(coro, bot.loop)
                try:
                    # Wait for completion with a reasonable timeout
                    future.result(timeout=self.TIMEOUT)
                    result = f"{action_desc} sent to {target}"
                except concurrent.futures.TimeoutError:
                    # Timeout - operation may still complete in background
                    result = f"{action_desc} initiated to {target} (operation timed out, may still complete)"
                except Exception as e:
                    result = f"Error sending {action_desc}: {str(e)}"
            else:
                # Bot loop not available - likely in testing or standalone mode
                # Try to run synchronously
                try:
                    loop = asyncio.get_running_loop()
                    # Already in an event loop (but not the bot's)
                    result = f"Error: Bot event loop not available for {action_desc}"
                except RuntimeError:
                    # No running loop - create temporary one (testing scenario)
                    # Save current loop if any
                    old_loop = None
                    try:
                        old_loop = asyncio.get_event_loop()
                    except RuntimeError:
                        pass
                    
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(coro)
                        result = f"{action_desc} sent to {target}"
                    finally:
                        loop.close()
                        # Restore previous loop if there was one
                        if old_loop is not None:
                            asyncio.set_event_loop(old_loop)
            
            return result
            
        except ValueError as e:
            return f"Error: Could not resolve target '{target}': {str(e)}"
        except Exception as e:
            return f"Error sending Discord message: {str(e)}"
