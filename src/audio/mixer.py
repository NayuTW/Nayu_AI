"""
Audio mixer that combines user mic and AI TTS into a virtual microphone.
Supports ducking (reducing mic volume when AI speaks).
"""
import asyncio
import logging
import numpy as np
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logger.warning("sounddevice not available, mixer disabled")


class AudioMixer:
    """
    Mix user mic and AI TTS audio into a virtual microphone sink.
    Provides ducking to reduce mic volume when AI speaks.
    """
    
    def __init__(
        self,
        output_device: Optional[str] = None,
        sample_rate: int = 48000,
        frame_ms: int = 20,
        ducking_db: float = -12.0,
    ):
        """
        Args:
            output_device: Output device name/index (virtual sink for Discord).
            sample_rate: Sample rate in Hz.
            frame_ms: Frame duration in ms.
            ducking_db: dB reduction for mic when AI speaks (negative value).
        """
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError("sounddevice not available")
        
        self.output_device = output_device
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_samples = int(sample_rate * frame_ms / 1000)
        self.ducking_db = ducking_db
        self.ducking_factor = 10 ** (ducking_db / 20)  # Convert dB to linear
        
        # Audio queues
        self.mic_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.tts_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        
        # State
        self.running = False
        self._mix_task: Optional[asyncio.Task] = None
        self._ai_speaking = False
        
        logger.info(f"AudioMixer initialized: {sample_rate}Hz, ducking={ducking_db}dB")
    
    async def start(self) -> None:
        """Start the mixer."""
        if self.running:
            return
        
        self.running = True
        self._mix_task = asyncio.create_task(self._mix_loop())
        logger.info("AudioMixer started")
    
    async def stop(self) -> None:
        """Stop the mixer."""
        self.running = False
        if self._mix_task:
            self._mix_task.cancel()
            try:
                await self._mix_task
            except asyncio.CancelledError:
                pass
        logger.info("AudioMixer stopped")
    
    async def enqueue_mic(self, frame: bytes) -> None:
        """
        Enqueue a mic frame for mixing.
        
        Args:
            frame: Raw PCM audio frame (int16).
        """
        if not self.mic_queue.full():
            try:
                self.mic_queue.put_nowait(frame)
            except asyncio.QueueFull:
                pass
    
    async def enqueue_tts(self, frame: bytes) -> None:
        """
        Enqueue a TTS frame for mixing.
        
        Args:
            frame: Raw PCM audio frame (int16).
        """
        if not self.tts_queue.full():
            try:
                self.tts_queue.put_nowait(frame)
                self._ai_speaking = True
            except asyncio.QueueFull:
                pass
    
    def clear_tts_queue(self) -> None:
        """
        Clear TTS queue (for interruption).
        """
        while not self.tts_queue.empty():
            try:
                self.tts_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        self._ai_speaking = False
        logger.debug("TTS queue cleared")
    
    async def _mix_loop(self) -> None:
        """
        Background mixing loop.
        Combines mic and TTS, applies ducking, and outputs to device.
        """
        loop = asyncio.get_running_loop()
        
        # Prepare output stream
        try:
            # Determine output device
            device = None
            if self.output_device:
                try:
                    device = int(self.output_device)
                except ValueError:
                    device = self.output_device
            
            with sd.OutputStream(
                device=device,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.frame_samples,
                dtype=np.int16,
            ) as stream:
                while self.running:
                    # Get frames (with timeout to allow checking running flag)
                    mic_frame = None
                    tts_frame = None
                    
                    try:
                        mic_frame = await asyncio.wait_for(
                            self.mic_queue.get(),
                            timeout=0.02,  # 20ms
                        )
                    except asyncio.TimeoutError:
                        pass
                    
                    try:
                        tts_frame = self.tts_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass
                    
                    # Check if AI still speaking
                    if tts_frame is None and self._ai_speaking:
                        self._ai_speaking = False
                        logger.debug("AI stopped speaking")
                    
                    # Mix frames
                    if mic_frame or tts_frame:
                        mixed = self._mix_frames(mic_frame, tts_frame)
                        
                        # Write to output
                        if mixed is not None:
                            stream.write(mixed)
                    else:
                        # No audio, write silence
                        silence = np.zeros(self.frame_samples, dtype=np.int16)
                        stream.write(silence)
                        await asyncio.sleep(0.001)
        except Exception as e:
            logger.exception(f"Mixer error: {e}")
            self.running = False
    
    def _mix_frames(
        self,
        mic_frame: Optional[bytes],
        tts_frame: Optional[bytes],
    ) -> Optional[np.ndarray]:
        """
        Mix mic and TTS frames with ducking.
        
        Args:
            mic_frame: Mic frame (int16 PCM).
            tts_frame: TTS frame (int16 PCM).
        
        Returns:
            Mixed frame as numpy array (int16).
        """
        # Convert to numpy arrays
        mic_audio = None
        tts_audio = None
        
        if mic_frame:
            mic_audio = np.frombuffer(mic_frame, dtype=np.int16).astype(np.float32)
        
        if tts_frame:
            tts_audio = np.frombuffer(tts_frame, dtype=np.int16).astype(np.float32)
        
        # Apply ducking if AI speaking
        if mic_audio is not None and self._ai_speaking:
            mic_audio *= self.ducking_factor
        
        # Mix
        if mic_audio is not None and tts_audio is not None:
            # Ensure same length
            min_len = min(len(mic_audio), len(tts_audio))
            mixed = mic_audio[:min_len] + tts_audio[:min_len]
        elif mic_audio is not None:
            mixed = mic_audio
        elif tts_audio is not None:
            mixed = tts_audio
        else:
            return None
        
        # Clip and convert back to int16
        mixed = np.clip(mixed, -32768, 32767).astype(np.int16)
        
        return mixed
