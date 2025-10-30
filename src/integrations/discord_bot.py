import asyncio
import logging
import os
from typing import Any, Dict, Optional, Set

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class DiscordBotService:
    """
    Discord adapter for Nayu_AI.

    Responsibilities:
    - Connect to Discord with Pycord (discord.py fork).
    - Read ALL messages in guilds the bot is in, and DMs to the bot.
    - Forward every message to the MainAgent for logging/memory/metrics (non-blocking).
    - Optionally generate AI replies based on respond_mode:
        - "passive": never reply, only log/ingest
        - "mention": reply if bot is mentioned or in DM
        - "prefix": reply if message starts with command_prefix or in DM
        - "all": reply to every message (careful!)
    - Provide helper methods to send DMs or channel messages programmatically.

    Expected MainAgent interface:
        async def handle_external_message(
            self,
            text: str,
            user_id: str,
            channel_id: str,
            source: str,
            metadata: Dict[str, Any],
        ) -> Optional[str]:
            return "response or None"

    If your MainAgent uses a different API, adapt `_maybe_get_agent_reply`.
    """

    def __init__(
        self,
        agent: Any,
        token: Optional[str] = None,
        respond_mode: str = "mention",
        command_prefix: str = "!",
        allowed_guild_ids: Optional[Set[int]] = None,
        allowed_channel_ids: Optional[Set[int]] = None,
        read_only: bool = False,
    ) -> None:
        self.agent = agent
        self.token = token or os.getenv("DISCORD_BOT_TOKEN") or ""
        if not self.token:
            raise RuntimeError("DISCORD_BOT_TOKEN not set")

        self.respond_mode = respond_mode  # "passive" | "mention" | "prefix" | "all"
        self.command_prefix = command_prefix
        self.allowed_guild_ids = allowed_guild_ids
        self.allowed_channel_ids = allowed_channel_ids
        self.read_only = read_only

        intents = discord.Intents.default()
        intents.message_content = True  # MUST be enabled in Developer Portal too
        intents.guilds = True
        intents.members = False

        self.bot = commands.Bot(command_prefix=command_prefix, intents=intents)
        self._wire_events()

        self._task: Optional[asyncio.Task] = None
        self._running = asyncio.Event()

    def _wire_events(self) -> None:
        @self.bot.event
        async def on_ready():
            logger.info("Discord bot connected as %s (id=%s)", self.bot.user, self.bot.user.id if self.bot.user else None)
            self._running.set()

        @self.bot.event
        async def on_message(message: discord.Message):
            # Ignore own messages and other bots
            if message.author.bot:
                return

            # Filter by guild/channel if configured
            if self.allowed_guild_ids is not None:
                if message.guild is None or message.guild.id not in self.allowed_guild_ids:
                    return
            if self.allowed_channel_ids is not None:
                if message.channel.id not in self.allowed_channel_ids:
                    return

            # Always forward the message to the agent for logging/memory
            await self._forward_to_agent_for_ingest(message)

            # Determine if we should reply
            if self.read_only or self.respond_mode == "passive":
                return

            should_reply = await self._should_reply(message)
            if not should_reply:
                return

            try:
                reply = await self._maybe_get_agent_reply(message)
            except Exception as e:
                logger.exception("Agent reply failed: %s", e)
                reply = "Sorry, something went wrong while generating a response."

            if reply:
                await self._safe_reply(message, reply)

        # Optional simple command to verify the bot
        @self.bot.command(name="ping")
        async def ping(ctx: commands.Context):
            await ctx.reply("pong")

    async def _forward_to_agent_for_ingest(self, message: discord.Message) -> None:
        content = message.content or ""
        user_id = str(message.author.id)
        channel_id = str(message.channel.id)
        source = "discord"

        metadata: Dict[str, Any] = {
            "username": str(message.author),
            "display_name": getattr(message.author, "display_name", None),
            "guild_id": message.guild.id if message.guild else None,
            "guild_name": message.guild.name if message.guild else None,
            "channel_name": getattr(message.channel, "name", None),
            "is_dm": message.guild is None,
            "message_id": str(message.id),
            "mentions_bot": self._is_bot_mentioned(message),
        }

        # Fire-and-forget ingestion; don't block the Discord gateway
        asyncio.create_task(self._invoke_agent_ingest(content, user_id, channel_id, source, metadata))

    async def _invoke_agent_ingest(
        self,
        text: str,
        user_id: str,
        channel_id: str,
        source: str,
        metadata: Dict[str, Any],
    ) -> None:
        """
        Send message to agent even if we don't plan to reply, so memory/metrics stay in sync.
        Default behavior: call the same hook used for replies, and ignore its returned text.
        If your agent has a dedicated 'ingest only' path, call that here instead.
        """
        try:
            handler = getattr(self.agent, "handle_external_message", None)
            if callable(handler):
                await handler(text=text, user_id=user_id, channel_id=channel_id, source=source, metadata=metadata)
            else:
                # Fallback: try 'process_user_message' or 'handle_message' if your agent exposes them
                for candidate in ("process_user_message", "handle_message", "ingest_message"):
                    func = getattr(self.agent, candidate, None)
                    if callable(func):
                        await func(text=text, user_id=user_id, channel_id=channel_id, source=source, metadata=metadata)
                        break
        except Exception:
            logger.exception("Agent ingestion failed")

    async def _maybe_get_agent_reply(self, message: discord.Message) -> Optional[str]:
        text = self._strip_bot_mention(message) if self._is_bot_mentioned(message) else (message.content or "")
        user_id = str(message.author.id)
        channel_id = str(message.channel.id)
        source = "discord"

        metadata: Dict[str, Any] = {
            "username": str(message.author),
            "display_name": getattr(message.author, "display_name", None),
            "guild_id": message.guild.id if message.guild else None,
            "guild_name": message.guild.name if message.guild else None,
            "channel_name": getattr(message.channel, "name", None),
            "is_dm": message.guild is None,
            "message_id": str(message.id),
            "mentions_bot": self._is_bot_mentioned(message),
            "respond_mode": self.respond_mode,
        }

        handler = getattr(self.agent, "handle_external_message", None)
        if not callable(handler):
            # If your agent uses another API, adapt here
            raise RuntimeError("MainAgent is missing 'handle_external_message'")

        return await handler(
            text=text,
            user_id=user_id,
            channel_id=channel_id,
            source=source,
            metadata=metadata,
        )

    async def _safe_reply(self, message: discord.Message, reply: str) -> None:
        """
        Reply in the same context:
        - In DMs: reply directly
        - In guild channels: send in channel, prefer a reply to the specific message
        """
        try:
            if message.guild is None:
                await message.channel.send(reply)
            else:
                await message.reply(reply, mention_author=False)
        except discord.Forbidden:
            logger.warning("Missing permissions to reply in channel %s", message.channel.id)
        except Exception:
            logger.exception("Failed to send reply")

    async def _should_reply(self, message: discord.Message) -> bool:
        is_dm = message.guild is None
        content = message.content or ""

        if is_dm:
            return True

        if self.respond_mode == "all":
            return True
        if self.respond_mode == "mention":
            return self._is_bot_mentioned(message)
        if self.respond_mode == "prefix":
            return content.strip().startswith(self.command_prefix)

        return False

    def _is_bot_mentioned(self, message: discord.Message) -> bool:
        if not self.bot.user:
            return False
        return any(u.id == self.bot.user.id for u in message.mentions)

    def _strip_bot_mention(self, message: discord.Message) -> str:
        """
        Remove the leading bot mention from content if present, for cleaner prompts.
        """
        content = message.content or ""
        if not self.bot.user:
            return content

        mention_forms = (f"<@{self.bot.user.id}>", f"<@!{self.bot.user.id}>")
        for mf in mention_forms:
            if content.startswith(mf):
                return content[len(mf):].lstrip()
        return content

    async def start(self) -> None:
        """
        Start the Discord bot within the current asyncio loop (non-blocking for the process).
        """
        if self._task and not self._task.done():
            logger.info("DiscordBotService already running")
            return

        async def runner():
            try:
                await self.bot.start(self.token)
            except asyncio.CancelledError:
                # Expected during shutdown
                pass
            except Exception:
                logger.exception("Discord bot crashed")

        self._task = asyncio.create_task(runner(), name="discord-bot-runner")
        await self._running.wait()

    async def stop(self) -> None:
        if self.bot.is_closed():
            return
        await self.bot.close()
        if self._task and not self._task.done():
            self._task.cancel()

    # Public helpers to send messages programmatically

    async def send_dm(self, user_id: int, content: str) -> None:
        try:
            user = await self.bot.fetch_user(user_id)
            await user.send(content)
        except Exception:
            logger.exception("Failed to send DM to %s", user_id)

    async def send_channel_message(self, channel_id: int, content: str) -> None:
        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel)):
                await channel.send(content)
            else:
                logger.warning("Channel %s not a text-capable channel", channel_id)
        except Exception:
            logger.exception("Failed to send message to channel %s", channel_id)
