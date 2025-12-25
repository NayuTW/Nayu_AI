# Discord Integration (Pycord)

This integration lets the MainAgent read messages from Discord (guilds + DMs) and optionally reply.

## Prerequisites

1. Create a Discord application and a bot in the Developer Portal.
2. Invite the bot to your server with appropriate permissions:
   - Send Messages
   - Read Message History
3. Enable the **Message Content Intent** for your bot in the Developer Portal.
4. Install dependencies:

```bash
pip install -U py-cord
```

5. Set the bot token:

```bash
export DISCORD_BOT_TOKEN="your-bot-token"
```

## Running

- Minimal example:

```bash
python -m src.app_discord_example
```

- In production, start the `DiscordBotService` alongside your FastAPI dashboard in your app’s startup hook (so both run in the same process and event loop).

## Configuration

Environment variables:

- `DISCORD_BOT_TOKEN` (required): Bot token.
- `DISCORD_RESPOND_MODE` (optional): One of:
  - `passive`: never reply, only log/ingest
  - `mention` (default): reply on bot mention or DM
  - `prefix`: reply when message starts with prefix or DM
  - `all`: reply to every message (use with caution)
- `DISCORD_COMMAND_PREFIX` (optional): Prefix for `prefix` mode (default: `!`).
- `DISCORD_READ_ONLY` (optional): `true` to log only, never reply.

Programmatic restrictions (pass to `DiscordBotService`):

- `allowed_guild_ids`: limit bot operations to specific guild IDs.
- `allowed_channel_ids`: limit bot operations to specific channel IDs.

## How It Works

- Listens to `on_message` for all guild + DM messages.
- For every message, forwards text + metadata to `MainAgent.handle_external_message(...)` for ingestion (memory/metrics).
- **Automatically downloads image attachments** from Discord messages and saves them to `.cache/discord_images/`.
- **Passes image paths to the agent** via metadata, allowing the vision tool to analyze them.
- Depending on `respond_mode`, the service obtains a reply from the agent and posts it back to the same context (DM or channel reply).

## Vision Tool Integration

The Discord integration now supports automatic image analysis:

1. **Automatic Download**: When a user sends a message with image attachments, the bot automatically downloads them to `.cache/discord_images/`.

2. **Vision Tool Access**: The main agent is informed about attached images and can use the `vision(path='...')` tool to analyze them.

3. **Example Usage**: 
   - User sends: "What's in this image?" with an image attachment
   - Agent automatically sees: `IMAGE ATTACHMENTS: 1. .cache/discord_images/discord_123_456_789.png`
   - Agent can call: `vision(path='.cache/discord_images/discord_123_456_789.png')`
   - Agent responds with image description

4. **Supported Formats**: Any image format Discord supports (PNG, JPG, GIF, WebP, etc.)

5. **Metadata**: Image information is included in:
   - `metadata['downloaded_images']`: List of local file paths
   - `metadata['image_attachments']`: List of attachment info (URL, filename, content type)

## Sending Messages Programmatically

From within your code (e.g., when an event triggers an alert), you can:

```python
await discord_service.send_dm(user_id, "Hello via DM!")
await discord_service.send_channel_message(channel_id, "Hello in a channel!")
```

## Notes and Best Practices

- Make sure **Message Content Intent** is enabled, otherwise your bot won’t see message bodies.
- Avoid `respond_mode=all` in busy servers to prevent spam and rate-limit issues.
- Always check `message.author.bot` to avoid infinite loops with other bots.
- Use `allowed_channel_ids` when piloting to keep the bot contained.
