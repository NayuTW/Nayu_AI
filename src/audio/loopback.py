"""
Audio device discovery and capture for PipeWire/PulseAudio.
Provides async capture from monitor sources (Discord output) and microphone.
"""
import asyncio
import logging
import struct
from typing import Optional, AsyncIterator, Dict, List

logger = logging.getLogger(__name__)

try:
    import sounddevice as sd
    import numpy as np
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False
    logger.warning("sounddevice not available, audio capture disabled")

try:
    import pulsectl
    PULSECTL_AVAILABLE = True
except ImportError:
    PULSECTL_AVAILABLE = False
    logger.warning("pulsectl not available, device discovery limited")


def list_audio_devices() -> Dict[str, List[Dict[str, any]]]:
    """
    List available audio devices for input/output and monitor sources.
    Returns dict with 'inputs', 'outputs', and 'monitors' keys.
    """
    devices = {"inputs": [], "outputs": [], "monitors": []}
    
    if not SOUNDDEVICE_AVAILABLE:
        return devices
    
    try:
        sd_devices = sd.query_devices()
        for idx, dev in enumerate(sd_devices):
            # Determine channel count (prefer input channels, fallback to output)
            channels = dev["max_input_channels"] if dev["max_input_channels"] > 0 else dev["max_output_channels"]
            
            dev_info = {
                "index": idx,
                "name": dev["name"],
                "channels": channels,
                "sample_rate": int(dev["default_samplerate"]),
            }
            
            if dev["max_input_channels"] > 0:
                # Check if it's a monitor source
                if "monitor" in dev["name"].lower():
                    devices["monitors"].append(dev_info)
                else:
                    devices["inputs"].append(dev_info)
            
            if dev["max_output_channels"] > 0:
                devices["outputs"].append(dev_info)
    except Exception as e:
        logger.exception(f"Error listing devices: {e}")
    
    # Try pulsectl for better monitor source detection
    if PULSECTL_AVAILABLE:
        try:
            with pulsectl.Pulse("nayu-device-list") as pulse:
                for source in pulse.source_list():
                    if "monitor" in source.name.lower():
                        devices["monitors"].append({
                            "name": source.name,
                            "description": source.description,
                            "index": source.index,
                        })
        except Exception as e:
            logger.warning(f"pulsectl device listing failed: {e}")
    
    return devices


class LoopbackCapture:
    """
    Async capture from a PulseAudio/PipeWire monitor source (e.g., Discord output).
    Yields mono int16 PCM frames at specified frame duration.
    """
    
    def __init__(
        self,
        monitor_name: Optional[str] = None,
        sample_rate: int = 48000,
        frame_ms: int = 20,
    ):
        """
        Args:
            monitor_name: Device name or index. If None, uses default.
            sample_rate: Sample rate in Hz (default 48000).
            frame_ms: Frame duration in milliseconds (default 20ms for VAD).
        """
        self.monitor_name = monitor_name
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_samples = int(sample_rate * frame_ms / 1000)
        self.running = False
        self._queue: Optional[asyncio.Queue] = None
        
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError("sounddevice not available")
    
    async def start(self) -> None:
        """Start audio capture."""
        if self.running:
            return
        
        self.running = True
        self._queue = asyncio.Queue(maxsize=100)
        
        # Start capture in background
        asyncio.create_task(self._capture_loop())
        logger.info(f"LoopbackCapture started: {self.monitor_name} @ {self.sample_rate}Hz")
    
    async def stop(self) -> None:
        """Stop audio capture."""
        self.running = False
        logger.info("LoopbackCapture stopped")
    
    async def frames(self) -> AsyncIterator[bytes]:
        """
        Async generator yielding mono int16 PCM frames.
        Each frame is frame_ms duration worth of samples.
        """
        if not self.running:
            raise RuntimeError("Capture not started")
        
        while self.running:
            try:
                frame = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield frame
            except asyncio.TimeoutError:
                continue
    
    async def _capture_loop(self) -> None:
        """Background task that captures audio and enqueues frames."""
        loop = asyncio.get_running_loop()
        
        def callback(indata, frames, time_info, status):
            """Called by sounddevice for each audio block."""
            if status:
                logger.warning(f"Audio callback status: {status}")
            
            # Convert to mono if needed
            if indata.ndim > 1:
                audio = indata.mean(axis=1)
            else:
                audio = indata.flatten()
            
            # Convert to int16
            audio_int16 = (audio * 32767).astype(np.int16)
            
            # Enqueue frame
            if self._queue and not self._queue.full():
                try:
                    loop.call_soon_threadsafe(
                        self._queue.put_nowait,
                        audio_int16.tobytes()
                    )
                except Exception:
                    pass
        
        try:
            # Determine device
            device = None
            if self.monitor_name:
                # Try to find device by name or use as index
                try:
                    device = int(self.monitor_name)
                except ValueError:
                    device = self.monitor_name
            
            with sd.InputStream(
                device=device,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.frame_samples,
                dtype=np.float32,
                callback=callback,
            ):
                while self.running:
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.exception(f"LoopbackCapture error: {e}")
            self.running = False


class MicCapture:
    """
    Async capture from user microphone.
    Similar to LoopbackCapture but explicitly for mic input.
    """
    
    def __init__(
        self,
        mic_name: Optional[str] = None,
        sample_rate: int = 48000,
        frame_ms: int = 20,
    ):
        """
        Args:
            mic_name: Device name or index. If None, uses default input.
            sample_rate: Sample rate in Hz (default 48000).
            frame_ms: Frame duration in milliseconds (default 20ms).
        """
        self.mic_name = mic_name
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_samples = int(sample_rate * frame_ms / 1000)
        self.running = False
        self._queue: Optional[asyncio.Queue] = None
        
        if not SOUNDDEVICE_AVAILABLE:
            raise RuntimeError("sounddevice not available")
    
    async def start(self) -> None:
        """Start microphone capture."""
        if self.running:
            return
        
        self.running = True
        self._queue = asyncio.Queue(maxsize=100)
        
        # Start capture in background
        asyncio.create_task(self._capture_loop())
        logger.info(f"MicCapture started: {self.mic_name} @ {self.sample_rate}Hz")
    
    async def stop(self) -> None:
        """Stop microphone capture."""
        self.running = False
        logger.info("MicCapture stopped")
    
    async def frames(self) -> AsyncIterator[bytes]:
        """
        Async generator yielding mono int16 PCM frames.
        Each frame is frame_ms duration worth of samples.
        """
        if not self.running:
            raise RuntimeError("Capture not started")
        
        while self.running:
            try:
                frame = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                yield frame
            except asyncio.TimeoutError:
                continue
    
    async def _capture_loop(self) -> None:
        """Background task that captures audio and enqueues frames."""
        loop = asyncio.get_running_loop()
        
        def callback(indata, frames, time_info, status):
            """Called by sounddevice for each audio block."""
            if status:
                logger.warning(f"Mic callback status: {status}")
            
            # Convert to mono if needed
            if indata.ndim > 1:
                audio = indata.mean(axis=1)
            else:
                audio = indata.flatten()
            
            # Convert to int16
            audio_int16 = (audio * 32767).astype(np.int16)
            
            # Enqueue frame
            if self._queue and not self._queue.full():
                try:
                    loop.call_soon_threadsafe(
                        self._queue.put_nowait,
                        audio_int16.tobytes()
                    )
                except Exception:
                    pass
        
        try:
            # Determine device
            device = None
            if self.mic_name:
                try:
                    device = int(self.mic_name)
                except ValueError:
                    device = self.mic_name
            
            with sd.InputStream(
                device=device,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.frame_samples,
                dtype=np.float32,
                callback=callback,
            ):
                while self.running:
                    await asyncio.sleep(0.1)
        except Exception as e:
            logger.exception(f"MicCapture error: {e}")
            self.running = False
