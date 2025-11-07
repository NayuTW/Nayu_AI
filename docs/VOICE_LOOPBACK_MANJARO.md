# Voice Loopback on Manjaro (KDE Plasma with PipeWire/PulseAudio)

This guide explains how to set up local audio loopback capture and virtual microphone mixing on Manjaro with KDE Plasma for the Nayu_AI voice session feature.

## Overview

The voice session feature allows the AI to:
1. Listen to Discord call participants (via PipeWire/PulseAudio monitor source)
2. Transcribe remote participant speech in real-time using faster-whisper
3. Optionally capture and transcribe your microphone separately
4. Mix your microphone and AI TTS output into a virtual microphone for Discord

## Prerequisites

### System Requirements

- Manjaro Linux with KDE Plasma
- PipeWire or PulseAudio audio system
- Python 3.10+ (3.11 recommended)
- All Nayu_AI dependencies installed (see main README)

### Audio System Check

Check if you're using PipeWire or PulseAudio:

```bash
# Check for PipeWire
pactl info | grep "Server Name"

# Should show either:
# Server Name: PulseAudio (on PipeWire 0.3.xx)
# or
# Server Name: pulseaudio
```

## Installation

### 1. Install Audio Dependencies

```bash
# Install required system packages
sudo pacman -S espeak libpulse

# Install Python audio packages
source .venv/bin/activate
pip install webrtcvad pulsectl sounddevice
```

### 2. Create Virtual Audio Sink (for Discord Input)

You need a virtual audio sink (null sink) whose monitor can be used as Discord's input microphone.

#### Option A: Temporary Setup (Using pactl)

Create a null sink temporarily (will disappear on reboot):

```bash
pactl load-module module-null-sink sink_name=nayu_virtual_mic sink_properties=device.description="Nayu_Virtual_Mic"
```

The monitor source will be `nayu_virtual_mic.monitor`.

#### Option B: Persistent Setup (PipeWire Configuration)

Create a persistent virtual device by adding to your PipeWire config:

```bash
# Create user config directory if needed
mkdir -p ~/.config/pipewire/pipewire.conf.d/

# Create virtual device config
cat > ~/.config/pipewire/pipewire.conf.d/nayu-virtual-mic.conf << 'EOF'
# Virtual microphone for Nayu AI
context.modules = [
    {   name = libpipewire-module-loopback
        args = {
            node.description = "Nayu Virtual Mic"
            capture.props = {
                node.name = "nayu_virtual_mic_input"
                media.class = "Audio/Sink"
            }
            playback.props = {
                node.name = "nayu_virtual_mic_output"
                media.class = "Audio/Source"
            }
        }
    }
]
EOF

# Restart PipeWire
systemctl --user restart pipewire pipewire-pulse
```

### 3. Identify Audio Devices

List available devices to find the correct names/indices:

```bash
# List all sources (including monitors)
pactl list short sources

# Example output:
# 42  alsa_output.pci-0000_00_1f.3.analog-stereo.monitor  ...
# 43  alsa_input.pci-0000_00_1f.3.analog-stereo  ...
# 44  nayu_virtual_mic.monitor  ...
```

**Important device names:**

1. **Discord Output Monitor**: The `.monitor` source of the device Discord uses for output
   - Example: `alsa_output.pci-0000_00_1f.3.analog-stereo.monitor`
   - This captures what Discord plays (remote participants)

2. **User Microphone**: Your physical microphone input
   - Example: `alsa_input.pci-0000_00_1f.3.analog-stereo`

3. **Virtual Sink Output**: The monitor of your virtual sink
   - Example: `nayu_virtual_mic.monitor`
   - Configure Discord to use the corresponding sink as its input microphone

### 4. Configure Discord

1. Open Discord Settings → Voice & Video
2. Set **Input Device** to: `Nayu Virtual Mic` (or similar name)
3. Set **Output Device** to your normal speakers/headphones
4. Disable Echo Cancellation and Noise Suppression (they interfere with the AI)

## Configuration

### Environment Variables

Set these environment variables before starting Nayu_AI:

```bash
# Enable voice session
export VOICE_SESSION=1

# Discord output monitor (captures remote participants)
# Use device name or index from `pactl list short sources`
export DISCORD_OUTPUT_MONITOR="alsa_output.pci-0000_00_1f.3.analog-stereo.monitor"

# Your microphone (optional, for user transcription)
export USER_MIC_SOURCE="alsa_input.pci-0000_00_1f.3.analog-stereo"

# Virtual sink output (where mixed audio goes to Discord)
export VIRTUAL_SINK_OUTPUT="nayu_virtual_mic"

# Optional: VAD aggressiveness (0-3, higher = more aggressive)
export VAD_AGGRESSIVENESS=2

# Optional: Mic ducking when AI speaks (dB reduction, negative value)
export DUCKING_DB=-12.0
```

### Dashboard Settings

Once the application is running with `VOICE_SESSION=1`, you can control:

1. **User Mic Transcription**: Toggle in dashboard Settings section
   - This setting is stored in the database and persists across restarts
   - Controls whether your mic is captured and transcribed separately

## Usage

### Starting with Voice Session

```bash
# Set environment variables
export VOICE_SESSION=1
export DISCORD_OUTPUT_MONITOR="alsa_output.pci-0000_00_1f.3.analog-stereo.monitor"
export USER_MIC_SOURCE="alsa_input.pci-0000_00_1f.3.analog-stereo"
export VIRTUAL_SINK_OUTPUT="nayu_virtual_mic"

# Start application
python -m src.app
```

### Expected Behavior

When voice session is active:

1. **Remote Speech**: 
   - Detected via VAD on Discord output monitor
   - Transcribed and logged as "Remote: [text]"
   - Published to event bus as `voice.transcript` events
   - Visible in dashboard via WebSocket

2. **User Speech** (if user mic enabled):
   - Detected via VAD on microphone
   - Transcribed and logged as "User: [text]"
   - Triggers AI interruption if AI is currently speaking
   - Mixed with AI TTS for Discord input

3. **AI TTS**:
   - Generated by NeuTTS-Air
   - Mixed into virtual microphone
   - Discord hears both user mic + AI TTS
   - User's mic is automatically ducked (reduced volume) when AI speaks

### Checking Logs

Voice session events appear in logs and dashboard:

```bash
# Watch application logs
python -m src.app | grep -E "(Voice|Remote|User|VAD|STT)"
```

Dashboard WebSocket events include:
- `voice.session.started`: Session initialized
- `voice.transcript`: New transcript (speaker: "remote" or "user")
- `voice.interrupt`: User interrupted AI
- `voice.ai.speaking`: AI started speaking

## Troubleshooting

### Device Not Found

**Error**: `DISCORD_OUTPUT_MONITOR not set` or `LoopbackCapture error`

**Solution**: 
1. List devices: `pactl list short sources`
2. Find correct monitor name
3. Update environment variable
4. Try using device index instead of name

### No Audio Captured

**Symptoms**: Voice session starts but no transcripts appear

**Checks**:
1. Verify Discord is actually playing audio to the correct device:
   ```bash
   pactl list sink-inputs
   ```
   
2. Test monitor capture manually:
   ```bash
   parecord -d alsa_output.pci-0000_00_1f.3.analog-stereo.monitor test.wav
   ```

3. Check VAD sensitivity - lower `VAD_AGGRESSIVENESS` if speech not detected

### Discord Not Hearing AI

**Symptoms**: AI transcripts work but Discord participants can't hear the AI

**Checks**:
1. Verify Discord input device is set to virtual sink monitor
2. Check mixer is running - look for "AudioMixer started" in logs
3. Verify virtual sink exists:
   ```bash
   pactl list short sinks | grep nayu
   ```

### AI and User Competing

**Symptoms**: AI talks over user or user can't interrupt

**Solutions**:
- Increase `DUCKING_DB` (e.g., `-18.0` for more aggressive ducking)
- Reduce `VAD_AGGRESSIVENESS` to detect speech earlier
- Ensure user mic capture is enabled (`USER_MIC_SOURCE` set)

### High CPU Usage

**Symptoms**: CPU usage spikes when voice session active

**Solutions**:
1. Use smaller Whisper model:
   - Modify `src/audio/stt_stream.py`: change `model_size` from "small.en" to "tiny.en"
   
2. Reduce VAD sensitivity to process fewer utterances:
   ```bash
   export VAD_AGGRESSIVENESS=3
   ```

3. Use GPU acceleration if available (requires CUDA-capable faster-whisper build)

### Permission Errors

**Error**: `sounddevice` or `pulsectl` permission errors

**Solution**:
```bash
# Add user to audio group
sudo usermod -a -G audio $USER

# Re-login or:
newgrp audio
```

## Advanced Configuration

### Custom Frame Duration

Default is 20ms frames (required for VAD). To experiment:

```python
# In src/audio/loopback.py
LoopbackCapture(..., frame_ms=30)  # 10, 20, or 30 only
```

### Multiple Discord Servers

To handle multiple Discord voice channels:

1. Create multiple monitor sources in PulseAudio routing
2. Use PulseAudio module-loopback to combine them
3. Point `DISCORD_OUTPUT_MONITOR` to combined source

### Noise Filtering

For better transcription in noisy environments:

1. Enable PulseAudio noise cancellation:
   ```bash
   pactl load-module module-echo-cancel source_name=denoised_mic
   export USER_MIC_SOURCE="denoised_mic"
   ```

2. Or use external tools like NoiseTorch before capture

## Technical Details

### Architecture

```
[Discord Output] → Monitor Source → LoopbackCapture → VAD → STT → "Remote"
[User Mic] → MicCapture → VAD → STT → "User"
                ↓
           AudioMixer (with ducking)
                ↓
         [Virtual Sink Monitor] → Discord Input

[AI Agent] → NeuTTS-Air → AudioMixer → (same virtual sink)
```

### Audio Format

- **Sample Rate**: 48 kHz (standard for PipeWire/Discord)
- **Format**: Mono, 16-bit PCM (int16)
- **Frame Size**: 20ms (960 samples @ 48kHz)
- **VAD**: webrtcvad (aggressiveness 0-3)

### VAD Parameters

Adjustable in `src/audio/vad.py`:
- `speech_pad_frames`: Pre-speech padding (default 10 = 200ms)
- `silence_pad_frames`: Post-speech silence (default 15 = 300ms)
- `min_speech_frames`: Min consecutive speech (default 5 = 100ms)

### Ducking

Linear gain reduction applied to mic when AI speaks:
- `-12 dB` = 25% volume (default)
- `-18 dB` = 12.5% volume (more aggressive)
- `-6 dB` = 50% volume (less aggressive)

## Further Reading

- [PipeWire Documentation](https://docs.pipewire.org/)
- [PulseAudio Modules](https://www.freedesktop.org/wiki/Software/PulseAudio/Documentation/User/Modules/)
- [faster-whisper GitHub](https://github.com/guillaumekln/faster-whisper)
- [webrtcvad Documentation](https://github.com/wiseman/py-webrtcvad)

## Support

For issues specific to the voice loopback feature:

1. Check logs for voice session initialization errors
2. Verify all environment variables are set correctly
3. Test audio capture independently (parecord, arecord)
4. Report issues with full logs and device configuration
