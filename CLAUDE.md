# CLAUDE.md

Technical reference for AI assistants working with this repository.

## Project Overview

**Modern Classics** translates classic literature and generates audiobooks using local and cloud AI.

**Documentation:**
- [README.md](README.md) - Project overview and quick start
- [GUIDE.md](GUIDE.md) - Complete user guide (read this for workflow details)
- [CHANGELOG.md](CHANGELOG.md) - Test results and version history

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

**Local TTS (free, voice cloning):**
```bash
python local_tts_xtts.py translated.md voice_ref.wav en
```

**Cloud TTS (paid, faster):**
```bash
python local_reader_audio.py translated/deduplicated/ --voice fable
python local_reader_audio_combiner.py playlist.m3u
python local_reader_audio_compress.py combined.mp3 96k
```

**See [GUIDE.md](GUIDE.md) for complete audio generation workflow.**

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

**Local TTS (XTTS-v2):**
- Free, voice cloning (10-30 sec sample)
- 16 languages, automatic post-processing (speed, normalize, MP3)
- 2-4x slower than realtime (CPU)

**Cloud TTS (OpenAI):**
- ~$15/book, 6 voices, faster generation
- Smart chunking, playlist generation

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

## Technical Details

### Model-Specific Handling
- **O1 models**: No system messages, use combined prompts
- **O3 models**: Support temperature and system messages
- **GPT models**: Standard chat completion
- **Local (Ollama)**: gemma3-translator:4b, ~16-20 words/sec

### File Naming Conventions
- Translations: `[book]_[language]_[YYYYMMDD]_[model].md`
- Audio: `[book]_part[XXX]_[voice]_[timestamp].[format]`
- Deduplicated: `chunk_XXX_DEDUPED.md`

### Anti-Duplication System
**Problem:** 20-word overlap causes duplicate audio

**Solution:**
1. Layer 1 (LLM): Context from previous chunk marked "reference only"
2. Layer 2 (Exact Match): Automatic cleanup of any duplicates

**Result:** Zero repetition at boundaries (validated in [CHANGELOG.md](CHANGELOG.md))