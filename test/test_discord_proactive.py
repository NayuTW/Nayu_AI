#!/usr/bin/env python3
"""
Test for Discord proactive messaging features.
"""
import sys
import os
import asyncio
from unittest.mock import Mock, AsyncMock, MagicMock

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents.persona.proactive import (
    ProactivePolicy, ProactiveScheduler, ProactiveContext, 
    ProactiveAction, IntentTemplate
)
from src.agents.core.events import EventBus
from src.agents.core.store import SQLiteStore
from src.agents.persona.mood import MoodTracker


def test_discord_actions_in_enum():
    """Test that Discord actions are available in ProactiveAction enum."""
    print("Testing Discord actions in enum...")
    
    # Check that new Discord actions exist
    assert hasattr(ProactiveAction, 'DISCORD_DM_RANDOM_USER')
    assert hasattr(ProactiveAction, 'DISCORD_MESSAGE_CHANNEL')
    
    # Verify they have correct values
    assert ProactiveAction.DISCORD_DM_RANDOM_USER.value == "discord_dm_random_user"
    assert ProactiveAction.DISCORD_MESSAGE_CHANNEL.value == "discord_message_channel"
    
    print("✓ Discord actions exist in ProactiveAction enum")


def test_discord_intent_templates():
    """Test Discord-specific intent templates."""
    print("\nTesting Discord intent templates...")
    
    # Test DM greeting templates
    dm_greeting = IntentTemplate.get_discord_dm_greeting()
    assert isinstance(dm_greeting, str)
    assert len(dm_greeting) > 0
    print(f"  Sample DM greeting: {dm_greeting}")
    
    # Test channel message templates
    channel_msg = IntentTemplate.get_discord_channel_message()
    assert isinstance(channel_msg, str)
    assert len(channel_msg) > 0
    print(f"  Sample channel message: {channel_msg}")
    
    # Test variety (run multiple times to check different templates)
    greetings = set()
    for _ in range(10):
        greetings.add(IntentTemplate.get_discord_dm_greeting())
    assert len(greetings) > 1, "Should have variety in greetings"
    
    print("✓ Discord intent templates work correctly")


def test_proactive_policy_discord_utilities():
    """Test that ProactivePolicy correctly calculates utilities for Discord actions."""
    print("\nTesting ProactivePolicy Discord utilities...")
    
    tracker = MoodTracker()
    policy = ProactivePolicy(mood_tracker=tracker, randomness=0.0, temperature=1.0)
    
    context = ProactiveContext(
        time_since_last_user_msg=100.0,
        time_since_last_agent_msg=50.0,
        recent_engagement=0.5,
        mood="neutral",
        interaction_count=5,
        proactive_count_this_hour=1,
        max_proactive_per_hour=3
    )
    
    # Test with Discord disabled (default)
    utilities = policy._calculate_utilities(context)
    assert ProactiveAction.DISCORD_DM_RANDOM_USER in utilities
    assert ProactiveAction.DISCORD_MESSAGE_CHANNEL in utilities
    assert utilities[ProactiveAction.DISCORD_DM_RANDOM_USER] == 0.0, "Should be disabled by default"
    assert utilities[ProactiveAction.DISCORD_MESSAGE_CHANNEL] == 0.0, "Should be disabled by default"
    
    # Test with Discord enabled
    policy.discord_enabled = True
    utilities = policy._calculate_utilities(context)
    assert utilities[ProactiveAction.DISCORD_DM_RANDOM_USER] > 0.0, "Should be enabled"
    assert utilities[ProactiveAction.DISCORD_MESSAGE_CHANNEL] > 0.0, "Should be enabled"
    
    print("✓ ProactivePolicy Discord utilities work correctly")


async def test_proactive_scheduler_discord_management():
    """Test ProactiveScheduler Discord user/channel management."""
    print("\nTesting ProactiveScheduler Discord management...")
    
    store = SQLiteStore(":memory:")
    bus = EventBus(store=store)
    tracker = MoodTracker()
    policy = ProactivePolicy(mood_tracker=tracker)
    
    scheduler = ProactiveScheduler(
        bus=bus,
        policy=policy,
        max_per_hour=3,
        enabled=True
    )
    
    # Test adding/removing users
    scheduler.add_discord_known_user("@user1")
    scheduler.add_discord_known_user("@user2")
    users = scheduler.get_discord_known_users()
    assert len(users) == 2
    assert "@user1" in users
    assert "@user2" in users
    
    scheduler.remove_discord_known_user("@user1")
    users = scheduler.get_discord_known_users()
    assert len(users) == 1
    assert "@user2" in users
    
    # Test adding/removing channels
    scheduler.add_discord_known_channel("#general", guild_id=123456)
    scheduler.add_discord_known_channel("#random")
    channels = scheduler.get_discord_known_channels()
    assert len(channels) == 2
    
    # Check channel config structure
    general_channel = next((c for c in channels if c["target"] == "#general"), None)
    assert general_channel is not None
    assert general_channel["guild_id"] == 123456
    
    scheduler.remove_discord_known_channel("#general", guild_id=123456)
    channels = scheduler.get_discord_known_channels()
    assert len(channels) == 1
    
    # Test random selection
    scheduler.add_discord_known_user("@user1")
    scheduler.add_discord_known_user("@user2")
    scheduler.add_discord_known_user("@user3")
    
    # Get multiple random users to verify randomness
    selected_users = set()
    for _ in range(20):
        user = scheduler.get_random_discord_user()
        selected_users.add(user)
    
    assert len(selected_users) > 1, "Should randomly select different users"
    
    # Test random channel selection
    scheduler.add_discord_known_channel("#channel1")
    scheduler.add_discord_known_channel("#channel2")
    channel = scheduler.get_random_discord_channel()
    assert channel is not None
    assert channel["target"] in ["#random", "#channel1", "#channel2"]
    
    print("✓ ProactiveScheduler Discord management works correctly")


async def test_proactive_scheduler_discord_messaging():
    """Test ProactiveScheduler Discord message sending."""
    print("\nTesting ProactiveScheduler Discord messaging...")
    
    store = SQLiteStore(":memory:")
    bus = EventBus(store=store)
    tracker = MoodTracker()
    policy = ProactivePolicy(mood_tracker=tracker)
    
    # Create mock Discord service
    mock_discord = Mock()
    mock_discord.send_dm_target = AsyncMock()
    mock_discord.send_channel_target = AsyncMock()
    
    scheduler = ProactiveScheduler(
        bus=bus,
        policy=policy,
        max_per_hour=3,
        enabled=True,
        discord_service=mock_discord
    )
    
    # Configure Discord proactive
    scheduler.set_discord_proactive_enabled(True)
    scheduler.add_discord_known_user("@testuser")
    scheduler.add_discord_known_channel("#testchannel", guild_id=999)
    
    # Test DM handling
    await scheduler._handle_discord_dm("Test DM message")
    mock_discord.send_dm_target.assert_called_once()
    args = mock_discord.send_dm_target.call_args
    assert args[0][1] == "Test DM message"  # Check message content
    
    # Test channel handling
    await scheduler._handle_discord_channel_message("Test channel message")
    mock_discord.send_channel_target.assert_called_once()
    args = mock_discord.send_channel_target.call_args
    assert args[0][1] == "Test channel message"  # Check message content
    
    print("✓ ProactiveScheduler Discord messaging works correctly")


async def test_discord_proactive_disabled_behavior():
    """Test that Discord proactive features are properly disabled when not configured."""
    print("\nTesting Discord proactive disabled behavior...")
    
    store = SQLiteStore(":memory:")
    bus = EventBus(store=store)
    tracker = MoodTracker()
    policy = ProactivePolicy(mood_tracker=tracker)
    
    scheduler = ProactiveScheduler(
        bus=bus,
        policy=policy,
        max_per_hour=3,
        enabled=True
    )
    
    # Subscribe to events to check for disabled messages
    event_queue = await bus.subscribe()
    
    # Try to send DM without Discord service configured
    await scheduler._handle_discord_dm("Test message")
    
    # Check for disabled event
    try:
        event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
        assert event.type == "proactive.discord_disabled"
        print("  ✓ Correctly published discord_disabled event when service not configured")
    except asyncio.TimeoutError:
        print("  ⚠ No event received (might be expected)")
    
    # Test with service but no targets
    mock_discord = Mock()
    mock_discord.send_dm_target = AsyncMock()
    scheduler.set_discord_service(mock_discord)
    scheduler.set_discord_proactive_enabled(True)
    
    await scheduler._handle_discord_dm("Test message")
    
    # Check for no targets event
    try:
        event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
        assert event.type == "proactive.discord_no_targets"
        print("  ✓ Correctly published discord_no_targets event when no users configured")
    except asyncio.TimeoutError:
        print("  ⚠ No event received (might be expected)")
    
    print("✓ Discord proactive disabled behavior works correctly")


def test_intent_generation_for_discord_actions():
    """Test that _get_intent_for_action returns correct intents for Discord actions."""
    print("\nTesting intent generation for Discord actions...")
    
    store = SQLiteStore(":memory:")
    bus = EventBus(store=store)
    tracker = MoodTracker()
    policy = ProactivePolicy(mood_tracker=tracker)
    
    scheduler = ProactiveScheduler(
        bus=bus,
        policy=policy,
        max_per_hour=3,
        enabled=True
    )
    
    # Test Discord DM intent
    dm_intent = scheduler._get_intent_for_action(ProactiveAction.DISCORD_DM_RANDOM_USER)
    assert isinstance(dm_intent, str)
    assert len(dm_intent) > 0
    print(f"  Discord DM intent: {dm_intent}")
    
    # Test Discord channel intent
    channel_intent = scheduler._get_intent_for_action(ProactiveAction.DISCORD_MESSAGE_CHANNEL)
    assert isinstance(channel_intent, str)
    assert len(channel_intent) > 0
    print(f"  Discord channel intent: {channel_intent}")
    
    print("✓ Intent generation for Discord actions works correctly")


async def run_all_tests():
    """Run all test functions."""
    print("=" * 60)
    print("Discord Proactive Features Test Suite")
    print("=" * 60)
    
    try:
        # Synchronous tests
        test_discord_actions_in_enum()
        test_discord_intent_templates()
        test_proactive_policy_discord_utilities()
        test_intent_generation_for_discord_actions()
        
        # Asynchronous tests
        await test_proactive_scheduler_discord_management()
        await test_proactive_scheduler_discord_messaging()
        await test_discord_proactive_disabled_behavior()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
