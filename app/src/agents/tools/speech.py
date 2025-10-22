import asyncio
from typing import Dict, Any
from faster_whisper import WhisperModel
import subprocess
import shutil

class SpeechTool:
    def __init__(self, state, stt_model_size="small.en", tts_voice_model_path: str = ""):
        self.state = state
        self.stt = WhisperModel(stt_model_size, compute_type="int8_float16")
        self.piper_bin = shutil.which("piper")
        # For piper, you typically provide a model path
        self.voice_model = tts_voice_model_path  # e.g., "/usr/share/piper/en_US-amy-low.onnx"

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
            if self.piper_bin and self.voice_model:
                # Output to file (could also pipe to playback)
                out_path = "out.wav"
                proc = subprocess.run([self.piper_bin, "--model", self.voice_model, "--output_file", out_path], input=text.encode("utf-8"))
                summary = f"Spoken via Piper ({out_path})."
            else:
                summary = "Piper not installed or voice model missing; printed text instead."
        else:
            summary = "Invalid speech action/args."
        delta = {"last_observation": summary}
        return {"summary": summary, "delta": delta}