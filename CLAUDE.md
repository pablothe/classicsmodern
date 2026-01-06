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

### Book Preprocessing (Run First!)

```bash
# Validate book structure before translation/audio
python3 book_preprocessor.py books/mybook/original.md

# Check translation completeness after translation
python3 book_preprocessor.py books/mybook/translated.md
```

**What it does:**
- Detects table of contents (TOC)
- Finds all chapter markers in content (Roman numerals, Markdown headers)
- Validates chapters are sequential (no missing chapters)
- Identifies gaps (e.g., has I, V, VI but missing II, III, IV)
- Compares TOC vs actual content
- Generates JSON metadata for downstream tools

**Output files:**
- `*_preprocessing_report.txt` - Human-readable validation report
- `*_chapter_data.json` - Machine-readable chapter metadata

**Use cases:**
1. **Before translation**: Ensure source book is complete
2. **After translation**: Validate all chapters were translated
3. **Before audio generation**: Confirm chapter count for proper audio splitting

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

### Text Summarization (NEW!)

**Standalone summarization (for already-translated files):**
```bash
# 50% summary (auto uses 2000-word chunks)
python3 book_summarizer.py books/mybook/translated.md 50

# 10% summary / 90% compression (auto uses 5000-word chunks)
python3 book_summarizer.py books/mybook/translated.md 10

# Custom chunk size (override auto-calculation)
python3 book_summarizer.py books/mybook/translated.md 30 1500
```

**What it does:**
- Uses same Ollama LLM as translation (gemma3-translator:4b)
- Auto-scales chunk size based on compression ratio (more compression = larger chunks for better context)
- Preserves Markdown structure (headers, lists, etc.)
- Context-aware (each chunk knows what came before)
- Output: `*_summarized_[percentage]pct.md`

**Auto-scaling chunk sizes:**
- 10% target (90% compression) → 5000 words/chunk (~10 pages)
- 20% target (80% compression) → 4000 words/chunk (~8 pages)
- 30% target (70% compression) → 3000 words/chunk (~6 pages)
- 50% target (50% compression) → 2000 words/chunk (~4 pages)
- 70%+ target (light compression) → 1000 words/chunk (~2 pages)

**Then generate audio:**
```bash
python3 local_tts_xtts.py books/mybook/translated_summarized_50pct.md voice_ref.wav en
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
- **Two-Layer Deduplication**:
  - **Layer 1 (LLM Context)**: Translator receives previous chunk's ending as "reference only" to prevent repeating it
  - **Layer 2 (Exact Match)**: Automatic failsafe deduplication catches any duplicates that slip through
  - **Result**: Clean audio with zero repetition at chunk boundaries
- **Auto-Organization**: Automatically places outputs in appropriate `books/[book_name]/` directories

### Summarization System (NEW!)
- **LLM-Powered**: Uses same Ollama model as translation (gemma3-translator:4b)
- **Adaptive Chunking**: Auto-scales chunk size based on compression ratio
  - More aggressive compression → larger chunks (more context needed)
  - Light compression → smaller chunks (less context needed)
- **Context-Aware**: Each chunk receives context from previous summary to maintain narrative flow
- **Structure Preservation**: Maintains Markdown headers, lists, formatting
- **Compression Range**: 10%-90% (target percentage of original length)
- **Use Cases**:
  - Create condensed audiobooks from long classics
  - Generate executive summaries
  - Reduce listening time while preserving key themes

### Audio Generation System

**Local TTS (XTTS-v2):**
- Free, voice cloning (10-30 sec sample)
- 16 languages, automatic post-processing (speed, normalize, MP3)
- 2-4x slower than realtime (CPU)
- **Chapter Detection**: Automatically detects chapters BEFORE text cleaning, preserves markers, then combines chunks into chapter-based audio files
- **Smart Combining**: Uses FFmpeg to stitch 250-char audio chunks into full chapter files

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