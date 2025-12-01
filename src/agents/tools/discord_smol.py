from typing import Any
from smolagents import Tool

class DiscordSendChannelTool(Tool):
    name = "discord_send_channel"
    description = "Post a message to a Discord channel by channel_id or human target like '#general'."
    inputs = {
        "text": {"type": "string", "description": "Message text to send"},
        "channel_id": {"type": "string", "description": "Discord channel ID (optional if target provided)", "nullable": True},
        "target": {"type": "string", "description": "Human-friendly channel target like '#general' (optional if channel_id provided)", "nullable": True},
        "guild_id": {"type": "number", "description": "Guild ID to disambiguate target (optional)", "nullable": True},
    }
    outputs = {"summary": {"type": "string"}}
    output_type = "string"

    def __init__(self, discord_service: Any):
        super().__init__()
        self.discord = discord_service

    def forward(self, text: str, channel_id: str = "", target: str = "", guild_id: int = 0) -> dict[str, str]:
        text = (text or "").strip()
        if not text:
            return {"summary": "No text provided."}

        try:
            if channel_id:
                # numeric ID path
                self.discord.bot.loop.create_task(self.discord.send_channel_message(int(channel_id), text))
                return {"summary": f"Sent to channel {channel_id}."}
            if target:
                gid = int(guild_id) if guild_id else None
                self.discord.bot.loop.create_task(self.discord.send_channel_target(target, text, guild_id=gid))
                return {"summary": f"Sent to {target}."}
            return {"summary": "Provide 'channel_id' or 'target'."}
        except Exception as e:
            return {"summary": f"Discord send failed: {e}"}
