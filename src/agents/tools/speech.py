import asyncio
from typing import Dict, Any, Optional
from faster_whisper import WhisperModel
import os
from pathlib import Path

class SpeechTool:
    def __init__(self, state, stt_model_size="small.en", tts_ref_audio: str = "", tts_ref_text: str = ""):
        self.state = state
        self.stt = WhisperModel(stt_model_size, compute_type="int8_float16")
        
        # Initialize NeuTTS-Air
        self.tts = None
        self.tts_available = False
        self.encoder_for_reference = None  # Separate encoder for ONNX decoder mode
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
    
    def _encode_reference_audio(self, ref_audio_path: str):
        """
        Encode reference audio to codes. Handles ONNX decoder scenario where 
        a separate encoder is needed.
        
        Args:
            ref_audio_path: Path to reference audio file or pre-encoded .pt file
            
        Returns:
            Encoded reference codes (torch.Tensor or np.ndarray)
        """
        import torch
        
        ref_path = Path(ref_audio_path)
        
        # Check if it's a pre-encoded .pt file
        if ref_path.suffix == '.pt':
            try:
                ref_codes = torch.load(ref_audio_path)
                return ref_codes
            except Exception as e:
                raise ValueError(f"Failed to load pre-encoded reference from {ref_audio_path}: {e}")
        
        # Check if we're using ONNX decoder (which can't encode)
        if hasattr(self.tts, '_is_onnx_codec') and self.tts._is_onnx_codec:
            # ONNX decoder can't encode, need to use full encoder
            if self.encoder_for_reference is None:
                try:
                    # Import neucodec for encoding
                    from neucodec import NeuCodec
                    import librosa
                    
                    # Create a separate encoder instance for reference encoding
                    self.encoder_for_reference = NeuCodec.from_pretrained("neuphonic/neucodec")
                    self.encoder_for_reference.eval()
                    # Keep on CPU to save memory
                    
                except ImportError as e:
                    raise ImportError(
                        "When using ONNX decoder, you need either:\n"
                        "1. Pre-encoded reference codes (.pt file), OR\n"
                        "2. The 'neucodec' package installed for encoding.\n"
                        f"Install with: pip install neucodec\nError: {e}"
                    )
            
            # Encode using the full codec
            try:
                import librosa
                wav, _ = librosa.load(ref_audio_path, sr=16000, mono=True)
                wav_tensor = torch.from_numpy(wav).float().unsqueeze(0).unsqueeze(0)  # [1, 1, T]
                with torch.no_grad():
                    ref_codes = self.encoder_for_reference.encode_code(audio_or_path=wav_tensor).squeeze(0).squeeze(0)
                return ref_codes
            except Exception as e:
                raise RuntimeError(f"Failed to encode reference audio with full codec: {e}")
        else:
            # Using full codec (PyTorch), can encode directly
            try:
                return self.tts.encode_reference(ref_audio_path)
            except Exception as e:
                raise RuntimeError(f"Failed to encode reference audio: {e}")

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
                            try:
                                self.ref_codes = self._encode_reference_audio(self.ref_audio_path)
                            except Exception as e:
                                summary = f"Failed to encode reference audio: {str(e)}. Please check your reference audio configuration."
                                delta = {"last_observation": summary}
                                return {"summary": summary, "delta": delta}
                            
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
