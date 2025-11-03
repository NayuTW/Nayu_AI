"""
SpeechTool converted to smolagents Tool class.
Handles speech-to-text and text-to-speech.
"""
import os
from typing import Optional
from smolagents import Tool

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

try:
    from neuttsair.neutts import NeuTTSAir
    import soundfile as sf
    import torch
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False


class SpeechSmolTool(Tool):
    """
    Transcribe audio files or generate speech from text.
    """
    name = "speech"
    description = (
        "Generate spoken audio from text (text-to-speech) or transcribe audio files to text (speech-to-text). "
        "Use action='speak' to generate audio output from text. "
        "Use action='transcribe' to convert audio files to text."
    )
    inputs = {
        "action": {
            "type": "string",
            "description": "Action: 'transcribe' for STT or 'speak' for TTS"
        },
        "path": {
            "type": "string",
            "description": "Path to audio file (for transcribe action)",
            "nullable": True
        },
        "text": {
            "type": "string",
            "description": "Text to speak (for speak action)",
            "nullable": True
        }
    }
    output_type = "string"
    
    def __init__(
        self,
        stt_model_size: str = "small.en",
        tts_ref_audio: str = "",
        tts_ref_text: str = ""
    ):
        super().__init__()
        
        # Initialize STT
        if not WHISPER_AVAILABLE:
            self.stt = None
        else:
            self.stt = WhisperModel(stt_model_size, compute_type="int8_float16")
        
        # Initialize TTS
        self.tts = None
        self.tts_available = TTS_AVAILABLE
        self.ref_audio_path = tts_ref_audio or os.getenv("TTS_REF_AUDIO", "")
        self.ref_text = tts_ref_text or os.getenv("TTS_REF_TEXT", "")
        self.ref_codes = None
        
        if TTS_AVAILABLE:
            self.NeuTTSAir = NeuTTSAir
            self.sf = sf
            self.torch = torch
    
    def _init_tts(self):
        """Lazy initialize TTS model."""
        if not self.tts_available:
            return False
        
        try:
            # Note: NNPACK warnings from PyTorch are harmless hardware optimization messages
            # They indicate NNPACK isn't available but don't affect functionality
            self.tts = self.NeuTTSAir(
                backbone_repo="neuphonic/neutts-air-q4-gguf",
                backbone_device="cpu",
                codec_repo="neuphonic/neucodec-onnx-decoder",
                codec_device="cpu"
            )
            
            # Load or encode reference if available
            if self.ref_audio_path and os.path.exists(self.ref_audio_path):
                # Check if reference is a pre-encoded .pt file
                if self.ref_audio_path.endswith('.pt'):
                    # Load pre-encoded reference codes directly
                    # Use weights_only=True for security (prevents arbitrary code execution)
                    try:
                        self.ref_codes = self.torch.load(self.ref_audio_path, map_location='cpu', weights_only=True)
                    except TypeError:
                        # Fallback for older PyTorch versions without weights_only parameter
                        self.ref_codes = self.torch.load(self.ref_audio_path, map_location='cpu')
                else:
                    # Fallback: encode raw audio file (backward compatibility)
                    self.ref_codes = self.tts.encode_reference(self.ref_audio_path)
                
                # Load reference text if it's a file path
                if self.ref_text and os.path.exists(self.ref_text):
                    with open(self.ref_text, "r") as f:
                        self.ref_text = f.read().strip()
            return True
        except Exception as e:
            return False
    
    def forward(
        self,
        action: str,
        path: Optional[str] = None,
        text: Optional[str] = None
    ) -> str:
        """Execute speech action and return result."""
        if action == "transcribe":
            if not path:
                return "Error: 'path' required for transcribe action"
            
            if not self.stt:
                return "Error: Whisper STT not available. Install faster-whisper"
            
            if not os.path.exists(path):
                return f"Error: Audio file not found at path: {path}"
            
            try:
                segments, info = self.stt.transcribe(path, beam_size=1, vad_filter=True)
                transcript = "".join([seg.text for seg in segments])
                return f"Transcript: {transcript}"
            except Exception as e:
                return f"Error transcribing audio: {str(e)}"
        
        elif action == "speak":
            if not text:
                return "Error: 'text' required for speak action"
            
            if not self.tts_available:
                return f"TTS not available. Would speak: {text}"
            
            # Initialize TTS if needed
            if self.tts is None:
                if not self._init_tts():
                    return f"TTS initialization failed. Would speak: {text}"
            
            try:
                import time
                import uuid
                # Use unique filename to avoid conflicts
                out_path = f"out_{int(time.time())}_{uuid.uuid4().hex[:8]}.wav"
                
                # Check if we have reference audio configured
                if self.ref_codes is not None and self.ref_text:
                    # Generate speech with voice cloning
                    wav = self.tts.infer(text, self.ref_codes, self.ref_text)
                    self.sf.write(out_path, wav, 24000)
                    return f"Spoken via NeuTTS-Air, saved to: {out_path}"
                else:
                    return (
                        "NeuTTS-Air requires reference audio and text for voice cloning. "
                        "Configure tts_ref_audio and tts_ref_text parameters. "
                        f"Would speak: {text}"
                    )
            except Exception as e:
                return f"Error generating speech: {str(e)}. Would speak: {text}"
        
        else:
            return f"Error: Unknown action '{action}'. Use 'transcribe' or 'speak'"
