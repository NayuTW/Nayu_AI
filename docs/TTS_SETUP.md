# NeuTTS-Air Text-to-Speech Setup Guide

This guide will help you set up NeuTTS-Air for text-to-speech functionality in the Nayu AI system.

## Overview

NeuTTS-Air is a state-of-the-art on-device TTS model that provides:
- 🗣 Best-in-class realistic voice synthesis
- 👫 Instant voice cloning from just 3 seconds of audio
- 📱 Optimized for on-device deployment
- 🚄 Real-time generation on mid-range devices

## Prerequisites

### 1. Install espeak

espeak is a required dependency for NeuTTS-Air's phonemizer.

**Ubuntu/Debian:**
```bash
sudo apt install espeak
```

**Arch Linux:**
```bash
sudo pacman -S espeak
```

**macOS:**
```bash
brew install espeak
```

**Windows:**
Download and install from [espeak-ng releases](https://github.com/espeak-ng/espeak-ng/releases), then set environment variables:
```powershell
$env:PHONEMIZER_ESPEAK_LIBRARY = "c:\Program Files\eSpeak NG\libespeak-ng.dll"
$env:PHONEMIZER_ESPEAK_PATH = "c:\Program Files\eSpeak NG"
setx PHONEMIZER_ESPEAK_LIBRARY "c:\Program Files\eSpeak NG\libespeak-ng.dll"
setx PHONEMIZER_ESPEAK_PATH "c:\Program Files\eSpeak NG"
```

### 2. Install Python Dependencies

The NeuTTS-Air dependencies are included in the requirements.txt:

```bash
pip install -r requirements.txt
```

This installs:
- librosa (audio processing)
- neucodec (neural audio codec)
- phonemizer (text-to-phoneme conversion)
- soundfile (audio file I/O)
- resemble-perth (audio watermarking)

## Configuration

### Preparing Reference Audio for Voice Cloning

NeuTTS-Air requires reference audio to clone a voice. Follow these guidelines:

#### Audio Requirements:
1. **Format**: Mono WAV file
2. **Sample Rate**: 16-44 kHz
3. **Duration**: 3-15 seconds
4. **Quality**: 
   - Clear, natural speech
   - Minimal background noise
   - Continuous speech (like a monologue)
   - Few pauses for better tone capture

#### Creating Reference Files:

1. **Record or find suitable audio** that meets the requirements above
2. **Create a transcript file** with the exact words spoken in the audio
3. **Save both files** in an accessible location

#### Example:

**reference.wav** - Audio file with someone saying:
> "My name is Dave, and um, I'm from London."

**reference.txt** - Text file containing:
```
My name is Dave, and um, I'm from London.
```

### Pre-encoding Reference Audio (Recommended)

For optimal performance, you can pre-encode your reference audio to a `.pt` file. This avoids re-encoding on every TTS initialization.

**Option 1: Use Pre-encoded .pt Files (Recommended)**

1. Pre-encode your reference audio using NeuTTS-Air:

```python
from neuttsair.neutts import NeuTTSAir
import torch

# Initialize NeuTTS-Air
tts = NeuTTSAir(
    backbone_repo="neuphonic/neutts-air-q4-gguf",
    backbone_device="cpu",
    codec_repo="neuphonic/neucodec-onnx-decoder",
    codec_device="cpu"
)

# Encode and save reference
ref_codes = tts.encode_reference("/path/to/reference.wav")
torch.save(ref_codes, "/path/to/reference.pt")
print("Reference codes saved to reference.pt")
```

2. Set environment variables to use the pre-encoded file:

**Linux/macOS:**
```bash
export TTS_REF_AUDIO=/path/to/reference.pt
export TTS_REF_TEXT=/path/to/reference.txt
# Or provide the text directly:
export TTS_REF_TEXT="My name is Dave, and um, I'm from London."
```

**Windows:**
```powershell
$env:TTS_REF_AUDIO="C:\path\to\reference.pt"
$env:TTS_REF_TEXT="C:\path\to\reference.txt"
# Or:
$env:TTS_REF_TEXT="My name is Dave, and um, I'm from London."
```

**Option 2: Use Raw Audio Files (Backward Compatible)**

If you don't pre-encode, the system will automatically encode raw audio files on first use:

**Linux/macOS:**
```bash
export TTS_REF_AUDIO=/path/to/reference.wav
export TTS_REF_TEXT=/path/to/reference.txt
```

**Windows:**
```powershell
$env:TTS_REF_AUDIO="C:\path\to\reference.wav"
$env:TTS_REF_TEXT="C:\path\to\reference.txt"
```

**Note:** Using pre-encoded `.pt` files significantly reduces TTS initialization time and is the recommended approach.

## Sample Reference Files

You can download sample reference files from the NeuTTS-Air repository:

```bash
# Clone the NeuTTS-Air repository (optional, just for samples)
git clone https://github.com/neuphonic/neutts-air.git /tmp/neutts-air-samples

# Use the sample files
export TTS_REF_AUDIO=/tmp/neutts-air-samples/samples/dave.wav
export TTS_REF_TEXT=/tmp/neutts-air-samples/samples/dave.txt
```

Available samples in the repository:
- `samples/dave.wav` and `samples/dave.txt`
- `samples/jo.wav` (no text file provided in original repo)

## Usage

Once configured, the speech tool will automatically use NeuTTS-Air for text-to-speech:

### Via the Agent
The main agent can use the speech tool through its tool registry:

```python
# The agent will call the speech tool when needed
response = await agent.handle_user_message("Please read this text aloud: Hello World!")
```

### Programmatically

```python
from src.agents.tools.speech import SpeechTool
from src.agents.state import SharedState

# Initialize
state = SharedState()
speech = SpeechTool(
    state,
    tts_ref_audio="/path/to/reference.wav",
    tts_ref_text="The transcript of the reference audio"
)

# Speak text
result = await speech.run(action="speak", text="Hello, this is a test!")
print(result['summary'])
# Output: Spoken via NeuTTS-Air (out.wav).
```

## Troubleshooting

### "NeuTTS-Air not installed"
- Ensure all dependencies are installed: `pip install -r requirements.txt`
- Check that espeak is installed and accessible

### "NeuTTS-Air requires reference audio and text"
- Set the TTS_REF_AUDIO environment variable
- Set the TTS_REF_TEXT environment variable
- Ensure the files exist and are readable

### "NeuTTS-Air initialization failed"
- Check that espeak is installed correctly
- Verify Python dependencies are compatible versions
- Check system resources (NeuTTS-Air requires some memory/compute)

### Poor Audio Quality
- Use higher quality reference audio (44 kHz vs 16 kHz)
- Ensure reference audio has clear, natural speech
- Avoid reference audio with background noise
- Try a longer reference clip (10-15 seconds)

## Advanced Configuration

### Using Different Models

NeuTTS-Air supports different model variants. By default, the code uses:
- Backbone: `neuphonic/neutts-air`
- Codec: `neuphonic/neucodec`

For faster inference with slightly lower quality, you can modify `speech.py` to use:
- Backbone: `neuphonic/neutts-air-q4-gguf` (quantized, requires llama-cpp-python)

### GPU Acceleration

By default, the system runs on CPU. To use GPU acceleration:

1. Install PyTorch with CUDA support
2. Modify `speech.py` to use `backbone_device="cuda"` and `codec_device="cuda"`

## Performance Tips

1. **Use pre-encoded .pt files**: Always use pre-encoded `.pt` files for reference audio instead of raw `.wav` files. This eliminates encoding overhead during TTS initialization and significantly improves startup time.
2. **Use GGUF models**: For on-device deployment, consider using quantized GGUF models
3. **Adjust model size**: Smaller models are faster but may have lower quality

## Resources

- [NeuTTS-Air GitHub](https://github.com/neuphonic/neutts-air)
- [NeuTTS-Air HuggingFace](https://huggingface.co/neuphonic/neutts-air)
- [Neuphonic Website](https://neuphonic.com)
- [espeak-ng Documentation](https://github.com/espeak-ng/espeak-ng/blob/master/docs/guide.md)

## License

NeuTTS-Air is provided by Neuphonic with its own license. Please review the license terms in the NeuTTS-Air repository.
