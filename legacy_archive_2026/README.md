# Legacy Archive (2026 Cleanup)

This directory contains deprecated documentation and scripts archived during the February 2026 codebase cleanup.

## Why Archived?

The Modern Classics project standardized on:
- **Kokoro TTS** as the ONLY supported TTS system
- **Unified translator** (`translator.py`) instead of per-model scripts
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
- Reason: Replaced by unified `translator.py --model <name>`

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

## Current Documentation

**Use these instead:**
- [README.md](../README.md) - Project overview
- [GUIDE.md](../GUIDE.md) - Complete workflow guide
- [CLAUDE.md](../CLAUDE.md) - Technical reference
- [FEATURES.md](../FEATURES.md) - Feature roadmap
- [TESTING.md](../TESTING.md) - Testing guide
- [CHANGELOG.md](../CHANGELOG.md) - Version history

## Current Tools

**Translation:**
- `translator.py` - Unified translator (all models)
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
