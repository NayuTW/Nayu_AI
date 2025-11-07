#!/usr/bin/env python3
"""
Demo script showcasing the persona system.
This demonstrates persona, mood tracking, and proactive behavior without requiring full LLM setup.
"""
import asyncio
import sys
import os
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.agents.persona import (
    Persona, DEFAULT_PERSONA, create_custom_persona,
    MoodTracker, MoodState,
    ProactivePolicy, ProactiveScheduler, ProactiveContext, ProactiveAction,
    IntentTemplate
)
from src.agents.core.events import EventBus
from src.agents.core.store import SQLiteStore


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def demo_persona_basics():
    """Demonstrate basic persona features."""
    print_section("Persona Basics")
    
    # Show default persona
    persona = DEFAULT_PERSONA
    print(f"\nDefault Persona: {persona.name}")
    print(f"Backstory: {persona.backstory}")
    print(f"Values: {', '.join(persona.values)}")
    print(f"\nPersonality Drives:")
    print(f"  Playfulness: {persona.playfulness:.1f}")
    print(f"  Curiosity: {persona.curiosity:.1f}")
    print(f"  Helpfulness: {persona.helpfulness:.1f}")
    print(f"  Talkativeness: {persona.talkativeness:.1f}")
    print(f"  Humor Level: {persona.humor_level:.1f}")
    
    # Show system prompt excerpt
    prompt = persona.system_prompt()
    lines = prompt.split('\n')[:10]
    print(f"\nSystem Prompt (first 10 lines):")
    for line in lines:
        print(f"  {line}")
    print("  ...")
    
    # Create custom persona
    print("\n" + "-" * 60)
    custom = create_custom_persona(
        name="CodeBot",
        backstory="A programming-focused AI assistant who loves clean code and best practices",
        values=["clarity", "efficiency", "learning"],
        playfulness=0.3,
        curiosity=0.9,
        helpfulness=0.95,
        humor_level=0.4,
    )
    print(f"\nCustom Persona: {custom.name}")
    print(f"Backstory: {custom.backstory}")
    print(f"Playfulness: {custom.playfulness:.1f} (more serious)")
    print(f"Curiosity: {custom.curiosity:.1f} (very curious)")


def demo_mood_tracking():
    """Demonstrate mood tracking."""
    print_section("Mood Tracking")
    
    tracker = MoodTracker(max_history=10)
    
    print(f"\nInitial mood: {tracker.get_mood_description()}")
    
    # Simulate conversation
    interactions = [
        ("Hey there!", "greeting"),
        ("This is amazing! I love it!", "very positive"),
        ("Tell me more!", "engaged"),
        ("That's so cool!!", "enthusiastic"),
    ]
    
    print("\nSimulating interactions:")
    for i, (text, note) in enumerate(interactions, 1):
        print(f"\n{i}. User: \"{text}\" ({note})")
        tracker.update_from_interaction(text)
        
        # Get state
        state = tracker.get_state()
        interaction = tracker.interactions[-1]
        
        print(f"   Sentiment: {interaction.sentiment:+.2f}")
        print(f"   Engagement: {interaction.engagement:.2f}")
        print(f"   Current mood: {state['mood_description']}")
    
    # Show mood influence
    print("\n" + "-" * 60)
    print("Mood Influence on Personality:")
    influence = tracker.get_mood_influence()
    for key, value in influence.items():
        if value != 0:
            print(f"  {key}: {value:+.2f}")


def demo_proactive_policy():
    """Demonstrate proactive decision making."""
    print_section("Proactive Behavior Policy")
    
    tracker = MoodTracker()
    # Add some positive interactions
    for _ in range(3):
        tracker.update_from_interaction("This is great!")
    
    policy = ProactivePolicy(mood_tracker=tracker, randomness=0.2)
    
    # Test different contexts
    contexts = [
        ("Idle user, high engagement", ProactiveContext(
            time_since_last_user_msg=120.0,  # 2 minutes idle
            time_since_last_agent_msg=130.0,
            recent_engagement=0.8,
            mood="happy",
            interaction_count=10,
            proactive_count_this_hour=1,
            max_proactive_per_hour=3
        )),
        ("Active user", ProactiveContext(
            time_since_last_user_msg=10.0,  # Just messaged
            time_since_last_agent_msg=15.0,
            recent_engagement=0.9,
            mood="excited",
            interaction_count=15,
            proactive_count_this_hour=2,
            max_proactive_per_hour=3
        )),
        ("Budget exhausted", ProactiveContext(
            time_since_last_user_msg=180.0,  # 3 minutes idle
            time_since_last_agent_msg=200.0,
            recent_engagement=0.7,
            mood="happy",
            interaction_count=20,
            proactive_count_this_hour=3,  # At max
            max_proactive_per_hour=3
        )),
    ]
    
    for scenario, context in contexts:
        print(f"\nScenario: {scenario}")
        print(f"  Time since last message: {context.time_since_last_user_msg:.0f}s")
        print(f"  Engagement: {context.recent_engagement:.1f}")
        print(f"  Proactive count: {context.proactive_count_this_hour}/{context.max_proactive_per_hour}")
        
        should_act = policy.should_be_proactive(context)
        print(f"  → Should be proactive? {should_act}")
        
        if should_act:
            action = policy.decide_action(context)
            print(f"  → Chosen action: {action.value}")


def demo_intent_templates():
    """Demonstrate intent templates."""
    print_section("Intent Templates")
    
    print("\nExample intents for each action type:")
    
    print("\n1. Questions:")
    for _ in range(2):
        print(f"   - \"{IntentTemplate.get_question()}\"")
    
    print("\n2. Fun Facts:")
    facts = [
        "octopuses have three hearts",
        "honey never spoils",
    ]
    for fact in facts:
        print(f"   - \"{IntentTemplate.get_fun_fact(fact)}\"")
    
    print("\n3. Activities:")
    for _ in range(2):
        print(f"   - \"{IntentTemplate.get_activity()}\"")
    
    print("\n4. Check-ins:")
    for _ in range(2):
        print(f"   - \"{IntentTemplate.get_check_in()}\"")


async def main():
    """Run all demos."""
    print("\n" + "=" * 60)
    print("  PERSONA SYSTEM DEMO")
    print("=" * 60)
    
    # Run demos
    demo_persona_basics()
    demo_mood_tracking()
    demo_proactive_policy()
    demo_intent_templates()
    
    print("\n" + "=" * 60)
    print("  Demo Complete!")
    print("=" * 60)
    print("\nTo try the full system:")
    print("  1. Install dependencies: pip install -r requirements.txt")
    print("  2. Run: python -m src.app")
    print("\nThen visit http://localhost:8008 to see the dashboard!")
    print()


if __name__ == "__main__":
    asyncio.run(main())
