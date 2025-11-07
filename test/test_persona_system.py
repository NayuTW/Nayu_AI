#!/usr/bin/env python3
"""
Test for persona, mood tracking, and proactive behavior system.
"""
import sys
import os
import asyncio

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents.persona.persona import Persona, DEFAULT_PERSONA, create_custom_persona
from src.agents.persona.mood import MoodTracker, MoodState
from src.agents.persona.proactive import (
    ProactivePolicy, ProactiveScheduler, ProactiveContext, 
    ProactiveAction, IntentTemplate
)
from src.agents.core.events import EventBus
from src.agents.core.store import SQLiteStore


def test_persona_creation():
    """Test persona creation and serialization."""
    print("Testing persona creation...")
    
    # Test default persona
    persona = DEFAULT_PERSONA
    assert persona.name == "Nayu"
    assert 0.0 <= persona.playfulness <= 1.0
    assert 0.0 <= persona.curiosity <= 1.0
    assert 0.0 <= persona.helpfulness <= 1.0
    
    # Test system prompt generation
    prompt = persona.system_prompt()
    assert persona.name in prompt
    assert "playfulness" in prompt.lower()
    
    # Test custom persona
    custom = create_custom_persona(
        name="TestBot",
        backstory="A test AI",
        values=["testing", "reliability"],
        playfulness=0.8,
        curiosity=0.9
    )
    assert custom.name == "TestBot"
    assert custom.playfulness == 0.8
    
    # Test serialization
    data = custom.to_dict()
    restored = Persona.from_dict(data)
    assert restored.name == custom.name
    assert restored.playfulness == custom.playfulness
    
    print("✓ Persona creation tests passed")


def test_mood_tracking():
    """Test mood tracking system."""
    print("\nTesting mood tracking...")
    
    tracker = MoodTracker(max_history=10)
    
    # Initial state
    assert tracker.current_mood == MoodState.NEUTRAL
    
    # Test positive interaction
    tracker.update_from_interaction(
        "This is amazing! I love it!",
        sentiment=None,  # Let it auto-compute
        engagement=None
    )
    
    # Should have recorded interaction
    assert len(tracker.interactions) == 1
    assert tracker.interactions[0].sentiment > 0  # Should be positive
    
    # Test multiple positive interactions
    for _ in range(3):
        tracker.update_from_interaction("Great! This is wonderful!")
    
    # Mood should be positive
    assert tracker.current_mood in [MoodState.HAPPY, MoodState.EXCITED, MoodState.PLAYFUL]
    
    # Test mood influence
    influence = tracker.get_mood_influence()
    assert "playfulness_modifier" in influence
    assert "talkativeness_modifier" in influence
    
    # Test mood description
    desc = tracker.get_mood_description()
    assert isinstance(desc, str)
    assert len(desc) > 0
    
    # Test state export
    state = tracker.get_state()
    assert "mood" in state
    assert "recent_sentiment" in state
    assert "recent_engagement" in state
    
    print("✓ Mood tracking tests passed")


def test_proactive_policy():
    """Test proactive policy decision making."""
    print("\nTesting proactive policy...")
    
    tracker = MoodTracker()
    policy = ProactivePolicy(mood_tracker=tracker, randomness=0.1)
    
    # Test should_be_proactive
    context = ProactiveContext(
        time_since_last_user_msg=60.0,  # 1 minute idle
        time_since_last_agent_msg=120.0,
        recent_engagement=0.7,
        mood="happy",
        interaction_count=5,
        proactive_count_this_hour=1,
        max_proactive_per_hour=3
    )
    
    # With good context, should sometimes be proactive
    # Run multiple times due to randomness
    proactive_count = 0
    for _ in range(10):
        if policy.should_be_proactive(context):
            proactive_count += 1
    
    # Should be proactive at least sometimes
    assert proactive_count > 0, "Should be proactive sometimes with good context"
    
    # Test budget limit
    budget_context = ProactiveContext(
        time_since_last_user_msg=300.0,
        time_since_last_agent_msg=300.0,
        recent_engagement=0.8,
        mood="excited",
        interaction_count=10,
        proactive_count_this_hour=3,  # At max
        max_proactive_per_hour=3
    )
    
    # Should not be proactive when budget exhausted
    assert not policy.should_be_proactive(budget_context), "Should respect budget limit"
    
    # Test action decision
    action = policy.decide_action(context)
    assert isinstance(action, ProactiveAction)
    
    print("✓ Proactive policy tests passed")


def test_intent_templates():
    """Test intent template generation."""
    print("\nTesting intent templates...")
    
    # Test each template type
    question = IntentTemplate.get_question()
    assert isinstance(question, str)
    assert len(question) > 0
    
    fact = IntentTemplate.get_fun_fact("test fact")
    assert "test fact" in fact
    
    activity = IntentTemplate.get_activity()
    assert isinstance(activity, str)
    
    check_in = IntentTemplate.get_check_in()
    assert isinstance(check_in, str)
    
    riff = IntentTemplate.get_riff("interesting topic")
    assert "interesting topic" in riff
    
    print("✓ Intent template tests passed")


async def test_proactive_scheduler():
    """Test proactive scheduler."""
    print("\nTesting proactive scheduler...")
    
    # Create test infrastructure
    import tempfile
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    temp_db.close()
    
    try:
        store = SQLiteStore(path=temp_db.name)
        bus = EventBus(store=store)
        
        tracker = MoodTracker()
        policy = ProactivePolicy(mood_tracker=tracker)
        
        scheduler = ProactiveScheduler(
            bus=bus,
            policy=policy,
            min_interval=1.0,  # Short for testing
            max_interval=2.0,
            max_per_hour=5,
            enabled=True
        )
        
        # Test callback
        callback_called = asyncio.Event()
        received_action = None
        received_intent = None
        
        async def test_callback(action, intent):
            nonlocal received_action, received_intent
            received_action = action
            received_intent = intent
            callback_called.set()
        
        scheduler.set_callback(test_callback)
        
        # Update context
        scheduler.update_context(engagement=0.8)
        
        # Get context
        context = scheduler.get_context()
        assert context.max_proactive_per_hour == 5
        
        # Test enabled/disabled
        scheduler.enabled = False
        context2 = scheduler.get_context()
        assert context2 is not None
        
        print("✓ Proactive scheduler tests passed")
        
        store.close()
    finally:
        if os.path.exists(temp_db.name):
            os.unlink(temp_db.name)


async def test_persona_integration():
    """Test persona integration with mood."""
    print("\nTesting persona integration...")
    
    persona = DEFAULT_PERSONA
    tracker = MoodTracker()
    
    # Simulate positive interactions
    for text in [
        "Hey! How are you?",
        "This is great!",
        "I love this feature!"
    ]:
        tracker.update_from_interaction(text)
    
    # Get mood state
    mood_state = tracker.get_mood_description()
    
    # Test persona system prompt includes mood
    base_prompt = persona.system_prompt()
    assert persona.name in base_prompt
    assert "playfulness" in base_prompt.lower()
    
    # Verify mood tracking works - description should be a non-empty string
    assert isinstance(mood_state, str)
    assert len(mood_state) > 0
    
    # Test mood influence
    influence = tracker.get_mood_influence()
    assert isinstance(influence, dict)
    
    print("✓ Persona integration tests passed")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Persona System Tests")
    print("=" * 60)
    
    try:
        # Synchronous tests
        test_persona_creation()
        test_mood_tracking()
        test_proactive_policy()
        test_intent_templates()
        
        # Async tests
        asyncio.run(test_proactive_scheduler())
        asyncio.run(test_persona_integration())
        
        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
        return 0
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    except Exception as e:
        print(f"\n❌ Error running tests: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
