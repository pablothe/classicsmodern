#!/bin/bash
# Orpheus-TTS Installation Script for Modern Classics
# Run with: bash install_orpheus.sh

set -e  # Exit on error

echo "=================================================="
echo "Orpheus-TTS Installation for Modern Classics"
echo "=================================================="
echo ""

# Check Python version
echo "✓ Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "  Found Python $python_version"
echo ""

# Check if ffmpeg is installed
echo "✓ Checking for FFmpeg..."
if command -v ffmpeg &> /dev/null; then
    ffmpeg_version=$(ffmpeg -version 2>&1 | head -n 1)
    echo "  Found: $ffmpeg_version"
else
    echo "  ⚠️  FFmpeg not found"
    echo "  Installing FFmpeg..."

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install ffmpeg
        else
            echo "  ❌ Error: Homebrew not found. Please install Homebrew first:"
            echo "     /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
            exit 1
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v apt &> /dev/null; then
            sudo apt update && sudo apt install -y ffmpeg
        elif command -v yum &> /dev/null; then
            sudo yum install -y ffmpeg
        else
            echo "  ❌ Error: Unable to install FFmpeg automatically"
            echo "     Please install FFmpeg manually"
            exit 1
        fi
    else
        echo "  ⚠️  Unsupported OS. Please install FFmpeg manually."
        exit 1
    fi
fi
echo ""

# Install orpheus-speech
echo "✓ Installing orpheus-speech..."
pip install orpheus-speech
echo ""

# Check for vllm issues and revert if needed
echo "✓ Checking vllm version..."
vllm_version=$(pip show vllm 2>/dev/null | grep Version | awk '{print $2}')

if [[ "$vllm_version" != "0.7.3" ]]; then
    echo "  ⚠️  Found vllm $vllm_version (may have bugs)"
    echo "  Reverting to vllm 0.7.3 for stability..."
    pip install vllm==0.7.3
else
    echo "  ✓ Using vllm 0.7.3 (stable)"
fi
echo ""

# Verify installation
echo "✓ Verifying installation..."
python3 -c "from orpheus_tts import OrpheusModel; print('  ✓ Orpheus-TTS installed successfully')" 2>/dev/null || {
    echo "  ❌ Error: Orpheus-TTS installation failed"
    echo "     Try manual installation: pip install orpheus-speech"
    exit 1
}
echo ""

# Run quick test
echo "=================================================="
echo "Installation Complete!"
echo "=================================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Run quick test:"
echo "   python local_tts_orpheus.py test_orpheus_sample.md"
echo ""
echo "2. Try different voices:"
echo "   python local_tts_orpheus.py test_orpheus_sample.md --voice leah"
echo ""
echo "3. Generate full audiobook:"
echo "   python local_tts_orpheus.py books/mybook/translated.md --voice tara"
echo ""
echo "Available voices (in order of quality):"
echo "  - tara (most conversational)"
echo "  - leah"
echo "  - jess"
echo "  - leo"
echo "  - dan"
echo "  - mia"
echo "  - zac"
echo "  - zoe"
echo ""
echo "For more info, see:"
echo "  - ORPHEUS_SETUP.md"
echo "  - TEST_ORPHEUS.md"
echo "  - ORPHEUS_INTEGRATION_SUMMARY.md"
echo ""
