# NeuTTS-Air TTS Fix Summary

## Problem Statement

The neutts-air TTS feature was non-functional with the following issues:
1. Error messages claimed "printed text instead" but text was never actually printed
2. Unhelpful error messages without actionable guidance
3. neutts-air package not properly installable (not on PyPI, no setup.py)
4. Silent failures when TTS was unavailable
5. No clear documentation on how to install and configure

## Root Causes

1. **Missing Package Installation**: The `neutts-air` package is not available on PyPI and the GitHub repository lacks a `setup.py` or `pyproject.toml`, making it non-installable via pip.

2. **Non-functional Fallback**: The code claimed to print text as a fallback when TTS failed, but the `print()` statements were missing. Text was never actually printed to console.

3. **Silent Failures**: Import errors and initialization failures were caught but not logged, making debugging difficult.

4. **Incomplete Documentation**: Installation instructions didn't clearly explain that neutts-air needed special installation steps.

## Solutions Implemented

### 1. Fixed Fallback Text Printing (`src/agents/tools/speech.py`)

**Changes:**
- Added `print(f"[TTS FALLBACK] {text}")` in all error paths:
  - When TTS initialization fails
  - When neutts-air is not installed  
  - When reference audio is not configured
  - When TTS inference fails

**Result:** Text is now actually printed to console when TTS is unavailable, making the system usable even without TTS installed.

### 2. Improved Error Messages

**Before:**
```
NeuTTS-Air initialization failed: <error>; printed text instead.
```

**After:**
```
NeuTTS-Air initialization failed: <error>. Text printed to console instead.
```

And for missing installation:
```
NeuTTS-Air not installed. Install neutts-air package and dependencies (see docs/TTS_SETUP.md). Text printed to console instead.
```

**Result:** Error messages now provide clear guidance on what went wrong and how to fix it.

### 3. Added Diagnostic Logging

**Added to `__init__` method:**
```python
print("✓ NeuTTS-Air successfully loaded")
print(f"  - Reference audio configured: {self.ref_audio_path}")
```

**When import fails:**
```python
print(f"✗ NeuTTS-Air not available: {e}")
print("  - TTS will fall back to printing text to console")
print("  - See docs/TTS_SETUP.md for installation instructions")
```

**Result:** Users immediately see TTS status on startup, making configuration issues obvious.

### 4. Created Installation Script (`scripts/install_neutts_air.sh`)

**Features:**
- Checks for espeak dependency
- Clones neutts-air repository
- Creates a proper setup.py
- Installs package in editable mode
- Verifies installation

**Usage:**
```bash
bash scripts/install_neutts_air.sh
```

**Result:** One-command installation of neutts-air package.

### 5. Updated Documentation

#### `requirements.txt`
Added comments explaining:
- neutts-air is not on PyPI
- How to install it manually or via git
- Reference to detailed setup docs

#### `docs/TTS_SETUP.md`
Added section "3. Install NeuTTS-Air Package" with:
- Automated installation via script
- Manual installation instructions
- setup.py creation steps
- Installation verification

#### `README.md`
Updated installation instructions to reference the new script.

### 6. Created Test Script (`test_tts_fallback.py`)

A demonstration script showing:
- How SpeechTool initializes
- Fallback behavior when TTS unavailable
- Helpful output for debugging

## Testing

The fix can be tested in three scenarios:

### Scenario 1: neutts-air Not Installed (Most Common)
```bash
python test_tts_fallback.py
```
**Expected:** 
- Initialization prints: "✗ NeuTTS-Air not available"
- Speak actions print: "[TTS FALLBACK] <text>"
- Helpful error messages with installation guidance

### Scenario 2: neutts-air Installed, No Reference Audio
```bash
export TTS_REF_AUDIO=""
export TTS_REF_TEXT=""
python test_tts_fallback.py
```
**Expected:**
- Initialization prints: "✓ NeuTTS-Air successfully loaded"
- Warning: "No reference audio configured"
- Speak actions print: "[TTS FALLBACK] <text>"
- Error: "Configure TTS_REF_AUDIO and TTS_REF_TEXT"

### Scenario 3: Full TTS Setup (Ideal)
```bash
export TTS_REF_AUDIO=/path/to/reference.wav
export TTS_REF_TEXT="transcript text"
python test_tts_fallback.py
```
**Expected:**
- Initialization prints: "✓ NeuTTS-Air successfully loaded"
- Reference audio path shown
- Audio generated to out.wav
- No fallback printing

## Files Changed

1. **src/agents/tools/speech.py** - Fixed fallback printing, improved logging
2. **requirements.txt** - Added installation notes
3. **scripts/install_neutts_air.sh** - New installation script
4. **docs/TTS_SETUP.md** - Updated installation instructions
5. **README.md** - Referenced new installation script
6. **test_tts_fallback.py** - New test/demo script

## Backward Compatibility

All changes are backward compatible:
- Code still works with neutts-air installed
- Fallback behavior is transparent to users
- No API changes to SpeechTool
- Existing configurations continue to work

## Installation Instructions for Users

### Quick Start (Without TTS)
No action needed! TTS will fall back to printing text.

### Install TTS Support

1. **Install espeak:**
   ```bash
   # Ubuntu/Debian
   sudo apt install espeak
   
   # Arch Linux
   sudo pacman -S espeak
   
   # macOS
   brew install espeak
   ```

2. **Install neutts-air:**
   ```bash
   bash scripts/install_neutts_air.sh
   ```

3. **Configure reference audio:**
   ```bash
   export TTS_REF_AUDIO=/path/to/reference.wav
   export TTS_REF_TEXT="transcript of the audio"
   ```

4. **Verify:**
   ```bash
   python test_tts_fallback.py
   ```

## Summary

This fix makes the TTS feature actually work as advertised:
- ✅ Text is now printed when TTS unavailable (as error messages claimed)
- ✅ Clear error messages with actionable guidance
- ✅ Easy installation via provided script
- ✅ Helpful diagnostic logging
- ✅ Comprehensive documentation
- ✅ Backward compatible
- ✅ Graceful degradation when TTS not installed

The system now works whether or not neutts-air is installed, with clear feedback about what's happening and how to improve the configuration.
