"""
Voice session orchestrator.
Coordinates audio capture, VAD, STT, TTS, and mixing for live voice interaction.
"""
import asyncio
import logging
import os
from typing import Optional, Callable, Awaitable

logger = logging.getLogger(__name__)


class VoiceSession:
    """
    Orchestrates live voice session with Discord call participants.
    Handles:
    - Capture of Discord output (remote participants)
    - Capture of user microphone (optional)
    - VAD and streaming STT
    - TTS playback via mixer
    - Turn-taking and interruption
    """
    
    def __init__(
        self,
        event_bus,
        speech_tool,
        store,
        enable_user_mic: bool = False,
    ):
        """
        Args:
            event_bus: EventBus for publishing transcript events.
            speech_tool: SpeechSmolTool for TTS.
            store: SQLiteStore for settings.
            enable_user_mic: Whether to capture and transcribe user mic.
        """
        self.bus = event_bus
        self.speech_tool = speech_tool
        self.store = store
        self.enable_user_mic = enable_user_mic
        
        # Audio components
        self.loopback_capture = None
        self.mic_capture = None
        self.vad = None
        self.stt = None
        self.mixer = None
        
        # State
        self.running = False
        self._tasks = []
        
        # Configuration from env/settings
        self.discord_monitor = os.getenv("DISCORD_OUTPUT_MONITOR")
        self.user_mic_source = os.getenv("USER_MIC_SOURCE")
        self.virtual_sink = os.getenv("VIRTUAL_SINK_OUTPUT")
        self.vad_aggressiveness = int(os.getenv("VAD_AGGRESSIVENESS", "2"))
        self.ducking_db = float(os.getenv("DUCKING_DB", "-12.0"))
        
        # Callback for transcript events
        self.on_transcript: Optional[Callable[[str, str], Awaitable[None]]] = None
        
        logger.info("VoiceSession initialized")
    
    async def start(self) -> bool:
        """
        Start the voice session.
        
        Returns:
            True if started successfully, False otherwise.
        """
        if self.running:
            logger.warning("VoiceSession already running")
            return True
        
        try:
            # Import audio modules
            from src.audio.loopback import LoopbackCapture, MicCapture, list_audio_devices
            from src.audio.vad import VAD, FrameRingBuffer
            from src.audio.stt_stream import StreamingSTT
            from src.audio.mixer import AudioMixer
            
            # Check configuration
            if not self.discord_monitor:
                logger.error("DISCORD_OUTPUT_MONITOR not set")
                return False
            
            # List available devices for debugging
            devices = list_audio_devices()
            logger.info(f"Available monitors: {[d['name'] for d in devices.get('monitors', [])]}")
            logger.info(f"Available inputs: {[d['name'] for d in devices.get('inputs', [])]}")
            
            # Initialize components
            logger.info("Initializing audio components...")
            
            # Loopback capture (Discord output)
            self.loopback_capture = LoopbackCapture(
                monitor_name=self.discord_monitor,
                sample_rate=48000,
                frame_ms=20,
            )
            
            # Mic capture (optional)
            if self.enable_user_mic and self.user_mic_source:
                self.mic_capture = MicCapture(
                    mic_name=self.user_mic_source,
                    sample_rate=48000,
                    frame_ms=20,
                )
            
            # VAD
            self.vad = VAD(
                sample_rate=48000,
                frame_ms=20,
                aggressiveness=self.vad_aggressiveness,
            )
            
            # STT
            self.stt = StreamingSTT(
                model_size="small.en",
                sample_rate=48000,
            )
            
            # Mixer (if virtual sink configured)
            if self.virtual_sink:
                self.mixer = AudioMixer(
                    output_device=self.virtual_sink,
                    sample_rate=48000,
                    frame_ms=20,
                    ducking_db=self.ducking_db,
                )
            
            # Start components
            logger.info("Starting audio components...")
            await self.loopback_capture.start()
            
            if self.mic_capture:
                await self.mic_capture.start()
            
            await self.stt.start()
            
            if self.mixer:
                await self.mixer.start()
            
            # Start processing tasks
            self.running = True
            self._tasks.append(asyncio.create_task(self._process_loopback()))
            
            if self.mic_capture:
                self._tasks.append(asyncio.create_task(self._process_mic()))
            
            logger.info("VoiceSession started successfully")
            await self.bus.publish("voice.session.started", {
                "discord_monitor": self.discord_monitor,
                "user_mic": self.user_mic_source if self.enable_user_mic else None,
            })
            
            return True
        
        except Exception as e:
            logger.exception(f"Failed to start VoiceSession: {e}")
            await self.stop()
            return False
    
    async def stop(self) -> None:
        """Stop the voice session."""
        if not self.running:
            return
        
        logger.info("Stopping VoiceSession...")
        self.running = False
        
        # Cancel tasks
        for task in self._tasks:
            task.cancel()
        
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        
        # Stop components
        if self.loopback_capture:
            await self.loopback_capture.stop()
        
        if self.mic_capture:
            await self.mic_capture.stop()
        
        if self.stt:
            await self.stt.stop()
        
        if self.mixer:
            await self.mixer.stop()
        
        logger.info("VoiceSession stopped")
        await self.bus.publish("voice.session.stopped", {})
    
    async def _process_loopback(self) -> None:
        """Process loopback capture (Discord output) with VAD and STT."""
        from src.audio.vad import FrameRingBuffer
        
        ring_buffer = FrameRingBuffer(
            vad=self.vad,
            speech_pad_frames=10,
            silence_pad_frames=15,
            min_speech_frames=5,
        )
        
        try:
            async for frame in self.loopback_capture.frames():
                if not self.running:
                    break
                
                # Process frame through VAD
                utterance = ring_buffer.process_frame(frame)
                
                if utterance:
                    # Complete utterance detected - transcribe
                    logger.debug("Transcribing remote utterance...")
                    try:
                        result = await self.stt.transcribe(utterance, speaker_label="remote")
                        text = result.get("text", "").strip()
                        
                        if text:
                            logger.info(f"Remote: {text}")
                            
                            # Publish transcript event
                            await self.bus.publish("voice.transcript", {
                                "speaker": "remote",
                                "text": text,
                                "duration": result.get("duration", 0),
                            })
                            
                            # Call callback if set
                            if self.on_transcript:
                                await self.on_transcript(text, "remote")
                    except Exception as e:
                        logger.exception(f"STT error: {e}")
        except Exception as e:
            logger.exception(f"Loopback processing error: {e}")
    
    async def _process_mic(self) -> None:
        """Process mic capture with VAD and STT."""
        from src.audio.vad import FrameRingBuffer
        
        ring_buffer = FrameRingBuffer(
            vad=self.vad,
            speech_pad_frames=10,
            silence_pad_frames=15,
            min_speech_frames=5,
        )
        
        try:
            async for frame in self.mic_capture.frames():
                if not self.running:
                    break
                
                # Forward to mixer if available
                if self.mixer:
                    await self.mixer.enqueue_mic(frame)
                
                # Process frame through VAD
                utterance = ring_buffer.process_frame(frame)
                
                if utterance:
                    # User speech detected - interrupt AI if speaking
                    if self.mixer and self.mixer.is_ai_speaking():
                        logger.info("User interrupt detected, stopping AI")
                        self.mixer.clear_tts_queue()
                        await self.bus.publish("voice.interrupt", {
                            "speaker": "user",
                        })
                    
                    # Transcribe
                    logger.debug("Transcribing user utterance...")
                    try:
                        result = await self.stt.transcribe(utterance, speaker_label="user")
                        text = result.get("text", "").strip()
                        
                        if text:
                            logger.info(f"User: {text}")
                            
                            # Publish transcript event
                            await self.bus.publish("voice.transcript", {
                                "speaker": "user",
                                "text": text,
                                "duration": result.get("duration", 0),
                            })
                            
                            # Call callback if set
                            if self.on_transcript:
                                await self.on_transcript(text, "user")
                    except Exception as e:
                        logger.exception(f"STT error: {e}")
        except Exception as e:
            logger.exception(f"Mic processing error: {e}")
    
    async def speak(self, text: str) -> None:
        """
        Generate TTS and enqueue to mixer.
        
        Args:
            text: Text to speak.
        """
        if not self.mixer:
            logger.warning("Mixer not available, cannot speak")
            return
        
        try:
            # Generate TTS audio
            # Note: This is a simplified version. Ideally, speech_tool should
            # support streaming frames instead of generating complete WAV files.
            # For now, we'll just log the intent.
            logger.info(f"AI would speak: {text}")
            
            # In a full implementation, you would:
            # 1. Generate TTS audio chunks
            # 2. Split into 20ms frames
            # 3. Enqueue to mixer.tts_queue
            
            # Placeholder: Mark AI as speaking
            await self.bus.publish("voice.ai.speaking", {"text": text})
        except Exception as e:
            logger.exception(f"TTS error: {e}")
