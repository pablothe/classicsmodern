#!/bin/bash
#
# Generate Audiobook Helper Script
# Usage: ./generate_audiobook.sh <translated_file> [voice] [format]
#

# Check if .env exists and load it
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check for API key
if [ -z "$OPENAI_API_KEY" ]; then
    echo "❌ ERROR: OPENAI_API_KEY not found"
    echo ""
    echo "Please create a .env file with your OpenAI API key:"
    echo "  echo 'OPENAI_API_KEY=your-api-key-here' > .env"
    echo ""
    echo "Then run this script again."
    exit 1
fi

# Check for input file
if [ -z "$1" ]; then
    echo "Usage: ./generate_audiobook.sh <translated_file> [voice] [format]"
    echo ""
    echo "Example:"
    echo "  ./generate_audiobook.sh books/crime_punishment/chunks/test_chunk/translated/chunk_001_modern_spanish_4b.md fable mp3"
    echo ""
    echo "Available voices: alloy, echo, fable, onyx, nova, shimmer"
    echo "Available formats: mp3, wav, flac"
    exit 1
fi

INPUT_FILE="$1"
VOICE="${2:-fable}"
FORMAT="${3:-mp3}"

echo "Generating audiobook..."
echo "  Input: $INPUT_FILE"
echo "  Voice: $VOICE"
echo "  Format: $FORMAT"
echo ""

# Activate virtual environment and run
source venv/bin/activate
python local_reader_audio.py "$INPUT_FILE" "$VOICE" "$FORMAT"
