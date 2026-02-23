#!/bin/bash
# Run smoke tests with clear output
#
# Usage:
#   ./tests/run_smoke_tests.sh           # Default: skip Stable Diffusion (heavy)
#   ./tests/run_smoke_tests.sh --fast    # Only tests with no external deps
#   ./tests/run_smoke_tests.sh --full    # Include heavy tests (Stable Diffusion)
#   ./tests/run_smoke_tests.sh --ollama  # Only Ollama-dependent tests
#   ./tests/run_smoke_tests.sh --audio   # Only audio generation tests

set -e
cd "$(dirname "$0")/.."

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

echo "=========================================="
echo "  MODERN CLASSICS - SMOKE TEST SUITE"
echo "=========================================="
echo ""

case "${1:-}" in
    --fast)
        echo "Mode: FAST (no external services)"
        echo ""
        pytest tests/smoke/ \
            -m "smoke and not requires_ollama and not requires_kokoro and not requires_diffusion and not requires_network and not requires_ffmpeg" \
            -v --tb=short 2>&1
        ;;
    --full)
        echo "Mode: FULL (all services)"
        echo ""
        pytest tests/smoke/ -m "smoke" -v --tb=short 2>&1
        ;;
    --ollama)
        echo "Mode: OLLAMA (translation + summarization)"
        echo ""
        pytest tests/smoke/test_smoke_translation.py tests/smoke/test_smoke_summarize.py \
            -v --tb=short 2>&1
        ;;
    --audio)
        echo "Mode: AUDIO (Kokoro TTS)"
        echo ""
        pytest tests/smoke/test_smoke_audio.py tests/smoke/test_smoke_full_pipeline.py \
            -v --tb=short 2>&1
        ;;
    *)
        echo "Mode: DEFAULT (skip Stable Diffusion)"
        echo ""
        pytest tests/smoke/ \
            -m "smoke and not requires_diffusion" \
            -v --tb=short 2>&1
        ;;
esac

EXIT_CODE=$?

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "  SMOKE TESTS PASSED"
else
    echo "  SMOKE TESTS FAILED (exit code: $EXIT_CODE)"
fi
echo "=========================================="

exit $EXIT_CODE
