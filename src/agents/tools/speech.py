import asyncio
from typing import Dict, Any, Optional
from faster_whisper import WhisperModel
import os

class SpeechTool:
    def __init__(self, state, stt_model_size="small.en", tts_ref_audio: str = "", tts_ref_text: str = ""):
        self.state = state
        self.stt = WhisperModel(stt_model_size, compute_type="int8_float16")
        
        # Initialize NeuTTS-Air
        self.tts = None
        self.tts_available = False
        # Allow environment variables to override defaults
        self.ref_audio_path = tts_ref_audio or os.getenv("TTS_REF_AUDIO", "")
        self.ref_text = tts_ref_text or os.getenv("TTS_REF_TEXT", "")
        self.ref_codes = None  # Pre-encoded reference for faster inference
        
        try:
            from neuttsair.neutts import NeuTTSAir
            import soundfile as sf
            self.NeuTTSAir = NeuTTSAir
            self.sf = sf
            self.tts_available = True
        except ImportError:
            # NeuTTS-Air not installed
            pass

    @staticmethod
    def spec():
        return {
            "name": "speech",
            "description": "Transcribe audio or speak text.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["transcribe", "speak"]},
                    "path": {"type": "string"},
                    "text": {"type": "string"}
                },
                "required": ["action"]
            }
        }

    async def run(self, action: str, path: str = "", text: str = "") -> Dict[str, Any]:
        if action == "transcribe" and path:
            segments, info = self.stt.transcribe(path, beam_size=1, vad_filter=True)
            transcript = "".join([seg.text for seg in segments])
            summary = f"Transcript: {transcript[:800]}"
        elif action == "speak" and text:
            if self.tts_available:
                # Initialize TTS model if not already done
                if self.tts is None:
                    try:
                        self.tts = self.NeuTTSAir(
                            backbone_repo="neuphonic/neutts-air-q4-gguf",
                            backbone_device="cpu",
                            codec_repo="neuphonic/neucodec-onnx-decoder",
                            codec_device="cpu"
                        )
                        
                        # Pre-encode reference if available
                        if self.ref_audio_path and os.path.exists(self.ref_audio_path):
                            self.ref_codes = self.tts.encode_reference(self.ref_audio_path)
                            # Load reference text if it's a file path
                            if self.ref_text and os.path.exists(self.ref_text):
                                with open(self.ref_text, "r") as f:
                                    self.ref_text = f.read().strip()
                    except Exception as e:
                        summary = f"NeuTTS-Air initialization failed: {str(e)}; printed text instead."
                        delta = {"last_observation": summary}
                        return {"summary": summary, "delta": delta}
                
                try:
                    out_path = "out.wav"
                    
                    # Check if we have reference audio configured
                    if self.ref_codes is not None and self.ref_text:
                        # Generate speech with voice cloning
                        wav = self.tts.infer(text, self.ref_codes, self.ref_text)
                        self.sf.write(out_path, wav, 24000)
                        summary = f"Spoken via NeuTTS-Air ({out_path})."
                    else:
                        # No reference configured - inform user
                        summary = "NeuTTS-Air requires reference audio and text for voice cloning. Configure tts_ref_audio and tts_ref_text parameters. Text printed instead."
                    
                except Exception as e:
                    summary = f"NeuTTS-Air failed: {str(e)}; printed text instead."
            else:
                summary = "NeuTTS-Air not installed; printed text instead."
        else:
            summary = "Invalid speech action/args."
        delta = {"last_observation": summary}
        return {"summary": summary, "delta": delta}
