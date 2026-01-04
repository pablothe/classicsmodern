# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**modernclassics** is a Python-based system for translating classic literature into modern languages and generating audiobooks using AI. The project processes century-old books through various AI models while preserving Markdown structure and meaning.

## Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
# Create .env file with:
OPENAI_API_KEY=your_api_key_here
```

## Core Commands

### Text Translation

**For single files (cloud-based OpenAI):**
```bash
# List available AI models
python translator.py --list-models

# Translate with default model (o3-mini-high recommended)
python translator.py books/alice_adventures/alices_adventures.md

# Specify model and languages
python translator.py input.md --model o3-mini-high --source-lang German --target-lang "Modern English"

# Custom output directory
python translator.py input.md --output-dir custom_output/
```

**For batch/chunks (local Ollama - RECOMMENDED for large books):**
```bash
# Split book into chunks first
python3 local_reader_smart_splitter.py books/crime_punishment/book.md

# Translate entire directory with automatic deduplication
python3 local_reader_batch_translator.py books/crime_punishment/chunks/ Russian "Modern English"

# This will:
# 1. Translate with context awareness (prevents duplicates)
# 2. Auto-run deduplication as failsafe
# 3. Create clean files in translated/deduplicated/
```

### Audio Generation

**Local TTS with XTTS-v2 (Recommended - $0 cost):**
```bash
# Setup (once)
pip install TTS==0.27.3 && brew install ffmpeg

# Generate audiobook
python local_tts_xtts.py translated.md voice_ref.wav en

# With voice cloning (prepare reference voice first)
python local_tts_xtts.py --prepare-voice sample.m4a voice_ref.wav

# Multi-language: es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh-cn, ja, ko, hu
python local_tts_xtts.py libro.md voz.wav es

# See LOCAL_TTS_GUIDE.md for details
```

**Cloud TTS with OpenAI (Legacy - ~$15/book):**
```bash
python audio_translator.py books/alice_adventures/alices_adventures.md --voice fable
# or: python local_reader_audio.py translated.md fable mp3
```

### Book Processing Utilities
```bash
# Extract from Project Gutenberg
python gutenberg_extractor.py

# Convert EPUB to Markdown
python epub_to_md.py input.epub
```

## Architecture

### Translation System
- **Multi-Model Support**: Supports o1-mini, o1-preview, o3-mini, o3-mini-high, gpt-4o-mini (cloud), and zongwei/gemma3-translator:4b (local via Ollama)
- **Smart Chunking**: Respects Markdown structure, ~250 words per chunk
- **Structure Preservation**: Maintains headers, links, tables, and formatting through translation
- **Context-Aware Translation**: Each chunk receives context from previous chunk to prevent duplicates
- **Two-Layer Deduplication** (NEW):
  - **Layer 1 (LLM Context)**: Translator receives previous chunk's ending as "reference only" to prevent repeating it
  - **Layer 2 (Exact Match)**: Automatic failsafe deduplication catches any duplicates that slip through
  - **Result**: Clean audio with zero repetition at chunk boundaries
- **Auto-Organization**: Automatically places outputs in appropriate `books/[book_name]/` directories

### Audio Generation System

**Local TTS (XTTS-v2) - Primary:**
- **Cost**: Free (fully local processing)
- **Voice Cloning**: Clone any voice with 10-30 second sample
- **Languages**: 16 languages (en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh-cn, ja, ko, hu)
- **Quality**: High-quality, natural prosody with voice matching
- **Post-Processing**: Automatic speed adjustment (1.15x), loudness normalization (-16 LUFS), MP3 conversion
- **Chunking**: Optimized for 500-1500 chars per chunk
- **Speed**: 2-4x slower than realtime (CPU), ~1x realtime (GPU)
- **See**: [LOCAL_TTS_GUIDE.md](LOCAL_TTS_GUIDE.md) for complete documentation

**Cloud TTS (OpenAI) - Legacy:**
- **Cost**: ~$15 per book
- **Text Cleaning**: Removes Markdown formatting for natural speech
- **Voice Options**: 6 preset voices (alloy, echo, fable, onyx, nova, shimmer)
- **Smart Chunking**: Breaks at natural boundaries (~4000 chars), creates playlists
- **Format Support**: wav, mp3, flac with automatic playlist generation

### File Organization Pattern
```
books/
├── [book_name]/
│   ├── [original].md
│   ├── chunks/                                  # Split for large books
│   │   ├── chunk_001.md
│   │   ├── chunk_002.md
│   │   └── translated/
│   │       ├── chunk_001_[language]_4b.md      # Raw translations
│   │       └── deduplicated/                   # ← Use these for audio!
│   │           ├── chunk_001_DEDUPED.md        # Clean, no overlaps
│   │           ├── audio/                      # OpenAI TTS (legacy)
│   │           │   ├── chunk_001_part001.mp3
│   │           │   └── audiobook_playlist.m3u
│   │           └── audio_xtts/                 # Local TTS (recommended)
│   │               ├── raw/                    # Unprocessed WAV
│   │               │   └── chunk_001_chunk001_raw.wav
│   │               ├── chunk_001_chunk001.mp3  # Processed (speed + normalized)
│   │               └── chunk_001_audiobook.m3u # Playlist
│   ├── [book]_[language]_[date]_[model].md     # Single-file translations
│   ├── [book]_part001_[voice]_[date].wav       # Audio parts (OpenAI)
│   └── [book]_audiobook_playlist_[date].m3u    # Playlist
```

## Key Implementation Details

### Model-Specific Handling
- **O1 models**: Don't support system messages, use combined prompts
- **O3 models**: Support temperature and system messages
- **GPT models**: Standard chat completion format

### Translation Quality Features
- Markdown structure analysis and preservation
- Table of contents link ID maintenance  
- Code block and table structure retention
- Automatic post-processing cleanup and verification

### Audio Processing

**Local TTS (XTTS-v2):**
- Voice cloning from 10-30 second reference sample
- Automatic post-processing pipeline:
  - Speed adjustment (1.15x default, reduces "draggy" TTS feel)
  - Loudness normalization (-16 LUFS, audiobook standard)
  - MP3 conversion (128kbps, reduces file size by ~90%)
- Optimal chunk size: 500-1500 characters
- Multi-language support (16 languages)
- Model caching (~1.8GB, downloaded once)

**Cloud TTS (OpenAI - Legacy):**
- Project Gutenberg header/footer removal
- Sentence-boundary splitting for natural pauses
- Playlist creation for sequential playback
- Automatic book directory detection and organization

## Development Notes

### Current Architecture Limitations
- Audio generation may hit API limits with very long texts (use multi-part)
- O1/O3 model parameters differ from standard GPT models
- Chunking strategy optimized for translation quality over speed

### Anti-Duplication System (NEW - Jan 2026)
- **Problem**: Translation chunks use 20-word overlap for context, causing duplicate audio at boundaries
- **Solution**: Two-layer hybrid approach:
  1. **LLM Context (Primary)**: Translator receives previous chunk's ending as context with instruction "DO NOT translate this, it's reference only"
  2. **Exact Match (Failsafe)**: Automatic deduplication detects and removes exact text duplicates between consecutive chunks
- **Effectiveness**:
  - Layer 1 prevents ~70% of duplicates
  - Layer 2 catches 100% of remaining duplicates
- **Result**: Clean, seamless audio with zero repetition
- **Tested**: See `TEST_RESULTS_DEDUPLICATION.md` for validation with 5-chunk test suite

### File Naming Conventions
- Translations: `[original_name]_[target_language]_[YYYYMMDD]_[model].md`
- Audio: `[book]_part[XXX]_[voice]_[timestamp].[format]`
- Original files preserved with `_original.md` suffix when copied to book directories

### Legacy Scripts
Multiple translator variants exist (`translator_o1_mini.py`, `translator_o3_mini_high.py`, etc.) but `translator.py` consolidates all functionality. Legacy scripts maintained for backward compatibility.