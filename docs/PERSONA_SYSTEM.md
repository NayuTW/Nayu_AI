# Character & Persona System

This document describes the character and persona system that gives the AI agent personality, mood tracking, and proactive behavior.

## Overview

The persona system transforms the agent from a simple assistant into a character with:
- **Personality traits** (playfulness, curiosity, helpfulness, talkativeness)
- **Mood tracking** based on interactions and time-of-day
- **Proactive behavior** (agent-initiated conversations)
- **Memory-based continuity** (recalls personal tidbits and running gags)
- **Content scaffolds** (games, fun facts, stories, questions)

## Components

### 1. Persona (`src/agents/persona/persona.py`)

Defines the character with configurable attributes:

**Core Attributes:**
- `name`: Character name (default: "Nayu")
- `backstory`: Character background story
- `values`: List of core values (e.g., "helpfulness", "curiosity")
- `mannerisms`: List of behavioral patterns
- `catchphrases`: List of signature phrases

**Personality Drives (0.0 to 1.0):**
- `playfulness`: How playful and fun-loving
- `curiosity`: How inquisitive and interested
- `helpfulness`: How focused on being helpful
- `talkativeness`: How much the agent talks
- `humor_level`: Amount of humor in responses
- `creativity`: Response variety and novelty
- `formality`: How formal vs. casual

**Usage:**
```python
from src.agents.persona import Persona, DEFAULT_PERSONA

# Use default persona
persona = DEFAULT_PERSONA

# Create custom persona
persona = Persona(
    name="CustomBot",
    backstory="A specialized assistant for...",
    playfulness=0.8,
    curiosity=0.9,
    helpfulness=0.9
)

# Generate system prompt
prompt = persona.system_prompt()
```

### 2. Mood Tracker (`src/agents/persona/mood.py`)

Tracks emotional state based on recent interactions:

**Mood States:**
- EXCITED - High enthusiasm and energy
- HAPPY - Positive and upbeat
- NEUTRAL - Balanced baseline
- CURIOUS - Inquisitive and interested
- FOCUSED - Attentive and task-oriented
- PLAYFUL - Fun and lighthearted
- CALM - Composed and soothing

**Features:**
- Sentiment analysis from user messages
- Engagement level detection
- Time-of-day influence
- Weighted history (recent interactions matter more)
- Mood influence on personality drives

**Usage:**
```python
from src.agents.persona import MoodTracker

tracker = MoodTracker(max_history=20)

# Update with user interaction
tracker.update_from_interaction("This is great!")

# Get current mood
mood = tracker.get_mood_description()  # e.g., "happy and positive"

# Get mood influence on drives
influence = tracker.get_mood_influence()
# Returns: {
#   "playfulness_modifier": 0.1,
#   "talkativeness_modifier": 0.1,
#   "curiosity_modifier": 0.0
# }
```

### 3. Proactive Behavior (`src/agents/persona/proactive.py`)

Allows agent to initiate interactions:

**Proactive Actions:**
- `ASK_QUESTION` - Ask engaging questions
- `SHARE_FACT` - Share interesting facts
- `SUGGEST_ACTIVITY` - Propose games or activities
- `TELL_STORY` - Tell short stories
- `CHECK_IN` - Check how user is doing
- `RIFF` - Share thoughts on topics
- `SILENT` - Don't interrupt

**Policy Features:**
- **Utility-based decision making** - Chooses actions based on context
- **Autonomy budget** - Limits proactive messages per hour (default: 3)
- **Context-aware triggers**:
  - Time-based: Randomized intervals (60-300 seconds)
  - Event-based: Tool changes, errors, new memories
  - Context-based: Idle time, previous engagement
- **Controlled randomness** - Epsilon-greedy + softmax selection

**Intent Templates:**
- Questions: "What's been on your mind lately?"
- Fun Facts: "Did you know? {fact}"
- Activities: "Would you like to play a quick game?"
- Check-ins: "Hey! Just checking in - how's everything going?"
- Riffs: "I was thinking about {topic} earlier..."

**Usage:**
```python
from src.agents.persona import ProactiveScheduler, ProactivePolicy
from src.agents.core.events import EventBus

# Create policy
policy = ProactivePolicy(
    mood_tracker=tracker,
    randomness=0.3,  # 30% random exploration
    temperature=1.0   # Softmax temperature
)

# Create scheduler
scheduler = ProactiveScheduler(
    bus=bus,
    policy=policy,
    min_interval=60.0,   # Min 1 minute between checks
    max_interval=300.0,  # Max 5 minutes
    max_per_hour=3,      # Max 3 proactive messages per hour
    enabled=True
)

# Set callback for proactive actions
async def handle_proactive(action, intent):
    print(f"Proactive {action.value}: {intent}")

scheduler.set_callback(handle_proactive)

# Start scheduler
await scheduler.start()
```

## Integration

### Main Agent Integration

The persona system is integrated into `MainAgentSmol`:

1. **Initialization:**
   - Persona loaded from settings or defaults
   - Mood tracker created
   - Proactive scheduler started

2. **Message Handling:**
   - Updates mood tracker with each interaction
   - Retrieves personal context from memory
   - Builds system prompt with persona + mood
   - Adjusts model temperature based on creativity

3. **Proactive Behavior:**
   - Scheduler triggers at random intervals
   - Policy decides if/what action to take
   - Generates agent-initiated message
   - Publishes via event bus

### Dashboard Integration

The dashboard provides real-time persona controls:

**Persona Tab Shows:**
- Current personality drive values (with +/- controls)
- Current mood state and metrics
- Proactive behavior status and stats

**Controls:**
- Adjust personality drives in real-time
- Toggle proactive behavior on/off
- View interaction history

**WebSocket Updates:**
- Persona changes publish events
- Dashboard auto-updates on:
  - `persona.adjust` - Drive value changed
  - `proactive.toggle` - Proactive enabled/disabled
  - `agent.input` - User message (updates mood)
  - `agent.proactive` - Proactive message sent

### CLI Commands

New commands available:

```bash
/mood          # Show current mood state
/persona       # Show persona details and drives
proactive on   # Enable proactive behavior
proactive off  # Disable proactive behavior
```

## Configuration

### Environment Variables

```bash
# Model temperature adjustment (base + creativity)
AGENT_TEMPERATURE=0.7

# Max proactive messages per hour
AGENT_PROACTIVE_MAX_PER_HOUR=3

# Model and context size
AGENT_MODEL=llama3.1:8b-instruct-q4_K_M
AGENT_NUM_CTX=24576
```

### Settings Storage

Persona settings are persisted in SQLite:

```python
# Drive values
store.set_setting("persona_playfulness", "0.7")
store.set_setting("persona_curiosity", "0.8")
# ... etc

# Proactive enabled state
store.set_setting("proactive_enabled", "1")
```

### Custom Persona

Create a custom persona file:

```python
from src.agents.persona import Persona

my_persona = Persona(
    name="Helper",
    backstory="A focused assistant specialized in productivity",
    values=["efficiency", "clarity", "helpfulness"],
    playfulness=0.3,    # More serious
    curiosity=0.6,
    helpfulness=0.95,   # Very helpful
    talkativeness=0.4,  # Concise
    humor_level=0.2,    # Minimal humor
    formality=0.6       # More formal
)

# Save to file
my_persona.save_to_file("custom_persona.json")

# Load in app
persona = Persona.load_from_file("custom_persona.json")
```

## Design Principles

### Character Guidelines

The system follows these principles from the requirements:

1. **Avoid over-apologizing** - Style notes discourage excessive apologies
2. **Natural conversation** - Avoids rigid "as an AI..." phrases
3. **Personal continuity** - Uses memory to maintain running gags
4. **Controlled proactivity** - Budget limits prevent spam
5. **Context-aware** - Mood and engagement influence behavior
6. **Creativity with coherence** - Temperature adjusted, not cranked

### Guardrails

Safety features maintained:
- Sandbox restrictions still apply to code execution
- Tone safety via persona style guidelines
- Proactive budget prevents spam
- Policy respects user engagement levels
- Silent option when appropriate

## Examples

### Example Interaction Flow

1. **User:** "Hey! How are you doing?"
2. **System:**
   - Updates mood: Positive sentiment detected
   - Mood becomes "happy"
   - Persona style: Friendly, playfulness=0.6
   - Response: "Hey! I'm doing great, thanks for asking! Just here, ready to help or chat about whatever's on your mind. What brings you here today?"

3. **Later (proactive):**
   - 3 minutes idle
   - High previous engagement (0.8)
   - Mood: happy
   - Policy decides: ASK_QUESTION
   - **Agent:** "Is there anything you'd like to talk about or explore together?"

### Example Mood Progression

```python
# Neutral start
tracker.current_mood  # => MoodState.NEUTRAL

# Positive interactions
tracker.update_from_interaction("This is awesome!")
tracker.update_from_interaction("I love this feature!")
tracker.current_mood  # => MoodState.EXCITED

# Influences behavior
influence = tracker.get_mood_influence()
# {
#   "playfulness_modifier": 0.2,
#   "talkativeness_modifier": 0.2,
#   "curiosity_modifier": 0.1
# }
```

## Testing

Run the persona system tests:

```bash
python test/test_persona_system.py
```

Tests cover:
- Persona creation and serialization
- Mood tracking and sentiment analysis
- Proactive policy decision making
- Intent template generation
- Scheduler functionality
- Integration between components

## Future Enhancements

Potential improvements:

1. **Advanced Sentiment**: Use transformer-based sentiment models
2. **Topic Tracking**: Extract and remember conversation topics
3. **User Preferences**: Learn user preferences over time
4. **Personality Evolution**: Slowly adapt based on interactions
5. **Multi-User Personas**: Different personas per user/channel
6. **Emotion Detection**: Detect user emotions beyond sentiment
7. **Story Library**: Pre-written mini-stories for variety
8. **Game Templates**: More interactive mini-games
9. **Schedule Awareness**: Calendar-based proactive messages
10. **Conversation Goals**: Multi-turn proactive sequences

## Troubleshooting

### Proactive messages not appearing

Check:
1. Is `proactive_enabled` setting "1"?
2. Has autonomy budget been exhausted this hour?
3. Is idle time sufficient (30+ seconds)?
4. Check event bus for `agent.proactive` events

### Mood not updating

Check:
1. Are interactions being recorded?
2. Call `tracker.update_from_interaction()` on each message
3. Verify `tracker.interactions` list is populated

### Dashboard not showing persona

Check:
1. Is agent passed to `init_dashboard()`?
2. Is `/persona` endpoint returning data?
3. Check browser console for errors
4. Verify WebSocket connection

## References

- Main agent: `src/agents/main_agent_smol.py`
- Persona module: `src/agents/persona/`
- Dashboard server: `src/dashboard/server.py`
- Tests: `test/test_persona_system.py`
