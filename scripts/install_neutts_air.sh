#!/bin/bash
# Installation script for NeuTTS-Air TTS package
#
# This script installs the NeuTTS-Air package which is not available on PyPI.
# It clones the repository, adds a setup.py, and installs it in editable mode.
#
# Prerequisites:
# - espeak must be installed (see docs/TTS_SETUP.md)
# - Python dependencies from requirements.txt must be installed

set -e

echo "========================================="
echo "NeuTTS-Air Installation Script"
echo "========================================="
echo ""

# Check if espeak is installed
if ! command -v espeak &> /dev/null && ! command -v espeak-ng &> /dev/null; then
    echo "⚠️  WARNING: espeak or espeak-ng not found!"
    echo "    NeuTTS-Air requires espeak for phonemization."
    echo ""
    echo "    Install it with:"
    echo "      Ubuntu/Debian: sudo apt install espeak"
    echo "      Arch Linux:    sudo pacman -S espeak"
    echo "      macOS:         brew install espeak"
    echo ""
    echo "    Press Ctrl+C to cancel or Enter to continue anyway..."
    read
fi

# Determine installation directory
INSTALL_DIR="${NEUTTS_INSTALL_DIR:-/tmp/neutts-air-install}"
echo "Installation directory: $INSTALL_DIR"
echo ""

# Clone the repository if it doesn't exist
if [ -d "$INSTALL_DIR" ]; then
    echo "✓ Directory already exists: $INSTALL_DIR"
    echo "  Updating repository..."
    cd "$INSTALL_DIR"
    git pull origin main || true
else
    echo "Cloning neutts-air repository..."
    git clone https://github.com/neuphonic/neutts-air.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

echo ""
echo "Creating setup.py for pip installation..."

# Create setup.py if it doesn't exist
if [ ! -f "setup.py" ]; then
    cat > setup.py << 'SETUP_EOF'
from setuptools import setup, find_packages
import os

# Read requirements from requirements.txt if it exists
requirements = []
if os.path.exists('requirements.txt'):
    with open('requirements.txt', 'r') as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name="neutts-air",
    version="0.1.0",
    description="State-of-the-art on-device TTS with instant voice cloning",
    author="Neuphonic",
    url="https://github.com/neuphonic/neutts-air",
    packages=find_packages(),
    install_requires=requirements if requirements else [
        "librosa>=0.11.0",
        "neucodec>=0.0.4",
        "phonemizer>=3.3.0",
        "soundfile>=0.13.1",
        "resemble-perth>=1.0.1",
        "torch>=2.0.0",
        "transformers>=4.43.0",
        "numpy>=1.24.0",
        "llama-cpp-python>=0.3.16",
        "onnxruntime>=1.23.0",
    ],
    python_requires=">=3.10",
)
SETUP_EOF
    echo "✓ Created setup.py"
else
    echo "✓ setup.py already exists"
fi

echo ""
echo "Installing neutts-air package..."
pip install -e .

echo ""
echo "========================================="
echo "Verifying installation..."
echo "========================================="

# Verify installation
if python -c "from neuttsair.neutts import NeuTTSAir; print('✓ NeuTTS-Air successfully installed and importable')" 2>&1; then
    echo ""
    echo "========================================="
    echo "✓ Installation successful!"
    echo "========================================="
    echo ""
    echo "Next steps:"
    echo "1. Configure reference audio for voice cloning:"
    echo "   export TTS_REF_AUDIO=/path/to/reference.wav"
    echo "   export TTS_REF_TEXT=\"The exact transcript of the audio\""
    echo ""
    echo "2. See docs/TTS_SETUP.md for more information"
    echo ""
else
    echo ""
    echo "✗ Installation verification failed"
    echo "  Please check the error messages above"
    exit 1
fi
