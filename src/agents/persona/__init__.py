"""
Persona and character system for the agent.
Provides personality, mood tracking, and proactive behavior.
"""
from src.agents.persona.persona import Persona, DEFAULT_PERSONA, create_custom_persona
from src.agents.persona.mood import MoodTracker, MoodState
from src.agents.persona.proactive import ProactiveScheduler, ProactivePolicy, ProactiveAction, IntentTemplate, ProactiveContext

__all__ = [
    'Persona',
    'DEFAULT_PERSONA',
    'create_custom_persona',
    'MoodTracker',
    'MoodState',
    'ProactiveScheduler',
    'ProactivePolicy',
    'ProactiveAction',
    'ProactiveContext',
    'IntentTemplate',
]
