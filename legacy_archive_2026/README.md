# Legacy Archive (2026 Cleanup)

This directory contains deprecated documentation and scripts archived during the February 2026 codebase cleanup.

## Why Archived?

The Modern Classics project standardized on:
- **Kokoro TTS** as the ONLY supported TTS system
- **Structured translator** (`structured_translator.py`) with Ollama (100% local)
- **Consolidated documentation** to reduce redundancy

Files here are preserved for historical reference but should **NOT be used** for new work.

## Directory Structure

### orpheus_docs/
**Deprecated TTS engine documentation**
- All Orpheus TTS files (replaced by Kokoro)
- Reason: Orpheus requires NVIDIA GPU, incompatible with Apple Silicon
- Alternative: Use `make_audiobook.py` with Kokoro

### tts_docs/
**TTS comparison and quality documentation**
- TTS engine comparisons (Edge, XTTS, Orpheus vs Kokoro)
- Voice testing guides
- Quality benchmarks
- Reason: Project standardized on Kokoro only, comparisons no longer relevant

### chapter_docs/
**Chapter detection and player feature documentation**
- Architecture details
- Implementation guides
- Feature descriptions
- Reason: Information consolidated into README.md, GUIDE.md, CLAUDE.md

### implementation_summaries/
**Point-in-time implementation summaries**
- RAG system summary
- Job queue summary
- Validation summary
- Sentence chunking fixes
- Reason: Moved to CHANGELOG.md or consolidated into main docs

### test_docs/
**Test-related markdown files**
- Test results
- Test data samples
- AI improvement notes
- Reason: Should be in `tests/` directory or TESTING.md

### translator_scripts/
**Individual model translator scripts**
- `translator_o1_mini.py`
- `translator_o3_mini_high.py`
- `claude_translator.py`
- etc.
- Reason: Replaced by `structured_translator.py` with local Ollama

### openai_scripts/
**OpenAI-dependent scripts archived February 22, 2026**
- `audio_generation.py` - OpenAI TTS via gpt-4o-audio-preview
- `audio_translator.py` - OpenAI-powered translation
- `local_reader_audio.py` - OpenAI TTS via tts-1
- `o3call.py` - OpenAI o3 API wrapper
- `simplify_further.py` - Text simplification via GPT-4o-mini
- `translator.py` - OpenAI translator (all cloud models)
- `generate_audiobook.sh` - Shell wrapper for OpenAI TTS
- Reason: Project is 100% local, no cloud APIs

### utility_scripts/
**Potentially deprecated utility scripts**
- Various one-off utilities
- Superseded by newer consolidated tools

## If You Need Something From Here

1. **Check main docs first** - Information may have been consolidated
2. **Use git history** - Full history preserved in repository
3. **Ask maintainers** - We can help find what you need

## Cleanup Date

- **Archived:** February 10, 2026
- **By:** Audit and cleanup process
- **Reason:** 47% of files were redundant or deprecated

### docs_archived_feb22/
**Documentation archived February 22, 2026**
- FEATURES.md - Obsolete planning docs (AI Chat and Karaoke are now implemented)
- AUDIOBOOK_SERVER.md - Outdated server architecture (info now in CLAUDE.md)
- CLEANUP_SUMMARY_2026.md - One-time cleanup artifact
- QUICK_REFERENCE.md - Redundant with updated README
- TESTING.md - Referenced non-existent CI/CD pipeline
- GUTENBERG_SETUP.md - Info folded into GUIDE.md
- JOB_QUEUE_README.md - Info folded into CLAUDE.md
- AUDIO_TEXT_SYNC.md - Info folded into CLAUDE.md

## Current Documentation

**Use these instead:**
- [README.md](../README.md) - Project overview
- [GUIDE.md](../GUIDE.md) - Complete workflow guide
- [CLAUDE.md](../CLAUDE.md) - Technical reference
- [CHANGELOG.md](../CHANGELOG.md) - Version history

## Current Tools

**Translation:**
- `structured_translator.py` - Structured translator (Ollama, 100% local)
- `structured_translator_v2.py` - Manifest-based translator
- `local_reader_batch_translator.py` - Batch translation

**Audio Generation:**
- `make_audiobook.py` - ONE COMMAND workflow (recommended)
- `local_tts_kokoro.py` - Direct Kokoro TTS
- See `legacy_tts/` for old TTS systems

**Validation:**
- `book_validator.py` - Book quality validation
- `book_processor.py` - Manifest generation

## Questions?

Open an issue on GitHub or check the main documentation.
