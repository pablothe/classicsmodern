# Documentation Index

Complete guide to all documentation in the Modern Classics project.

## Quick Start Guides

### 🚀 [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md)
**Complete step-by-step workflow from book to audiobook**
- Splitting books into chunks
- Translating with automatic deduplication
- Generating and combining audio
- Compressing audiobooks
- Best practices and tips

**Start here if**: You want to translate a book and create an audiobook from scratch.

---

### 📖 [TRANSLATION_WORKFLOW.md](TRANSLATION_WORKFLOW.md)
**Detailed guide for batch translation using local AI**
- How to translate large books (100k+ words)
- Progress tracking and resume capability
- Anti-duplication system explanation
- Troubleshooting translation issues

**Start here if**: You only need translation, or want deep understanding of the translation process.

---

## Reference Documentation

### 🤖 [CLAUDE.md](CLAUDE.md)
**Project overview and architecture for AI assistants**
- Core commands and usage
- System architecture overview
- Model-specific handling
- File organization patterns
- Development notes

**Use this for**: Understanding project architecture, getting command references, or working with Claude Code.

---

### 📚 [LOCAL_READER_README.md](LOCAL_READER_README.md)
**Complete vision and roadmap for the Local Reader project**
- Project overview and goals
- Feature roadmap (MVP → V1.0 → V2.0)
- Mobile app integration plans
- Deployment options
- Technology stack

**Use this for**: Understanding the full vision, roadmap, and future plans.

---

## Issue Tracking & Testing

### ⚠️ [KNOWN_ISSUES.md](KNOWN_ISSUES.md)
**Known issues, workarounds, and solutions**
- Chunk overlap duplication (SOLVED ✅)
- Table of contents in wrong language
- Progress tracking between sessions
- API rate limits and costs
- Workarounds summary

**Use this for**: Troubleshooting problems, understanding limitations, finding solutions.

---

### ✅ [TEST_RESULTS_DEDUPLICATION.md](TEST_RESULTS_DEDUPLICATION.md)
**Validation results for the anti-duplication system**
- Test setup with 5 mini chunks
- Layer 1 (LLM Context) results
- Layer 2 (Exact Match) results
- File comparisons before/after
- Effectiveness analysis

**Use this for**: Understanding how deduplication works, validation evidence, system reliability.

---

## Specialized Guides

### 🎵 [AUDIOBOOK_PLAYBACK_GUIDE.md](AUDIOBOOK_PLAYBACK_GUIDE.md)
**How to play generated audiobooks**
- Desktop playback options
- Mobile playback options
- Playlist formats
- Transfer methods

**Use this for**: Playing your generated audiobooks on various devices.

---

### 📊 [PROGRESS_TRACKING.md](PROGRESS_TRACKING.md)
**Progress tracking implementation**
- How progress is saved
- Resume functionality
- Checkpoint file format
- Manual progress management

**Use this for**: Understanding or debugging progress tracking and resume features.

---

## Key Files by Use Case

### "I want to create my first audiobook"
1. [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) - Complete workflow
2. [KNOWN_ISSUES.md](KNOWN_ISSUES.md) - Common issues to avoid

### "I'm getting errors during translation"
1. [TRANSLATION_WORKFLOW.md](TRANSLATION_WORKFLOW.md) - Translation troubleshooting
2. [KNOWN_ISSUES.md](KNOWN_ISSUES.md) - Known problems and fixes

### "I want to understand the project architecture"
1. [CLAUDE.md](CLAUDE.md) - Technical overview
2. [LOCAL_READER_README.md](LOCAL_READER_README.md) - Project vision

### "I'm hearing duplicate audio at chunk boundaries"
1. [TEST_RESULTS_DEDUPLICATION.md](TEST_RESULTS_DEDUPLICATION.md) - System validation
2. [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md#anti-duplication-system) - How to use it

### "I want to contribute to development"
1. [LOCAL_READER_README.md](LOCAL_READER_README.md) - Roadmap and priorities
2. [KNOWN_ISSUES.md](KNOWN_ISSUES.md) - Known problems to fix
3. [CLAUDE.md](CLAUDE.md) - Architecture and conventions

---

## Recent Updates (January 2026)

### ✨ New Features
- **Two-layer anti-duplication system** - Prevents duplicate audio at chunk boundaries
  - Layer 1: LLM context awareness (~70% prevention)
  - Layer 2: Exact-match failsafe (100% of remaining duplicates)
- **Automatic deduplication** - Runs automatically after batch translation
- **Context-aware translation** - Each chunk receives previous translation as context

### 📝 New Documentation
- [TEST_RESULTS_DEDUPLICATION.md](TEST_RESULTS_DEDUPLICATION.md) - Validation of anti-duplication
- [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) - Complete end-to-end workflow
- This index file

### 🔧 Updated Documentation
- [CLAUDE.md](CLAUDE.md) - Added deduplication architecture
- [TRANSLATION_WORKFLOW.md](TRANSLATION_WORKFLOW.md) - Added anti-duplication section
- [KNOWN_ISSUES.md](KNOWN_ISSUES.md) - Marked chunk overlap as SOLVED
- [LOCAL_READER_README.md](LOCAL_READER_README.md) - Updated roadmap progress

---

## File Organization

```
docs/
├── DOCS_INDEX.md                     # This file
├── WORKFLOW_GUIDE.md                 # Complete workflow (START HERE)
├── TRANSLATION_WORKFLOW.md           # Translation deep-dive
├── CLAUDE.md                         # Architecture reference
├── LOCAL_READER_README.md            # Project vision & roadmap
├── KNOWN_ISSUES.md                   # Issues & workarounds
├── TEST_RESULTS_DEDUPLICATION.md     # Test validation
├── AUDIOBOOK_PLAYBACK_GUIDE.md       # Playback instructions
└── PROGRESS_TRACKING.md              # Progress system docs
```

---

## Quick Command Reference

```bash
# Split book into chunks
python3 local_reader_smart_splitter.py books/YOUR_BOOK/book.md

# Translate chunks (with auto-deduplication)
python3 local_reader_batch_translator.py books/YOUR_BOOK/chunks/ Russian English

# Generate audio from deduplicated files
python3 local_reader_audio.py books/YOUR_BOOK/chunks/translated/deduplicated/

# Combine audio parts
python3 local_reader_audio_combiner.py audiobook_playlist.m3u

# Compress audio
python3 local_reader_audio_compress.py audiobook_COMBINED.mp3 96k
```

---

## Getting Help

1. **Check documentation**: Use this index to find the right guide
2. **Search known issues**: See [KNOWN_ISSUES.md](KNOWN_ISSUES.md)
3. **Review test results**: See [TEST_RESULTS_DEDUPLICATION.md](TEST_RESULTS_DEDUPLICATION.md) for validation
4. **Follow workflow**: Use [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md) step-by-step

---

**Last updated**: January 3, 2026
