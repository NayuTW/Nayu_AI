"""
Discord tool converted to smolagents Tool class.
Handles sending messages to Discord channels and DMs.
"""
from typing import Optional, Any
from smolagents import Tool


class DiscordSmolTool(Tool):
    """
    Send messages to Discord channels or direct messages.
    Requires an active Discord bot service.
    """
    name = "discord"
    description = (
        "Send messages to Discord (DMs or channels). "
        "You can specify numeric IDs or human-friendly targets like '#general' or '@username'. "
        "Use action='send_channel' for channel messages or action='send_dm' for direct messages."
    )
    inputs = {
        "action": {
            "type": "string",
            "description": "Action: 'send_channel' for channels or 'send_dm' for DMs"
        },
        "text": {
            "type": "string",
            "description": "Message text to send"
        },
        "channel_id": {
            "type": "string",
            "description": "Discord channel ID (for send_channel)",
            "nullable": True
        },
        "user_id": {
            "type": "string",
            "description": "Discord user ID (for send_dm)",
            "nullable": True
        },
        "target": {
            "type": "string",
            "description": "Human-friendly target like '#general' or '@alice'",
            "nullable": True
        },
        "guild_id": {
            "type": "integer",
            "description": "Guild ID for name resolution (optional)",
            "nullable": True
        }
    }
    output_type = "string"
    
    def __init__(self, discord_service: Any):
        super().__init__()
        self.discord = discord_service
    
    def forward(
        self,
        action: str,
        text: str,
        channel_id: Optional[str] = None,
        user_id: Optional[str] = None,
        target: Optional[str] = None,
        guild_id: Optional[int] = None
    ) -> str:
        """Execute Discord action and return result."""
        import asyncio
        
        text = (text or "").strip()
        if not text:
            return "Error: No text provided for Discord message"
        
        try:
            # Define the async operation
            async def send_discord_message():
                if action == "send_channel":
                    if channel_id:
                        await self.discord.send_channel_message(int(channel_id), text)
                        return f"Sent message to channel {channel_id}"
                    elif target:
                        await self.discord.send_channel_target(target, text, guild_id=guild_id)
                        return f"Sent message to {target}"
                    else:
                        return "Error: Provide 'channel_id' or 'target' for send_channel action"
                
                elif action == "send_dm":
                    if user_id:
                        await self.discord.send_dm(int(user_id), text)
                        return f"Sent DM to user {user_id}"
                    elif target:
                        await self.discord.send_dm_target(target, text, guild_id=guild_id)
                        return f"Sent DM to {target}"
                    else:
                        return "Error: Provide 'user_id' or 'target' for send_dm action"
                
                else:
                    return f"Error: Unknown action '{action}'. Use 'send_channel' or 'send_dm'"
            
            # Try to get the running event loop (Discord bot's loop)
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, create a task and schedule it
                # Use asyncio.create_task to schedule the coroutine
                future = asyncio.ensure_future(send_discord_message(), loop=loop)
                # Return immediately without waiting (fire and forget)
                return "Discord message scheduled for delivery"
            except RuntimeError:
                # No running loop, try to use the Discord bot's loop
                if hasattr(self.discord, 'bot') and hasattr(self.discord.bot, 'loop'):
                    loop = self.discord.bot.loop
                    # Schedule the coroutine on the bot's event loop
                    asyncio.run_coroutine_threadsafe(send_discord_message(), loop)
                    return "Discord message scheduled for delivery"
                else:
                    return "Error: No event loop available for Discord operations"
        
        except Exception as e:
            return f"Error sending Discord message: {str(e)}"
