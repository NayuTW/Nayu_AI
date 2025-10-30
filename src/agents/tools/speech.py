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
        self.import_error = None
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
            print("✓ NeuTTS-Air successfully loaded")
            if self.ref_audio_path:
                print(f"  - Reference audio configured: {self.ref_audio_path}")
            else:
                print("  - Warning: No reference audio configured (TTS_REF_AUDIO not set)")
        except ImportError as e:
            # NeuTTS-Air not installed
            self.import_error = str(e)
            print(f"✗ NeuTTS-Air not available: {e}")
            print("  - TTS will fall back to printing text to console")
            print("  - See docs/TTS_SETUP.md for installation instructions")

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
                        print(f"Initializing NeuTTS-Air TTS engine...")
                        self.tts = self.NeuTTSAir(
                            backbone_repo="neuphonic/neutts-air-q4-gguf",
                            backbone_device="cpu",
                            codec_repo="neuphonic/neucodec-onnx-decoder",
                            codec_device="cpu"
                        )
                        print(f"✓ TTS engine initialized")
                        
                        # Pre-encode reference if available
                        if self.ref_audio_path and os.path.exists(self.ref_audio_path):
                            print(f"Encoding reference audio: {self.ref_audio_path}")
                            self.ref_codes = self.tts.encode_reference(self.ref_audio_path)
                            print(f"✓ Reference audio encoded successfully")
                            # Load reference text if it's a file path
                            if self.ref_text and os.path.exists(self.ref_text):
                                with open(self.ref_text, "r") as f:
                                    self.ref_text = f.read().strip()
                                print(f"✓ Reference text loaded: {len(self.ref_text)} characters")
                    except Exception as e:
                        # Print the text as fallback with detailed error info
                        print(f"\n✗ NeuTTS-Air initialization failed!")
                        print(f"  Error type: {type(e).__name__}")
                        print(f"  Error message: {str(e)}")
                        import traceback
                        print(f"  Traceback:\n{traceback.format_exc()}")
                        print(f"[TTS FALLBACK] {text}")
                        summary = f"NeuTTS-Air initialization failed: {type(e).__name__}: {str(e)}. Text printed to console instead."
                        delta = {"last_observation": summary}
                        return {"summary": summary, "delta": delta}
                
                try:
                    out_path = "out.wav"
                    
                    # Check if we have reference audio configured
                    if self.ref_codes is not None and self.ref_text:
                        # Generate speech with voice cloning
                        print(f"Generating speech with NeuTTS-Air...")
                        wav = self.tts.infer(text, self.ref_codes, self.ref_text)
                        self.sf.write(out_path, wav, 24000)
                        print(f"✓ Audio generated: {out_path}")
                        summary = f"Spoken via NeuTTS-Air ({out_path})."
                    else:
                        # No reference configured - print text as fallback
                        print(f"\n⚠ Reference audio not available:")
                        print(f"  - ref_codes: {'Set' if self.ref_codes is not None else 'NOT SET'}")
                        print(f"  - ref_text: {'Set' if self.ref_text else 'NOT SET'}")
                        print(f"[TTS FALLBACK] {text}")
                        summary = "NeuTTS-Air requires reference audio and text for voice cloning. Configure TTS_REF_AUDIO and TTS_REF_TEXT environment variables. Text printed to console instead."
                    
                except Exception as e:
                    # Print the text as fallback with detailed error info
                    print(f"\n✗ NeuTTS-Air inference failed!")
                    print(f"  Error type: {type(e).__name__}")
                    print(f"  Error message: {str(e)}")
                    import traceback
                    print(f"  Traceback:\n{traceback.format_exc()}")
                    print(f"[TTS FALLBACK] {text}")
                    summary = f"NeuTTS-Air inference failed: {type(e).__name__}: {str(e)}. Text printed to console instead."
            else:
                # Print the text as fallback
                print(f"[TTS FALLBACK] {text}")
                summary = "NeuTTS-Air not installed. Install neutts-air package and dependencies (see docs/TTS_SETUP.md). Text printed to console instead."
        else:
            summary = "Invalid speech action/args."
        delta = {"last_observation": summary}
        return {"summary": summary, "delta": delta}
