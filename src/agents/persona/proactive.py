"""
Proactive behavior system for agent initiative.
Allows agent to initiate conversation, ask questions, and suggest activities.
"""
import asyncio
import random
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List
from enum import Enum

from src.agents.core.events import EventBus
from src.agents.persona.mood import MoodTracker


class ProactiveAction(Enum):
    """Types of proactive actions the agent can take."""
    ASK_QUESTION = "ask_question"
    SHARE_FACT = "share_fact"
    SUGGEST_ACTIVITY = "suggest_activity"
    TELL_STORY = "tell_story"
    CHECK_IN = "check_in"
    RIFF = "riff"
    SILENT = "silent"


@dataclass
class ProactiveContext:
    """Context information for proactive decision making."""
    time_since_last_user_msg: float  # seconds
    time_since_last_agent_msg: float  # seconds
    recent_engagement: float  # 0.0 to 1.0
    mood: str
    interaction_count: int
    proactive_count_this_hour: int
    max_proactive_per_hour: int


class IntentTemplate:
    """Templates for different types of proactive intents."""
    
    QUESTIONS = [
        "Is there anything you'd like to talk about or explore together?",
        "What's been on your mind lately?",
        "Have you come across anything interesting recently?",
        "Is there something you're curious about that I could help with?",
        "What would you like to do or chat about?"
    ]
    
    FUN_FACTS = [
        "Here's something cool I learned: {fact}",
        "Did you know? {fact}",
        "Random fun fact: {fact}",
        "This is interesting: {fact}"
    ]
    
    ACTIVITIES = [
        "Would you like to play a quick game? I could do '2 truths and a lie' or a word association game!",
        "Want to do a quick brainstorming session? Pick any topic!",
        "How about a mini creative challenge? I could give you a writing prompt or idea starter.",
        "Feel like exploring a random topic together? I can pick something interesting!",
        "Want to hear a short story, or would you rather tell me one?"
    ]
    
    CHECK_INS = [
        "Hey! Just checking in - how's everything going?",
        "Hope you're doing well! Anything I can help with?",
        "Just wanted to say hi! What are you up to?",
        "Checking in - is there anything on your mind?"
    ]
    
    RIFFS = [
        "You know what's fascinating? {topic}",
        "I was thinking about {topic} earlier...",
        "Random thought: {topic}",
        "This might sound random, but {topic}"
    ]
    
    @classmethod
    def get_question(cls) -> str:
        return random.choice(cls.QUESTIONS)
    
    @classmethod
    def get_fun_fact(cls, fact: str = "octopuses have three hearts!") -> str:
        return random.choice(cls.FUN_FACTS).format(fact=fact)
    
    @classmethod
    def get_activity(cls) -> str:
        return random.choice(cls.ACTIVITIES)
    
    @classmethod
    def get_check_in(cls) -> str:
        return random.choice(cls.CHECK_INS)
    
    @classmethod
    def get_riff(cls, topic: str = "how language shapes thought") -> str:
        return random.choice(cls.RIFFS).format(topic=topic)


class ProactivePolicy:
    """
    Policy layer that decides when and how to be proactive.
    Uses utility-based decision making with controlled randomness.
    """
    
    def __init__(
        self,
        mood_tracker: Optional[MoodTracker] = None,
        randomness: float = 0.3,  # Epsilon for epsilon-greedy
        temperature: float = 1.0   # Softmax temperature
    ):
        self.mood_tracker = mood_tracker
        self.randomness = randomness
        self.temperature = temperature
    
    def should_be_proactive(self, context: ProactiveContext) -> bool:
        """
        Decide if agent should be proactive based on context.
        
        Returns:
            True if agent should initiate interaction
        """
        # Check autonomy budget
        if context.proactive_count_this_hour >= context.max_proactive_per_hour:
            return False
        
        # Don't interrupt if user is actively chatting
        if context.time_since_last_user_msg < 30.0:
            return False
        
        # Calculate proactive probability
        base_prob = 0.3  # Base 10% chance per check
        
        # Increase probability with idle time (up to 5 minutes)
        idle_factor = min(context.time_since_last_user_msg / 300.0, 1.0)
        base_prob += idle_factor * 0.3
        
        # Increase probability with high previous engagement
        engagement_factor = context.recent_engagement * 0.2
        base_prob += engagement_factor
        
        # Mood influence
        if self.mood_tracker:
            mood_state = self.mood_tracker.current_mood.value
            if mood_state in ['playful', 'excited', 'curious']:
                base_prob += 0.15
            elif mood_state == 'calm':
                base_prob -= 0.1
        
        # Cap at reasonable maximum
        base_prob = min(base_prob, 0.8)
        
        return random.random() < base_prob
    
    def decide_action(self, context: ProactiveContext) -> ProactiveAction:
        """
        Decide what type of proactive action to take.
        Uses softmax with utility scores.
        
        Returns:
            The chosen ProactiveAction
        """
        # Calculate utility scores for each action
        utilities = self._calculate_utilities(context)
        
        # Epsilon-greedy: sometimes pick randomly for variety
        if random.random() < self.randomness:
            return random.choice(list(ProactiveAction))
        
        # Softmax selection based on utilities
        action = self._softmax_select(utilities)
        return action
    
    def _calculate_utilities(self, context: ProactiveContext) -> Dict[ProactiveAction, float]:
        """Calculate utility scores for each action type."""
        utilities = {
            ProactiveAction.ASK_QUESTION: 1.0,
            ProactiveAction.SHARE_FACT: 0.7,
            ProactiveAction.SUGGEST_ACTIVITY: 0.8,
            ProactiveAction.TELL_STORY: 0.6,
            ProactiveAction.CHECK_IN: 0.9,
            ProactiveAction.RIFF: 0.5,
            ProactiveAction.SILENT: 0.3,
        }
        
        # Adjust based on idle time
        if context.time_since_last_user_msg > 300:  # 5+ minutes
            utilities[ProactiveAction.CHECK_IN] += 0.5
        
        # Adjust based on engagement
        if context.recent_engagement > 0.7:
            utilities[ProactiveAction.ASK_QUESTION] += 0.3
            utilities[ProactiveAction.SUGGEST_ACTIVITY] += 0.4
        elif context.recent_engagement < 0.3:
            utilities[ProactiveAction.SHARE_FACT] += 0.2
            utilities[ProactiveAction.SILENT] += 0.4
        
        # Adjust based on mood
        if self.mood_tracker:
            mood_state = self.mood_tracker.current_mood.value
            if mood_state == 'playful':
                utilities[ProactiveAction.SUGGEST_ACTIVITY] += 0.4
                utilities[ProactiveAction.RIFF] += 0.3
            elif mood_state == 'curious':
                utilities[ProactiveAction.ASK_QUESTION] += 0.3
                utilities[ProactiveAction.SHARE_FACT] += 0.3
            elif mood_state == 'calm':
                utilities[ProactiveAction.SILENT] += 0.3
        
        # Recent proactive actions - avoid being too frequent
        if context.proactive_count_this_hour > context.max_proactive_per_hour * 0.7:
            utilities[ProactiveAction.SILENT] += 0.5
        
        return utilities
    
    def _softmax_select(self, utilities: Dict[ProactiveAction, float]) -> ProactiveAction:
        """Select action using softmax based on utility scores."""
        import math
        
        actions = list(utilities.keys())
        scores = [utilities[a] / self.temperature for a in actions]
        
        # Compute softmax
        exp_scores = [math.exp(s) for s in scores]
        total = sum(exp_scores)
        probabilities = [e / total for e in exp_scores]
        
        # Sample from distribution
        r = random.random()
        cumsum = 0.0
        for action, prob in zip(actions, probabilities):
            cumsum += prob
            if r <= cumsum:
                return action
        
        return actions[-1]  # Fallback


class ProactiveScheduler:
    """
    Scheduler for proactive agent behavior.
    Runs background task that periodically checks if agent should be proactive.
    """
    
    def __init__(
        self,
        bus: EventBus,
        policy: ProactivePolicy,
        min_interval: float = 30.0,  # Min seconds between checks
        max_interval: float = 120.0,  # Max seconds between checks
        max_per_hour: int = 20,
        enabled: bool = True
    ):
        self.bus = bus
        self.policy = policy
        self.min_interval = min_interval
        self.max_interval = max_interval
        self.max_per_hour = max_per_hour
        self.enabled = enabled
        
        self._task: Optional[asyncio.Task] = None
        self._last_user_msg_time: float = time.time()
        self._last_agent_msg_time: float = time.time()
        self._proactive_count: int = 0
        self._hour_start: float = time.time()
        self._recent_engagement: float = 0.5
        self._interaction_count: int = 0
        
        # Callback for when proactive action should be taken
        self._on_proactive_callback: Optional[Callable] = None
    
    def set_callback(self, callback: Callable):
        """Set callback to be called when proactive action is triggered."""
        self._on_proactive_callback = callback
    
    async def start(self):
        """Start the proactive scheduler."""
        if self._task is not None:
            return
        
        # Subscribe to relevant events
        event_queue = await self.bus.subscribe()
        
        # Start monitoring task
        self._task = asyncio.create_task(self._run(event_queue))
    
    async def stop(self):
        """Stop the proactive scheduler."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
    
    def update_context(
        self,
        last_user_msg_time: Optional[float] = None,
        last_agent_msg_time: Optional[float] = None,
        engagement: Optional[float] = None
    ):
        """Update context information for decision making."""
        if last_user_msg_time is not None:
            self._last_user_msg_time = last_user_msg_time
            self._interaction_count += 1
        
        if last_agent_msg_time is not None:
            self._last_agent_msg_time = last_agent_msg_time
        
        if engagement is not None:
            self._recent_engagement = engagement
    
    def get_context(self) -> ProactiveContext:
        """Build current context for policy decisions."""
        now = time.time()
        
        # Reset hourly counter if needed
        if now - self._hour_start > 3600:
            self._proactive_count = 0
            self._hour_start = now
        
        mood = "neutral"
        if self.policy.mood_tracker:
            mood = self.policy.mood_tracker.current_mood.value
        
        return ProactiveContext(
            time_since_last_user_msg=now - self._last_user_msg_time,
            time_since_last_agent_msg=now - self._last_agent_msg_time,
            recent_engagement=self._recent_engagement,
            mood=mood,
            interaction_count=self._interaction_count,
            proactive_count_this_hour=self._proactive_count,
            max_proactive_per_hour=self.max_per_hour
        )
    
    async def _run(self, event_queue: asyncio.Queue):
        """Main loop for proactive scheduler."""
        while True:
            try:
                # Random interval between checks for variety
                interval = random.uniform(self.min_interval, self.max_interval)
                
                # Wait with timeout to allow event processing
                try:
                    # Check for events with timeout
                    event = await asyncio.wait_for(event_queue.get(), timeout=interval)
                    await self._handle_event(event)
                except asyncio.TimeoutError:
                    # Timeout - time to consider proactive action
                    if self.enabled:
                        await self._check_proactive()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                await self.bus.publish("proactive.error", {"error": str(e)})
                await asyncio.sleep(5)
    
    async def _handle_event(self, event):
        """Handle events that might trigger proactive behavior."""
        # Update context based on events
        if event.type == "agent.input":
            self._last_user_msg_time = time.time()
            self._interaction_count += 1
        elif event.type == "agent.output":
            self._last_agent_msg_time = time.time()
        elif event.type == "tool.toggle" and not self.enabled:
            # Could trigger a proactive response about tool status
            pass
    
    async def _check_proactive(self):
        """Check if agent should be proactive and take action if so."""
        context = self.get_context()
        
        if not self.policy.should_be_proactive(context):
            return
        
        # Decide action
        action = self.policy.decide_action(context)
        
        if action == ProactiveAction.SILENT:
            return
        
        # Increment counter
        self._proactive_count += 1
        
        # Get intent based on action
        intent = self._get_intent_for_action(action)
        
        # Publish event
        await self.bus.publish("proactive.trigger", {
            "action": action.value,
            "intent": intent,
            "context": {
                "idle_time": context.time_since_last_user_msg,
                "mood": context.mood,
                "engagement": context.recent_engagement
            }
        })
        
        # Call callback if set
        if self._on_proactive_callback:
            try:
                await self._on_proactive_callback(action, intent)
            except Exception as e:
                await self.bus.publish("proactive.callback_error", {"error": str(e)})
    
    def _get_intent_for_action(self, action: ProactiveAction) -> str:
        """Generate intent text for the given action type."""
        if action == ProactiveAction.ASK_QUESTION:
            return IntentTemplate.get_question()
        elif action == ProactiveAction.SHARE_FACT:
            return IntentTemplate.get_fun_fact()
        elif action == ProactiveAction.SUGGEST_ACTIVITY:
            return IntentTemplate.get_activity()
        elif action == ProactiveAction.CHECK_IN:
            return IntentTemplate.get_check_in()
        elif action == ProactiveAction.RIFF:
            # Could use memory to get recent topics here
            return IntentTemplate.get_riff()
        elif action == ProactiveAction.TELL_STORY:
            return "Let me tell you a quick story..."
        else:
            return IntentTemplate.get_question()
