"""
Mood and emotion tracking system.
Tracks sentiment from recent interactions and adjusts agent behavior.
"""
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
from collections import deque


class MoodState(Enum):
    """Possible mood states for the agent."""
    EXCITED = "excited"
    HAPPY = "happy"
    NEUTRAL = "neutral"
    CURIOUS = "curious"
    FOCUSED = "focused"
    PLAYFUL = "playful"
    CALM = "calm"


@dataclass
class Interaction:
    """Record of a single interaction with sentiment."""
    timestamp: float
    user_text: str
    sentiment: float  # -1.0 to 1.0
    engagement: float  # 0.0 to 1.0
    
    def age_seconds(self) -> float:
        """How long ago was this interaction."""
        return time.time() - self.timestamp


class MoodTracker:
    """
    Tracks mood based on recent interactions, time of day, and engagement.
    Influences agent tone, talkativeness, and playfulness.
    """
    
    def __init__(self, max_history: int = 20):
        self.max_history = max_history
        self.interactions: deque = deque(maxlen=max_history)
        self.current_mood: MoodState = MoodState.NEUTRAL
        self._last_update: float = time.time()
    
    def update_from_interaction(
        self,
        user_text: str,
        sentiment: Optional[float] = None,
        engagement: Optional[float] = None
    ):
        """
        Update mood based on a new interaction.
        
        Args:
            user_text: The user's message
            sentiment: Sentiment score (-1.0 to 1.0), auto-computed if None
            engagement: Engagement score (0.0 to 1.0), auto-computed if None
        """
        if sentiment is None:
            sentiment = self._estimate_sentiment(user_text)
        if engagement is None:
            engagement = self._estimate_engagement(user_text)
        
        interaction = Interaction(
            timestamp=time.time(),
            user_text=user_text,
            sentiment=sentiment,
            engagement=engagement
        )
        
        self.interactions.append(interaction)
        self._update_mood()
        self._last_update = time.time()
    
    def _estimate_sentiment(self, text: str) -> float:
        """
        Simple sentiment estimation based on keywords.
        Returns value between -1.0 (negative) and 1.0 (positive).
        """
        text_lower = text.lower()
        
        # Positive keywords
        positive_words = [
            'great', 'good', 'nice', 'awesome', 'excellent', 'love', 'like',
            'happy', 'thanks', 'thank', 'wonderful', 'amazing', 'cool', 'fun',
            'interesting', 'excited', 'yay', '!'
        ]
        
        # Negative keywords
        negative_words = [
            'bad', 'terrible', 'awful', 'hate', 'dislike', 'sad', 'angry',
            'frustrated', 'annoying', 'broken', 'error', 'problem', 'issue',
            'wrong', 'fail'
        ]
        
        pos_count = sum(1 for word in positive_words if word in text_lower)
        neg_count = sum(1 for word in negative_words if word in text_lower)
        
        # Multiple exclamation marks = high enthusiasm
        if '!!' in text or '!!!' in text:
            pos_count += 2
        
        total = pos_count + neg_count
        if total == 0:
            return 0.0
        
        sentiment = (pos_count - neg_count) / total
        return max(-1.0, min(1.0, sentiment))
    
    def _estimate_engagement(self, text: str) -> float:
        """
        Estimate engagement level based on message characteristics.
        Returns value between 0.0 (low) and 1.0 (high).
        """
        # Length indicates engagement
        length_score = min(len(text) / 200.0, 1.0)
        
        # Questions indicate engagement
        question_score = 0.3 if '?' in text else 0.0
        
        # Exclamations indicate enthusiasm
        exclaim_score = min(text.count('!') * 0.15, 0.3)
        
        # Combine scores
        engagement = (length_score * 0.5) + question_score + exclaim_score
        return min(engagement, 1.0)
    
    def _update_mood(self):
        """Update current mood based on recent interactions."""
        if not self.interactions:
            self.current_mood = MoodState.NEUTRAL
            return
        
        # Weight recent interactions more heavily
        weighted_sentiment = 0.0
        weighted_engagement = 0.0
        total_weight = 0.0
        
        for i, interaction in enumerate(reversed(self.interactions)):
            # Recent interactions get higher weight
            weight = 1.0 / (i + 1)
            weighted_sentiment += interaction.sentiment * weight
            weighted_engagement += interaction.engagement * weight
            total_weight += weight
        
        avg_sentiment = weighted_sentiment / total_weight
        avg_engagement = weighted_engagement / total_weight
        
        # Time of day influence
        time_of_day_factor = self._get_time_of_day_factor()
        
        # Determine mood based on sentiment and engagement
        if avg_sentiment > 0.5 and avg_engagement > 0.6:
            self.current_mood = MoodState.EXCITED
        elif avg_sentiment > 0.3:
            self.current_mood = MoodState.HAPPY
        elif avg_engagement > 0.7:
            self.current_mood = MoodState.CURIOUS
        elif avg_engagement > 0.5 and avg_sentiment > -0.2:
            self.current_mood = MoodState.FOCUSED
        elif time_of_day_factor > 0.6:
            self.current_mood = MoodState.PLAYFUL
        elif avg_sentiment < -0.3:
            self.current_mood = MoodState.CALM  # Be calming when user is negative
        else:
            self.current_mood = MoodState.NEUTRAL
    
    def _get_time_of_day_factor(self) -> float:
        """
        Get a factor based on time of day.
        Morning/evening might be more playful, afternoon more focused.
        Returns 0.0 to 1.0.
        """
        from datetime import datetime
        hour = datetime.now().hour
        
        # Morning (6-9): moderate playfulness
        if 6 <= hour < 9:
            return 0.5
        # Midday (9-17): more focused
        elif 9 <= hour < 17:
            return 0.3
        # Evening (17-22): more playful
        elif 17 <= hour < 22:
            return 0.7
        # Late night (22-6): calm
        else:
            return 0.4
    
    def get_mood_influence(self) -> Dict[str, float]:
        """
        Get mood influence on personality drives.
        Returns adjustments to apply to base drives.
        """
        influence = {
            "playfulness_modifier": 0.0,
            "talkativeness_modifier": 0.0,
            "curiosity_modifier": 0.0
        }
        
        if self.current_mood == MoodState.EXCITED:
            influence["playfulness_modifier"] = 0.2
            influence["talkativeness_modifier"] = 0.2
            influence["curiosity_modifier"] = 0.1
        elif self.current_mood == MoodState.HAPPY:
            influence["playfulness_modifier"] = 0.1
            influence["talkativeness_modifier"] = 0.1
        elif self.current_mood == MoodState.CURIOUS:
            influence["curiosity_modifier"] = 0.3
            influence["talkativeness_modifier"] = 0.1
        elif self.current_mood == MoodState.FOCUSED:
            influence["playfulness_modifier"] = -0.1
            influence["talkativeness_modifier"] = -0.1
        elif self.current_mood == MoodState.PLAYFUL:
            influence["playfulness_modifier"] = 0.3
            influence["curiosity_modifier"] = 0.1
        elif self.current_mood == MoodState.CALM:
            influence["playfulness_modifier"] = -0.2
            influence["talkativeness_modifier"] = -0.1
        
        return influence
    
    def get_mood_description(self) -> str:
        """Get a human-readable description of the current mood."""
        mood_descriptions = {
            MoodState.EXCITED: "excited and energetic",
            MoodState.HAPPY: "happy and positive",
            MoodState.NEUTRAL: "neutral and balanced",
            MoodState.CURIOUS: "curious and inquisitive",
            MoodState.FOCUSED: "focused and attentive",
            MoodState.PLAYFUL: "playful and fun",
            MoodState.CALM: "calm and composed"
        }
        return mood_descriptions.get(self.current_mood, "neutral")
    
    def get_state(self) -> Dict[str, Any]:
        """Get current mood state as dictionary."""
        recent_sentiment = 0.0
        recent_engagement = 0.0
        
        if self.interactions:
            recent = list(self.interactions)[-5:]  # Last 5 interactions
            recent_sentiment = sum(i.sentiment for i in recent) / len(recent)
            recent_engagement = sum(i.engagement for i in recent) / len(recent)
        
        return {
            "mood": self.current_mood.value,
            "mood_description": self.get_mood_description(),
            "recent_sentiment": round(recent_sentiment, 2),
            "recent_engagement": round(recent_engagement, 2),
            "interaction_count": len(self.interactions),
            "time_since_update": round(time.time() - self._last_update, 1)
        }
