"""
Streaming speech-to-text using faster-whisper.
Transcribes utterances as they become available from VAD.
"""
import asyncio
import logging
import io
import struct
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False
    logger.warning("faster-whisper not available, STT disabled")


class StreamingSTT:
    """
    Streaming speech-to-text engine.
    Transcribes PCM audio utterances on-demand.
    """
    
    def __init__(
        self,
        model_size: str = "small.en",
        sample_rate: int = 48000,
        compute_type: str = "int8_float16",
    ):
        """
        Args:
            model_size: Whisper model size (tiny, base, small, medium, large).
            sample_rate: Audio sample rate.
            compute_type: Compute type for faster-whisper.
        """
        if not WHISPER_AVAILABLE:
            raise RuntimeError("faster-whisper not installed")
        
        self.sample_rate = sample_rate
        self.model_size = model_size
        
        logger.info(f"Initializing Whisper model: {model_size}")
        self.model = WhisperModel(model_size, compute_type=compute_type)
        logger.info("Whisper model ready")
        
        # Queue for transcription requests
        self._queue: asyncio.Queue = asyncio.Queue()
        self._results: Dict[int, asyncio.Queue] = {}
        self._next_id = 0
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None
    
    async def start(self) -> None:
        """Start the transcription worker."""
        if self._running:
            return
        
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("StreamingSTT worker started")
    
    async def stop(self) -> None:
        """Stop the transcription worker."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        logger.info("StreamingSTT worker stopped")
    
    async def transcribe(
        self,
        audio_bytes: bytes,
        speaker_label: str = "unknown",
    ) -> Dict[str, Any]:
        """
        Transcribe an audio utterance.
        
        Args:
            audio_bytes: Raw PCM audio (int16).
            speaker_label: Label for speaker (e.g., "remote", "user").
        
        Returns:
            Dict with 'text', 'speaker', and other metadata.
        """
        if not self._running:
            raise RuntimeError("StreamingSTT not started")
        
        # Create result queue for this request
        request_id = self._next_id
        self._next_id += 1
        result_queue = asyncio.Queue(maxsize=1)
        self._results[request_id] = result_queue
        
        # Enqueue transcription request
        await self._queue.put({
            "id": request_id,
            "audio": audio_bytes,
            "speaker": speaker_label,
        })
        
        # Wait for result
        try:
            result = await asyncio.wait_for(result_queue.get(), timeout=30.0)
            return result
        finally:
            self._results.pop(request_id, None)
    
    async def _worker(self) -> None:
        """Background worker that processes transcription requests."""
        loop = asyncio.get_running_loop()
        
        while self._running:
            try:
                # Get next request
                request = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            
            request_id = request["id"]
            audio_bytes = request["audio"]
            speaker = request["speaker"]
            
            try:
                # Run transcription in thread pool (CPU-bound)
                result = await loop.run_in_executor(
                    None,
                    self._transcribe_sync,
                    audio_bytes,
                    speaker,
                )
                
                # Send result back
                result_queue = self._results.get(request_id)
                if result_queue:
                    try:
                        result_queue.put_nowait(result)
                    except asyncio.QueueFull:
                        pass
            except Exception as e:
                logger.exception(f"Transcription error: {e}")
                # Send error result
                result_queue = self._results.get(request_id)
                if result_queue:
                    try:
                        result_queue.put_nowait({
                            "text": "",
                            "speaker": speaker,
                            "error": str(e),
                        })
                    except asyncio.QueueFull:
                        pass
    
    def _transcribe_sync(
        self,
        audio_bytes: bytes,
        speaker: str,
    ) -> Dict[str, Any]:
        """
        Synchronous transcription (runs in thread pool).
        
        Args:
            audio_bytes: Raw PCM audio (int16).
            speaker: Speaker label.
        
        Returns:
            Dict with transcription results.
        """
        # Convert bytes to numpy array
        import numpy as np
        
        # Decode int16 PCM
        audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
        
        # Convert to float32 [-1, 1]
        audio_float32 = audio_int16.astype(np.float32) / 32768.0
        
        # Transcribe with low beam size for speed
        segments, info = self.model.transcribe(
            audio_float32,
            beam_size=1,
            vad_filter=False,  # Already VAD-filtered
            language="en",
        )
        
        # Collect transcript
        transcript_parts = []
        for segment in segments:
            transcript_parts.append(segment.text)
        
        transcript = "".join(transcript_parts).strip()
        
        return {
            "text": transcript,
            "speaker": speaker,
            "language": info.language if hasattr(info, "language") else "en",
            "duration": len(audio_bytes) / 2 / self.sample_rate,  # int16 = 2 bytes per sample
        }
