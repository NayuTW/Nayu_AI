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
            # Get the event loop to run async operations
            loop = asyncio.get_event_loop()
            
            if action == "send_channel":
                if channel_id:
                    # Send by channel ID
                    task = self.discord.send_channel_message(int(channel_id), text)
                    loop.create_task(task)
                    return f"Sent message to channel {channel_id}"
                elif target:
                    # Send by target (e.g., '#general')
                    task = self.discord.send_channel_target(target, text, guild_id=guild_id)
                    loop.create_task(task)
                    return f"Sent message to {target}"
                else:
                    return "Error: Provide 'channel_id' or 'target' for send_channel action"
            
            elif action == "send_dm":
                if user_id:
                    # Send DM by user ID
                    task = self.discord.send_dm(int(user_id), text)
                    loop.create_task(task)
                    return f"Sent DM to user {user_id}"
                elif target:
                    # Send DM by target (e.g., '@alice')
                    task = self.discord.send_dm_target(target, text, guild_id=guild_id)
                    loop.create_task(task)
                    return f"Sent DM to {target}"
                else:
                    return "Error: Provide 'user_id' or 'target' for send_dm action"
            
            else:
                return f"Error: Unknown action '{action}'. Use 'send_channel' or 'send_dm'"
        
        except Exception as e:
            return f"Error sending Discord message: {str(e)}"
