# Discord Proactive Messaging Feature

## Overview

This feature allows the Nayu_AI agent to proactively send messages to Discord users or channels based on the proactive behavior system. The agent can randomly select from a configured list of known users or channels and send friendly check-in messages.

## Features

- **Random User DMs**: Send direct messages to randomly selected users from a configured list
- **Channel Messages**: Send messages to randomly selected channels from a configured list
- **Integration with Mood System**: Discord proactive messages are influenced by the agent's mood
- **Configurable**: Easy to enable/disable and manage lists of users and channels via CLI
- **Persistent**: Settings are saved to SQLite database and persist across restarts

## Configuration

### Environment Variables

No additional environment variables are required. The feature uses the existing `DISCORD_BOT_TOKEN` and proactive system settings.

### CLI Commands

When the Discord bot is running, the following commands are available:

#### Enable/Disable Discord Proactive Messaging

```
discord proactive on     # Enable Discord proactive messaging
discord proactive off    # Disable Discord proactive messaging
```

#### Manage Known Users for DMs

```
discord add user @username        # Add a user to the proactive DM list
discord add user 123456789        # Add a user by ID
discord rm user @username         # Remove a user from the list
```

#### Manage Known Channels

```
discord add channel #general             # Add a channel (searches across guilds)
discord add channel #general 123456789   # Add a channel with specific guild ID
discord rm channel #general              # Remove a channel
discord rm channel #general 123456789    # Remove a channel with specific guild ID
```

#### View Configuration

```
discord list    # Show current Discord proactive configuration
```

## How It Works

1. **Proactive Scheduler**: The existing proactive scheduler runs in the background, periodically checking if the agent should take a proactive action.

2. **Action Selection**: When proactive behavior is triggered, the scheduler decides which action to take based on:
   - Current mood state
   - Time since last interaction
   - Recent engagement level
   - Available actions (including Discord options if configured)

3. **Discord Actions**: Two new proactive actions are available:
   - `DISCORD_DM_RANDOM_USER`: Sends a friendly DM to a random user from the configured list
   - `DISCORD_MESSAGE_CHANNEL`: Sends a message to a random channel from the configured list

4. **Message Templates**: Discord messages use pre-defined templates that vary for personality:
   - **DM Greetings**: "Hey! Hope you're doing well. Just wanted to reach out and say hi!"
   - **Channel Messages**: "Hey everyone! Hope you're all having a great day!"

5. **Mood Influence**: The agent's current mood affects the likelihood of Discord actions:
   - **Playful mood**: More likely to message channels
   - **Curious mood**: More likely to send DMs
   - **Calm mood**: Less likely to send Discord messages

## Usage Example

### Basic Setup

1. Start the agent with Discord bot enabled (requires `DISCORD_BOT_TOKEN` environment variable)

2. Enable Discord proactive messaging:
   ```
   discord proactive on
   ```

3. Add some users and channels:
   ```
   discord add user @alice
   discord add user @bob
   discord add channel #general 123456789
   discord add channel #random
   ```

4. Enable the general proactive system if not already enabled:
   ```
   proactive on
   ```

5. The agent will now occasionally send proactive messages to these users/channels based on its proactive schedule.

### Checking Status

View current configuration at any time:
```
discord list
```

Example output:
```
Discord Proactive Configuration:
  Enabled: True
  Policy Enabled: True
  Known Users (2):
    - @alice
    - @bob
  Known Channels (2):
    - #general (guild: 123456789)
    - #random
```

## Configuration Persistence

All Discord proactive settings are automatically saved to the SQLite database:
- `discord_proactive_enabled`: Whether Discord proactive is enabled
- `discord_known_users`: Comma-separated list of user targets
- `discord_known_channels`: Semicolon-separated list of channel configs (format: `target|guild_id`)

These settings persist across agent restarts.

## Integration with Existing Systems

### Proactive Schedule

Discord actions follow the same schedule and budget rules as other proactive actions:
- Minimum 30 seconds between proactive checks
- Maximum configurable actions per hour (default: 3)
- Influenced by idle time and engagement

### Event System

Discord proactive actions publish events to the event bus:
- `proactive.discord_sent`: Successfully sent a Discord message
- `proactive.discord_disabled`: Attempted action when Discord not configured
- `proactive.discord_no_targets`: Attempted action with no users/channels configured
- `proactive.discord_error`: Error occurred while sending message

## Safety and Privacy

- **User Control**: Users must be explicitly added to the known users list
- **Channel Control**: Channels must be explicitly configured
- **Rate Limiting**: Subject to the same rate limits as other proactive actions
- **Easy Disable**: Can be disabled at any time with `discord proactive off`
- **No Data Collection**: The feature only stores user/channel targets, no message content

## Testing

A comprehensive test suite is available in `test/test_discord_proactive.py`:

```bash
python test/test_discord_proactive.py
```

Tests cover:
- Discord action enum values
- Intent template generation
- ProactivePolicy utility calculations
- ProactiveScheduler user/channel management
- Random selection logic
- Message sending (with mocks)
- Disabled behavior
- Error handling

## Troubleshooting

### Discord messages not being sent

1. Check that Discord bot is running (should show "Discord bot: RUNNING" on startup)
2. Verify Discord proactive is enabled: `discord list`
3. Verify you have users or channels configured: `discord list`
4. Check that general proactive behavior is enabled: should show "proactive: ON" on startup
5. Be patient - proactive actions have rate limits (max 3 per hour by default)

### Messages going to wrong users/channels

- Use `discord list` to verify your configuration
- Remove incorrect entries with `discord rm user` or `discord rm channel`
- For channels in specific guilds, always specify the guild_id

### Cannot add users or channels

- Make sure the Discord bot has seen these users/channels in messages
- The bot builds an index of users/channels it encounters
- Try using numeric IDs instead of @mentions or #names

## Future Enhancements

Potential improvements for future versions:
- Dashboard UI for managing Discord proactive settings
- Per-user or per-channel proactive schedules
- Custom message templates per user/channel
- Integration with memory system for personalized messages
- Time-of-day preferences for proactive messages
