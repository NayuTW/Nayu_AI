# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- **TTS Engine Migration**: Switched from Piper to NeuTTS-Air for text-to-speech functionality
  - NeuTTS-Air provides state-of-the-art voice synthesis with instant voice cloning
  - Requires reference audio (3-15 seconds) for voice cloning
  - Configuration via environment variables: TTS_REF_AUDIO and TTS_REF_TEXT
  - Graceful fallback when dependencies not installed or reference audio not configured

### Added
- NeuTTS-Air dependencies in requirements.txt:
  - librosa (audio processing)
  - neucodec (neural audio codec)
  - phonemizer (text-to-phoneme conversion)
  - soundfile (audio file I/O)
  - resemble-perth (audio watermarking)
- Comprehensive TTS setup guide: docs/TTS_SETUP.md
- Example script: examples/tts_example.py
- Environment variable support for TTS configuration

### Removed
- Piper TTS system dependency and references

### Security
- All changes validated with CodeQL - 0 security alerts

### Migration Notes
For users upgrading from previous versions:
1. Install espeak: `sudo apt install espeak` (or equivalent for your OS)
2. Install updated dependencies: `pip install -r requirements.txt`
3. Configure reference audio (optional but recommended):
   ```bash
   export TTS_REF_AUDIO=/path/to/reference.wav
   export TTS_REF_TEXT=/path/to/reference.txt
   ```
4. See docs/TTS_SETUP.md for detailed instructions

The SpeechTool API remains backward compatible. If NeuTTS-Air dependencies are not installed or reference audio is not configured, the system will gracefully fall back to printing text with helpful error messages.
