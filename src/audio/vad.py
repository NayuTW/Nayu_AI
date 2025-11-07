"""
Voice Activity Detection using webrtcvad.
Detects speech vs silence in audio frames and accumulates utterances.
"""
import logging
from collections import deque
from typing import Optional, List

logger = logging.getLogger(__name__)

try:
    import webrtcvad
    WEBRTCVAD_AVAILABLE = True
except ImportError:
    WEBRTCVAD_AVAILABLE = False
    logger.warning("webrtcvad not available, VAD disabled")


class VAD:
    """
    Voice Activity Detector using webrtcvad.
    Supports 8kHz, 16kHz, 32kHz, or 48kHz sample rates.
    Frame duration must be 10, 20, or 30ms.
    """
    
    def __init__(
        self,
        sample_rate: int = 48000,
        frame_ms: int = 20,
        aggressiveness: int = 2,
    ):
        """
        Args:
            sample_rate: Audio sample rate (8000, 16000, 32000, or 48000).
            frame_ms: Frame duration in ms (10, 20, or 30).
            aggressiveness: VAD aggressiveness (0-3), higher = more aggressive filtering.
        """
        if not WEBRTCVAD_AVAILABLE:
            raise RuntimeError("webrtcvad not installed")
        
        if sample_rate not in (8000, 16000, 32000, 48000):
            raise ValueError(f"Invalid sample rate: {sample_rate}. Must be 8k, 16k, 32k, or 48k")
        
        if frame_ms not in (10, 20, 30):
            raise ValueError(f"Invalid frame_ms: {frame_ms}. Must be 10, 20, or 30")
        
        if not (0 <= aggressiveness <= 3):
            raise ValueError(f"Invalid aggressiveness: {aggressiveness}. Must be 0-3")
        
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.aggressiveness = aggressiveness
        
        self.vad = webrtcvad.Vad(aggressiveness)
        logger.info(f"VAD initialized: {sample_rate}Hz, {frame_ms}ms, aggressiveness={aggressiveness}")
    
    def is_speech(self, frame_bytes: bytes) -> bool:
        """
        Determine if frame contains speech.
        
        Args:
            frame_bytes: Raw PCM audio frame (int16).
        
        Returns:
            True if speech detected, False otherwise.
        """
        try:
            return self.vad.is_speech(frame_bytes, self.sample_rate)
        except Exception as e:
            logger.warning(f"VAD error: {e}")
            return False


class FrameRingBuffer:
    """
    Ring buffer for accumulating audio frames into utterances.
    Handles speech onset/offset detection with padding.
    """
    
    def __init__(
        self,
        vad: VAD,
        speech_pad_frames: int = 10,
        silence_pad_frames: int = 10,
        min_speech_frames: int = 5,
    ):
        """
        Args:
            vad: VAD instance.
            speech_pad_frames: Number of frames to include before speech onset.
            silence_pad_frames: Number of silence frames before considering speech ended.
            min_speech_frames: Minimum consecutive speech frames to trigger onset.
        """
        self.vad = vad
        self.speech_pad_frames = speech_pad_frames
        self.silence_pad_frames = silence_pad_frames
        self.min_speech_frames = min_speech_frames
        
        # Ring buffer for pre-speech padding
        self._ring_buffer: deque = deque(maxlen=speech_pad_frames)
        
        # Utterance accumulator
        self._utterance_frames: List[bytes] = []
        
        # State tracking
        self._triggered = False  # Are we currently in a speech segment?
        self._silence_count = 0  # Consecutive silence frames
        self._speech_count = 0   # Consecutive speech frames
    
    def process_frame(self, frame: bytes) -> Optional[bytes]:
        """
        Process a single audio frame.
        
        Args:
            frame: Raw PCM audio frame (int16).
        
        Returns:
            Complete utterance (concatenated frames) if speech ended, None otherwise.
        """
        is_speech = self.vad.is_speech(frame)
        
        if not self._triggered:
            # Not in speech segment - look for onset
            self._ring_buffer.append(frame)
            
            if is_speech:
                self._speech_count += 1
                if self._speech_count >= self.min_speech_frames:
                    # Speech onset detected
                    self._triggered = True
                    self._speech_count = 0
                    self._silence_count = 0
                    
                    # Start utterance with ring buffer contents
                    self._utterance_frames = list(self._ring_buffer)
                    logger.debug("Speech onset detected")
            else:
                self._speech_count = 0
        else:
            # In speech segment - look for offset
            self._utterance_frames.append(frame)
            
            if not is_speech:
                self._silence_count += 1
                
                if self._silence_count >= self.silence_pad_frames:
                    # Speech offset detected - return complete utterance
                    self._triggered = False
                    self._silence_count = 0
                    self._speech_count = 0
                    
                    utterance = b"".join(self._utterance_frames)
                    self._utterance_frames = []
                    logger.debug(f"Speech offset detected, utterance: {len(utterance)} bytes")
                    return utterance
            else:
                self._silence_count = 0
        
        return None
    
    def flush(self) -> Optional[bytes]:
        """
        Flush any remaining utterance.
        Call this when stopping capture.
        
        Returns:
            Remaining utterance if any, None otherwise.
        """
        if self._utterance_frames:
            utterance = b"".join(self._utterance_frames)
            self._utterance_frames = []
            self._triggered = False
            self._silence_count = 0
            self._speech_count = 0
            logger.debug(f"Flushed utterance: {len(utterance)} bytes")
            return utterance
        return None
