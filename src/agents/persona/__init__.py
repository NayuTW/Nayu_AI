"""
Persona and character system for the agent.
Provides personality, mood tracking, and proactive behavior.
"""
from src.agents.persona.persona import Persona, DEFAULT_PERSONA
from src.agents.persona.mood import MoodTracker, MoodState
from src.agents.persona.proactive import ProactiveScheduler, ProactivePolicy, ProactiveAction, IntentTemplate

__all__ = [
    'Persona',
    'DEFAULT_PERSONA',
    'MoodTracker',
    'MoodState',
    'ProactiveScheduler',
    'ProactivePolicy',
    'ProactiveAction',
    'IntentTemplate',
]
