from typing import Any, Dict, Optional

class DiscordTool:
    """
    Tool for sending messages to Discord via the running DiscordBotService.
    Actions:
      - send_dm(user_id, text) OR send_dm(target, text) with target like "@alice"
      - send_channel(channel_id, text) OR send_channel(target, text) with target like "#general"
    """

    def __init__(self, discord_service: Any):
        self.discord = discord_service

    @staticmethod
    def spec():
        # Add concrete examples inside the description so the model sees how to call it.
        return {
            "name": "discord",
            "description": (
                "Send messages to Discord (DMs or channels). You can specify numeric IDs or human-friendly targets.\n"
                "Examples:\n"
                '- {"action":"send_channel","text":"Hello everyone!","target":"#general"}\n'
                '- {"action":"send_dm","text":"Hi there","target":"@alice"}\n'
                '- {"action":"send_channel","text":"Deploy completed ✅","channel_id":"123456789012345678"}\n'
                "If a name is ambiguous, ask a brief clarifying question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["send_dm", "send_channel"]},
                    "text": {"type": "string", "description": "Message text to send"},
                    "user_id": {"type": "string", "description": "Discord user ID (for send_dm)"},
                    "channel_id": {"type": "string", "description": "Discord channel ID (for send_channel)"},
                    "target": {"type": "string", "description": "Human-friendly target like '@alice' or '#general'"},
                    "guild_id": {"type": "number", "description": "Guild ID for name resolution (optional)"},
                },
                "required": ["action", "text"],
            },
        }

    async def run(
        self,
        action: str,
        text: str,
        user_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        target: Optional[str] = None,
        guild_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        text = (text or "").strip()
        if not text:
            return {"summary": "No text provided.", "delta": {}}

        try:
            if action == "send_dm":
                if user_id:
                    await self.discord.send_dm(int(user_id), text)
                    return {"summary": f"Sent DM to {user_id}.", "delta": {}}
                if target:
                    await self.discord.send_dm_target(target, text, guild_id=guild_id)
                    return {"summary": f"Sent DM to {target}.", "delta": {}}
                return {"summary": "Provide 'user_id' or 'target' for send_dm.", "delta": {}}

            if action == "send_channel":
                if channel_id:
                    await self.discord.send_channel_message(int(channel_id), text)
                    return {"summary": f"Sent message to channel {channel_id}.", "delta": {}}
                if target:
                    await self.discord.send_channel_target(target, text, guild_id=guild_id)
                    return {"summary": f"Sent message to {target}.", "delta": {}}
                return {"summary": "Provide 'channel_id' or 'target' for send_channel.", "delta": {}}

            return {"summary": "Invalid action.", "delta": {}}
        except Exception as e:
            return {"summary": f"Discord send failed: {e}", "delta": {}}
