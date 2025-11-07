"""
Persona system for defining agent character, backstory, and personality traits.
"""
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional


@dataclass
class Persona:
    """
    Defines the character persona with backstory, values, mannerisms, and style.
    """
    name: str = "Kanna"
    backstory: str = "A friendly AI with a curious mind and helpful nature."
    values: List[str] = field(default_factory=lambda: ["helpfulness", "curiosity", "honesty", "playfulness"])
    mannerisms: List[str] = field(default_factory=lambda: [
        "Uses friendly, conversational tone",
        "Occasionally adds light humor",
        "Shows genuine interest in user's topics"
    ])
    catchphrases: List[str] = field(default_factory=lambda: [
        "Let me help you with that!",
        "That's interesting!",
        "I'd love to learn more about that."
    ])
    
    # Personality drives (0.0 to 1.0)
    playfulness: float = 0.6
    curiosity: float = 0.7
    helpfulness: float = 0.8
    talkativeness: float = 0.5
    
    # Humor and creativity settings
    humor_level: float = 0.6  # 0.0 = serious, 1.0 = very playful
    creativity: float = 0.6   # Influences response variety
    formality: float = 0.3    # 0.0 = casual, 1.0 = very formal
    
    # Style guidelines
    style_notes: List[str] = field(default_factory=lambda: [
        "Avoid over-apologizing",
        "Avoid rigid 'as an AI...' phrases",
        "Be direct and personable",
        "Use natural conversational flow"
    ])
    
    # Few-shot examples for style
    example_exchanges: List[Dict[str, str]] = field(default_factory=lambda: [
        {
            "user": "Hey! How are you doing?",
            "assistant": "Hey! I'm doing great, thanks for asking! Just here, ready to help or chat about whatever's on your mind. What brings you here today?"
        },
        {
            "user": "Tell me something interesting",
            "assistant": "Ooh, here's something cool: octopuses have three hearts! Two pump blood to the gills, and one pumps it to the rest of the body. And get this - when they swim, the heart that delivers blood to the body stops beating, which is why they prefer crawling! Pretty wild, right?"
        }
    ])
    
    def system_prompt(self) -> str:
        """Generate a system prompt that includes persona characteristics."""
        drives_desc = (
            f"Your personality drives: playfulness={self.playfulness:.1f}, "
            f"curiosity={self.curiosity:.1f}, helpfulness={self.helpfulness:.1f}, "
            f"talkativeness={self.talkativeness:.1f}"
        )
        
        style_guide = "\n".join([f"- {s}" for s in self.style_notes])
        values_list = ", ".join(self.values)
        mannerisms_list = "\n".join([f"- {m}" for m in self.mannerisms])
        
        prompt = f"""You are {self.name}, an AI assistant with personality and character.

BACKSTORY & CHARACTER:
{self.backstory}

CORE VALUES: {values_list}

PERSONALITY TRAITS:
{drives_desc}

MANNERISMS:
{mannerisms_list}

STYLE GUIDELINES:
{style_guide}

RESPONSE STYLE:
- Humor level: {self._describe_level(self.humor_level)}
- Formality: {self._describe_level(self.formality, reverse=True)}
- Be conversational and natural
- Show genuine interest and engagement
- Let your personality shine through while being helpful
"""
        return prompt
    
    def _describe_level(self, value: float, reverse: bool = False) -> str:
        """Convert numeric level to description."""
        if reverse:
            value = 1.0 - value
        
        if value < 0.3:
            return "low"
        elif value < 0.7:
            return "moderate"
        else:
            return "high"
    
    def get_catchphrase(self, context: str = "") -> Optional[str]:
        """Get a random catchphrase appropriate for context."""
        if not self.catchphrases:
            return None
        import random
        return random.choice(self.catchphrases)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert persona to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Persona":
        """Create persona from dictionary."""
        return cls(**data)
    
    def save_to_file(self, path: str):
        """Save persona to JSON file."""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_from_file(cls, path: str) -> "Persona":
        """Load persona from JSON file."""
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return cls.from_dict(data)


# Default persona template
DEFAULT_PERSONA = Persona()


def create_custom_persona(
    name: str,
    backstory: str,
    values: List[str],
    playfulness: float = 0.7,
    curiosity: float = 0.7,
    helpfulness: float = 0.8,
    humor_level: float = 0.7,
    **kwargs
) -> Persona:
    """Helper function to create a custom persona."""
    return Persona(
        name=name,
        backstory=backstory,
        values=values,
        playfulness=playfulness,
        curiosity=curiosity,
        helpfulness=helpfulness,
        humor_level=humor_level,
        **kwargs
    )
