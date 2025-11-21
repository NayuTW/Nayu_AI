import asyncio
import logging
import os
from typing import Any, Optional, Set, Iterable

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

# Discord hard limit is 2000 characters per message. Leave headroom.
MAX_DISCORD_MSG_LEN = 1900


def _chunk_text(s: str, n: int = MAX_DISCORD_MSG_LEN) -> Iterable[str]:
    if not s:
        return []
    return (s[i:i+n] for i in range(0, len(s), n))


def _only_digits(s: str) -> Optional[int]:
    s = "".join(ch for ch in s if ch.isdigit())
    if len(s) >= 16:  # Discord snowflakes are 17–19 digits typically
        try:
            return int(s)
        except Exception:
            return None
    return None


class DiscordBotService:
    """
    Discord adapter for Nayu_AI.

    - Keeps a lightweight directory of seen users/channels to resolve @names / #channels -> IDs.
    - Provides send helpers that accept targets like "@alice" or "#general".
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
        intents.members = True  # enable for richer resolution (requires Server Members Intent for large guilds)

        self.bot = commands.Bot(command_prefix=command_prefix, intents=intents)
        self._wire_events()

        self._task: Optional[asyncio.Task] = None
        self._running = asyncio.Event()

        # Lightweight directory
        # Users
        self._users_by_id: dict[int, dict[str, Any]] = {}  # id -> {username, discriminator, display_name_by_guild:{gid:name}}
        self._usernames_index: dict[str, set[int]] = {}     # lower(username or "name#disc") -> set(ids)
        self._displaynames_index_by_guild: dict[int, dict[str, set[int]]] = {}  # gid -> lower(display) -> set(ids)
        # Channels
        self._channels_by_id: dict[int, dict[str, Any]] = {}  # id -> {name, guild_id}
        self._channels_by_name_by_guild: dict[int, dict[str, int]] = {}  # gid -> lower(name) -> id

    def _wire_events(self) -> None:
        @self.bot.event
        async def on_ready():
            logger.info(
                "Discord bot connected as %s (id=%s) respond_mode=%s read_only=%s",
                self.bot.user,
                self.bot.user.id if self.bot.user else None,
                self.respond_mode,
                self.read_only,
            )
            # Preload channels/usernames we can access (best effort)
            try:
                for guild in self.bot.guilds:
                    await self._index_guild(guild)
            except Exception:
                logger.exception("Pre-indexing guilds failed")
            self._running.set()

        @self.bot.event
        async def on_guild_join(guild: discord.Guild):
            try:
                await self._index_guild(guild)
            except Exception:
                logger.exception("Indexing new guild failed")

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

            is_dm = message.guild is None
            mentions_bot = self._is_bot_mentioned(message)
            content = message.content or ""
            logger.debug(
                "on_message: guild=%s channel=%s is_dm=%s respond_mode=%s mentions_bot=%s content_len=%d",
                message.guild.id if message.guild else None,
                message.channel.id,
                is_dm,
                self.respond_mode,
                mentions_bot,
                len(content),
            )

            # Update directory from this message context
            try:
                self._update_directory_from_message(message)
            except Exception:
                logger.exception("Directory update failed")

            # Lightweight ingest only (do NOT generate an LLM reply here)
            asyncio.create_task(self._lightweight_ingest(message))

            # Determine if we should reply
            if self.read_only or self.respond_mode == "passive":
                return

            should_reply = await self._should_reply(message)
            if not should_reply:
                logger.debug("Reply gated: should_reply=%s", should_reply)
                return

            try:
                reply = await self._maybe_get_agent_reply(message)
            except Exception as e:
                logger.exception("Agent reply failed: %s", e)
                reply = "Sorry, something went wrong while generating a response."

            # Avoid sending blank messages; provide a friendly fallback
            if not reply or not str(reply).strip():
                logger.info("Agent returned empty response; sending fallback")
                reply = "Sorry — I didn’t catch that. Could you rephrase?"

            await self._safe_reply(message, reply)

        # Optional simple command to verify the bot
        @self.bot.command(name="ping")
        async def ping(ctx: commands.Context):
            await ctx.reply("pong")

    async def _index_guild(self, guild: discord.Guild):
        # Index channels
        try:
            for ch in guild.text_channels:
                self._channels_by_id[ch.id] = {"name": ch.name, "guild_id": guild.id}
                self._channels_by_name_by_guild.setdefault(guild.id, {})[ch.name.lower()] = ch.id
        except Exception:
            logger.exception("Indexing channels failed for guild %s", guild.id)

        # Index members (best effort; may be partial without privileged intent)
        try:
            async for member in guild.fetch_members(limit=None):
                self._index_member(member)
        except Exception:
            # Fallback: only cache members we see in messages
            logger.debug("fetch_members not available or failed for guild %s", guild.id)

    def _index_member(self, member: discord.Member):
        uid = member.id
        username = member.name or ""
        discriminator = getattr(member, "discriminator", None)
        display = member.display_name or ""
        # Users by ID
        entry = self._users_by_id.setdefault(uid, {"username": username, "discriminator": discriminator, "display_name_by_guild": {}})
        entry["username"] = username or entry.get("username") or ""
        entry["discriminator"] = discriminator if discriminator is not None else entry.get("discriminator")
        entry["display_name_by_guild"][member.guild.id] = display
        # Username/global index (username and name#disc string)
        key1 = (username or "").lower()
        if key1:
            self._usernames_index.setdefault(key1, set()).add(uid)
        if discriminator and username:
            key2 = f"{username}#{discriminator}".lower()
            self._usernames_index.setdefault(key2, set()).add(uid)
        # Display name in this guild
        if display:
            self._displaynames_index_by_guild.setdefault(member.guild.id, {}).setdefault(display.lower(), set()).add(uid)

    def _update_directory_from_message(self, message: discord.Message):
        # User
        if isinstance(message.author, (discord.Member, discord.User)):
            if isinstance(message.author, discord.Member):
                self._index_member(message.author)
            else:
                uid = message.author.id
                username = message.author.name or ""
                discriminator = getattr(message.author, "discriminator", None)
                entry = self._users_by_id.setdefault(uid, {"username": username, "discriminator": discriminator, "display_name_by_guild": {}})
                entry["username"] = username or entry.get("username") or ""
                entry["discriminator"] = discriminator if discriminator is not None else entry.get("discriminator")
                key1 = (username or "").lower()
                if key1:
                    self._usernames_index.setdefault(key1, set()).add(uid)
                if discriminator and username:
                    key2 = f"{username}#{discriminator}".lower()
                    self._usernames_index.setdefault(key2, set()).add(uid)

        # Channel
        ch = message.channel
        if isinstance(ch, (discord.TextChannel, discord.Thread)):
            base = ch.parent if isinstance(ch, discord.Thread) else ch
            self._channels_by_id[base.id] = {"name": base.name, "guild_id": base.guild.id if base.guild else None}
            if base.guild:
                self._channels_by_name_by_guild.setdefault(base.guild.id, {})[base.name.lower()] = base.id

    async def _lightweight_ingest(self, message: discord.Message) -> None:
        """
        Publish a minimal ingest event without invoking the full LLM pipeline.
        This prevents 'dashboard-only' outputs when we don't intend to reply.
        """
        try:
            payload: dict[str, Any] = {
                "source": "discord",
                "user_id": str(message.author.id),
                "channel_id": str(message.channel.id),
                "text": message.content or "",
                "metadata": {
                    "username": str(message.author),
                    "display_name": getattr(message.author, "display_name", None),
                    "guild_id": message.guild.id if message.guild else None,
                    "guild_name": message.guild.name if message.guild else None,
                    "channel_name": getattr(message.channel, "name", None),
                    "is_dm": message.guild is None,
                    "message_id": str(message.id),
                    "mentions_bot": self._is_bot_mentioned(message),
                },
            }
            # If the agent exposes an EventBus, publish the ingest event
            bus = getattr(self.agent, "bus", None)
            if bus and hasattr(bus, "publish"):
                await bus.publish("message.ingest", payload)
        except Exception:
            logger.exception("Lightweight ingest failed")

    async def _maybe_get_agent_reply(self, message: discord.Message) -> Optional[str]:
        text = self._strip_bot_mention(message) if self._is_bot_mentioned(message) else (message.content or "")
        user_id = str(message.author.id)
        channel_id = str(message.channel.id)
        source = "discord"

        metadata: dict[str, Any] = {
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

        reply = await handler(
            text=text,
            user_id=user_id,
            channel_id=channel_id,
            source=source,
            metadata=metadata,
        )

        # Normalize to string (agent may return None)
        return "" if reply is None else str(reply)

    async def _safe_reply(self, message: discord.Message, reply: str) -> None:
        """
        Reply in the same context:
        - In DMs: reply directly
        - In guild channels: send in channel, prefer a reply to the specific message
        - Chunk long replies to respect Discord's 2000-char limit
        """
        try:
            parts = list(_chunk_text(reply))
            if not parts:
                logger.info("Nothing to send after chunking")
                return

            if message.guild is None:
                for part in parts:
                    await message.channel.send(part)
            else:
                # Reply to the triggering message once, then continue in channel for additional parts
                await message.reply(parts[0], mention_author=False)
                for part in parts[1:]:
                    await message.channel.send(part)
        except discord.Forbidden:
            logger.warning("Missing permissions to reply in channel %s", message.channel.id)
        except discord.HTTPException as e:
            logger.exception("Failed to send reply (HTTPException): %s", e)
        except Exception:
            logger.exception("Failed to send reply")

    async def send_dm(self, user_id: int, content: str) -> None:
        """Send a DM by numeric user ID."""
        try:
            user = await self.bot.fetch_user(user_id)
            for part in _chunk_text(content):
                await user.send(part)
        except Exception:
            logger.exception("Failed to send DM to %s", user_id)

    async def send_channel_message(self, channel_id: int, content: str) -> None:
        """Send a message to a text-capable channel by numeric ID."""
        try:
            channel = self.bot.get_channel(channel_id) or await self.bot.fetch_channel(channel_id)
            if isinstance(channel, (discord.TextChannel, discord.Thread, discord.DMChannel)):
                for part in _chunk_text(content):
                    await channel.send(part)
            else:
                logger.warning("Channel %s not a text-capable channel", channel_id)
        except Exception:
            logger.exception("Failed to send message to channel %s", channel_id)

    # --- Target resolution and convenience sends ---

    def resolve_user(self, target: str, guild_id: Optional[int] = None) -> Optional[int]:
        """
        Resolve a user target to ID:
        - raw ID: "1234567890"
        - mention: "<@123...>" or "<@!123...>"
        - "@name" or "name"
        - "name#1234" (legacy discriminator)
        Priority: guild display name -> username -> name#disc -> global partial match.
        """
        if not target:
            return None
        target = target.strip()
        # Raw digits or mention
        if any(ch.isdigit() for ch in target):
            maybe = _only_digits(target)
            if maybe:
                return maybe

        # Strip leading "@"
        name = target[1:] if target.startswith("@") else target
        name_l = name.lower()

        # Prefer guild display names
        if guild_id is not None:
            by_guild = self._displaynames_index_by_guild.get(guild_id, {})
            # Exact
            ids = by_guild.get(name_l)
            if ids:
                return next(iter(ids))
            # Startswith or contains (best-effort)
            for key, ids in by_guild.items():
                if key.startswith(name_l) or name_l in key:
                    return next(iter(ids))

        # Try username/global exact
        ids = self._usernames_index.get(name_l)
        if ids:
            return next(iter(ids))

        # Fuzzy: startswith on username keys
        for key, ids in self._usernames_index.items():
            if key.startswith(name_l) or name_l in key:
                return next(iter(ids))

        return None

    def resolve_channel(self, target: str, guild_id: Optional[int] = None) -> Optional[int]:
        """
        Resolve a channel target to ID:
        - raw ID: "123..."
        - mention: "<#123...>"
        - "#name" or "name"
        Prefer channels in the provided guild when possible.
        """
        if not target:
            return None
        target = target.strip()
        if any(ch.isdigit() for ch in target):
            maybe = _only_digits(target)
            if maybe:
                return maybe
        # Strip leading "#"
        name = target[1:] if target.startswith("#") else target
        name_l = name.lower()

        if guild_id is not None:
            by_name = self._channels_by_name_by_guild.get(guild_id, {})
            ch_id = by_name.get(name_l)
            if ch_id:
                return ch_id
            # fuzzy
            for key, cid in by_name.items():
                if key.startswith(name_l) or name_l in key:
                    return cid

        # Fallback: any guild
        for gid, by_name in self._channels_by_name_by_guild.items():
            ch_id = by_name.get(name_l)
            if ch_id:
                return ch_id
            for key, cid in by_name.items():
                if key.startswith(name_l) or name_l in key:
                    return cid

        return None

    async def send_dm_target(self, target: str, content: str, guild_id: Optional[int] = None) -> None:
        uid = self.resolve_user(target, guild_id=guild_id)
        if uid is None:
            raise ValueError(f"Could not resolve user target: {target}")
        await self.send_dm(uid, content)

    async def send_channel_target(self, target: str, content: str, guild_id: Optional[int] = None) -> None:
        cid = self.resolve_channel(target, guild_id=guild_id)
        if cid is None:
            raise ValueError(f"Could not resolve channel target: {target}")
        await self.send_channel_message(cid, content)

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
