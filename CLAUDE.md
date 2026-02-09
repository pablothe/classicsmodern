# CLAUDE.md

Technical reference for AI assistants working with this repository.

## Project Overview

**Modern Classics** translates classic literature and generates audiobooks using local and cloud AI.

**Documentation:**
- [README.md](README.md) - Project overview and quick start
- [GUIDE.md](GUIDE.md) - Complete user guide (read this for workflow details)
- [CHANGELOG.md](CHANGELOG.md) - Test results and version history

## Environment Setup

**IMPORTANT: This project requires a Python virtual environment (venv) to work correctly.**

```bash
# 1. Create virtual environment (Python 3.11+ recommended)
python3 -m venv venv

# 2. Activate virtual environment
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install Kokoro TTS (REQUIRED for audiobook generation)
pip install kokoro-tts kokoro-onnx soundfile

# 5. Install system dependencies
brew install ffmpeg  # macOS
# or apt-get install ffmpeg  # Linux

# 6. Set up environment variables (optional, for translation)
# Create .env file with:
OPENAI_API_KEY=your_api_key_here
```

**Why venv is required:**
- The audiobook server runs inside venv and uses `venv/bin/python3` for subprocess calls
- Kokoro TTS dependencies (`kokoro-onnx`, `soundfile`) must be installed in venv
- Without venv, audio generation will fail with "kokoro-onnx library not installed"

**Server startup (ALWAYS use start_server.sh):**
```bash
# Correct (uses venv automatically)
./start_server.sh

# Incorrect (will fail - missing dependencies)
python3 server/audiobook_server.py
```

## Quick Start - ONE COMMAND WORKFLOW ⭐

**For most use cases, use the unified audiobook maker:**

```bash
# Create complete audiobook from any book (ONE COMMAND!)
python3 make_audiobook.py books/alice_adventures/alices_adventures.md --generate-cover

# That's it! This will:
# 1. Strip Gutenberg boilerplate automatically
# 2. Detect chapters (Roman numerals, numbered lists, markdown headers)
# 3. Generate high-quality audio with Kokoro TTS (52 voices, commercial-friendly)
# 4. Generate cover art
# 5. Register with web server for playback
# 6. Create organized output in books/{book_name}/audio_kokoro/
```

**Common options:**
```bash
# British female voice (recommended for classics)
python3 make_audiobook.py INPUT.md --voice bf_emma --generate-cover

# American male voice + faster playback
python3 make_audiobook.py INPUT.md --voice am_adam --speed 1.15

# With summarization (50% of original length)
python3 make_audiobook.py INPUT.md --summarize 50 --generate-cover

# Available voices:
# - bf_emma (British Female - classics)
# - bm_george (British Male - classics)
# - af_sky (American Female - default)
# - am_adam (American Male)
# - am_onyx (American Male - deep)
# Total: 52 voices (af_*, am_*, bf_*, bm_*)
```

**Requirements:**
```bash
pip install kokoro-tts kokoro-onnx soundfile
brew install ffmpeg  # macOS
```

---

## Advanced Workflows

### Book Validation (RECOMMENDED - for feature readiness)

**New unified validation tool for Karaoke and AI features:**

```bash
# Validate book for all features
python3 book_validator.py books/mybook/book.md

# Auto-fix common issues (Gutenberg boilerplate, missing TOC)
python3 book_validator.py books/mybook/book.md --auto-fix

# Require specific features
python3 book_validator.py books/mybook/book.md --require karaoke,ai_chat

# JSON output for scripting
python3 book_validator.py books/mybook/book.md --json
```

**What it validates:**
- ✅ **Chapter structure** - TOC, sequential chapters, no gaps
- ✅ **Text quality** - No Gutenberg boilerplate, minimum length
- ✅ **Metadata** - Title, author detection
- ✅ **Feature readiness** - Karaoke, AI chat, web player support

**Feature requirements:**
- **Karaoke Mode** - Requires: clean text + chapters
- **AI Chat** - Requires: 3+ sequential chapters
- **Web Player** - Requires: 1+ chapter

**Auto-fix capabilities:**
- Strip Gutenberg boilerplate (header/footer)
- Generate missing table of contents
- Suggest metadata additions

**Output example:**
```
✅ VALID
Feature support: 3/3 features ready
  ✅ Karaoke
  ✅ Ai_Chat
  ✅ Web_Player
```

**Integration with processing scripts:**
- `book_summarizer.py` - Auto-validates output after summarization
- `local_tts_kokoro.py` - Pre-flight validation before audio generation
- Both scripts show feature readiness and suggest fixes

**Use cases:**
1. **Before translation**: Ensure source book is complete
2. **After summarization**: Validate chapters preserved
3. **Before audio generation**: Confirm Karaoke/AI support
4. **CI/CD**: Automated quality gates

**Legacy tool (still available):**
```bash
# Old preprocessing tool (basic chapter detection only)
python3 book_preprocessor.py books/mybook/book.md
```

### Text Translation

**NEW: Structured Translator (RECOMMENDED - Preserves Chapter Structure):**
```bash
# Validate and translate in one workflow (guaranteed complete)
python3 structured_translator.py books/mybook/book.md \
  --source-lang Latin \
  --target-lang "Modern English" \
  --model ollama:zongwei/gemma3-translator:4b

# What it does:
# 1. PRE-VALIDATES source (fails fast if incomplete)
# 2. PARSES into blocks (metadata, TOC, chapters)
# 3. TRANSLATES content ONLY (preserves chapter markers)
# 4. ASSEMBLES clean output (auto-generates TOC)
# Result: All chapters present, structure preserved

# With OpenAI (faster, costs money):
python3 structured_translator.py books/mybook/book.md \
  --source-lang Latin \
  --target-lang "Modern English" \
  --model openai:o3-mini-high

# Available models:
# - ollama:zongwei/gemma3-translator:4b (free, local, accurate)
# - openai:o3-mini-high (paid, cloud, fast)
# - openai:gpt-4o-mini (paid, cloud, cheap)
```

**Why Structured Translator?**
- ✅ Pre-validates before translation (no wasted time)
- ✅ Translates chapter-by-chapter (progress tracking)
- ✅ Preserves structure (markers never corrupted)
- ✅ Guaranteed completeness (all chapters or fail)
- ✅ Auto-generates clean TOC from markers

---

**Legacy: For single files (cloud-based OpenAI):**
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

### Cover Art Generation (NEW!)

**Modular design: Two separate scripts for flexibility**

**1. generate.py** - Core image generator (does ONE thing: text → image)
```bash
# Generate cover from any prompt
python3 generate.py "whimsical Alice in Wonderland scene, fantasy illustration" --output alice.png

# Custom size and quality
python3 generate.py "dark Victorian mystery" --output cover.png --width 512 --height 768 --steps 50
```

**2. book_prompts.py** - Book-specific prompt generator (optional helper)
```bash
# Get prompt for known book
python3 book_prompts.py "Alice in Wonderland"
# Output: "Book cover art, whimsical dreamlike scene, surreal fantasy forest..."

# Use in pipeline
python3 generate.py "$(python3 book_prompts.py 'Moby Dick')" --output moby.png
```

**Integrated workflow (automatic with audiobook generation):**
```bash
# Add --generate-cover flag to local_tts_xtts.py
python3 local_tts_xtts.py translated.md voice.wav en --generate-cover
```

**What it does:**
- **generate.py**: Pure function (prompt → PNG), no hardcoded book logic
- **book_prompts.py**: Optional catalog of 16+ book styles
- Modular: Swap out prompt generator, use custom prompts, or add your own
- Uses Stable Diffusion v1.5 (local, free)
- Runs on Apple Silicon GPU (MPS), CUDA, or CPU
- Generates 512x512 PNG images (customizable)

**Requirements:**
```bash
pip install diffusers torch transformers accelerate
```

### Audio Generation

**IMPORTANT: This project uses Kokoro TTS ONLY. Legacy TTS scripts (Edge, XTTS, Orpheus) are deprecated and archived in `legacy_tts/`.**

**Local TTS - Kokoro (ONLY SUPPORTED SYSTEM):**
```bash
# Use the unified audiobook maker (recommended)
python3 make_audiobook.py books/mybook/book.md --voice bf_emma --generate-cover

# Or use Kokoro directly
python3 local_tts_kokoro.py translated.md --voice bf_emma

# British female voice (great for classics)
python3 local_tts_kokoro.py translated.md --voice bf_emma

# British male voice with cover art
python3 local_tts_kokoro.py translated.md --voice bm_george --generate-cover

# Custom speed
python3 local_tts_kokoro.py translated.md --speed 1.15

# Top voices:
# - af_sky (American Female - Sky, DEFAULT)
# - bf_emma (British Female - Emma, classics)
# - bm_george (British Male - George, classics)
# - am_adam (American Male - Adam)
# - am_onyx (American Male - Onyx, deep)
# Total: 52 voices available (af_*, am_*, bf_*, bm_*, etc.)
```

**Why Kokoro Only?**
- Apache 2.0 license (commercial-friendly, unlike XTTS-v2)
- 31× faster than alternatives (6.5s vs 203s per passage for Bark)
- 100% local inference via ONNX Runtime (no API calls, unlike Edge-TTS)
- Quality rivals commercial APIs (superior to Edge/XTTS)
- 52 preset voices (American, British, male/female) - no voice cloning needed
- Apple Silicon GPU acceleration (MPS) - no NVIDIA GPU required
- Requires: `pip install kokoro-tts kokoro-onnx soundfile`
- Models: Auto-downloaded to ~/.cache/kokoro/ (~335MB, one-time)

**Virtual Environment Setup:**
```bash
# Create virtual environment with Python 3.11+ (tested with 3.11, 3.13)
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
venv\Scripts\activate     # Windows

# Install dependencies
pip install kokoro-tts kokoro-onnx soundfile
pip install -r requirements.txt
brew install ffmpeg  # macOS
```

**Legacy TTS Systems (DEPRECATED - See `legacy_tts/README.md`):**
- ~~Edge-TTS~~ - Requires Microsoft API (not truly local), inferior quality
- ~~XTTS-v2~~ - Non-commercial license (AGPL), slow, 250-char limit
- ~~Orpheus~~ - Requires NVIDIA GPU (incompatible with Apple Silicon)

**These scripts are archived in `legacy_tts/` and should NOT be used for new audiobooks.**

**See [GUIDE.md](GUIDE.md) for complete audio generation workflow.**

### Web Server & Mobile Access

**Starting the Server:**
```bash
# ALWAYS use the startup script (handles venv activation)
./start_server.sh

# Server runs on http://localhost:8080
# Access from phone: http://[your-mac-ip]:8080
```

**Web Interface Features:**
- **Book Catalog** (`/`) - Browse all audiobooks with cover art
- **Audio Player** - Chapter-based playback with progress tracking
- **Job Dashboard** (`/jobs`) - Monitor translation/audio generation jobs
- **AI Chat** - Ask questions about book content (requires 3+ chapters)
- **Karaoke Mode** - Synchronized text highlighting during playback

**API Endpoints:**
```
GET  /api/books                    # List all books
GET  /api/books/{book_id}          # Get book details
GET  /api/books/{book_id}/audio    # Stream audio
POST /api/playback/{book_id}       # Save playback position
POST /api/jobs/download            # Download from Gutenberg
POST /api/jobs/translate           # Start translation job
POST /api/jobs/audiobook           # Generate audiobook
```

## Architecture

### Book Manifest System (NEW - February 2026)
The project now uses a unified manifest system for consistent chapter handling:

- **`book_processor.py`** - Single source of truth for book structure
  - Detects chapters using 14+ patterns (Roman numerals, markdown headers, numbered lists, etc.)
  - Strips Gutenberg boilerplate automatically
  - Generates table of contents when missing
  - Creates JSON manifest with all metadata and checkpoints
  - Handles edge cases like Alice in Wonderland (all chapters on one line)

- **`book_manifest.json`** - Human-readable structure containing:
  ```json
  {
    "chapters": [...],           // All chapters with content
    "checkpoints": {              // Per-chapter progress tracking
      "translation": {...},
      "audio": {...}
    },
    "metadata": {...},            // Title, author, language
    "toc_markdown": "..."         // Generated table of contents
  }
  ```

- **Manifest-Based Pipeline**:
  - `structured_translator_v2.py` - Uses manifest chapters for translation
  - `local_tts_kokoro_v2.py` - Uses manifest for audio boundaries
  - `manifest_utils.py` - Shared utilities for checkpoint management
  - Perfect chapter alignment across all processes
  - Resume from exact chapter after interruption

- **Usage**:
  ```bash
  # Generate manifest (one time)
  python3 book_processor.py books/mybook/book.md

  # Use manifest for translation
  python3 structured_translator_v2.py books/mybook/book_manifest.json --target-lang Spanish

  # Use manifest for audio
  python3 local_tts_kokoro_v2.py books/mybook/book_manifest.json --voice bf_emma
  ```

### Web Server & Job Queue System
- **FastAPI Server**: Full-featured audiobook server with web dashboard (`server/audiobook_server.py`)
  - REST API for book catalog and metadata
  - Audio streaming with HTTP range requests
  - Device-specific playback position tracking
  - Auto-discovery of books in `books/` directory
  - CORS enabled for mobile access
- **Unified Job Queue**: Background job processing system (`server/job_queue.py`)
  - Download books from Project Gutenberg catalog
  - Translate books with real-time progress tracking
  - Generate audiobooks with pipeline integration
  - SQLite database for job persistence (`jobs.db`)
  - Web dashboard at `/jobs` for monitoring
- **AI Chat Integration**: LLM-powered Q&A about book content
  - Hybrid RAG system for context retrieval
  - Semantic search with embeddings
  - Question classification for targeted responses

### Translation System
- **Multi-Model Support**: Supports o1-mini, o1-preview, o3-mini, o3-mini-high, gpt-4o-mini (cloud), and zongwei/gemma3-translator:4b (local via Ollama)
- **Smart Chunking**: Respects Markdown structure, ~10k words per chunk (updated from ~250 for better context)
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

### Cover Art Generation System (NEW!)
- **Model**: Stable Diffusion v1.5 (runwayml/stable-diffusion-v1-5)
- **Hardware Acceleration**: Apple Silicon GPU (MPS) or fallback to CPU
- **Output**: 512x512 PNG images
- **Customization**:
  - Custom prompts for specific artistic styles
  - Adjustable guidance scale (7.5 default)
  - Book-aware prompt generation from content
- **Use Cases**:
  - Generate audiobook cover art
  - Create promotional imagery
  - Visualize scenes from classic literature

### Audio Generation System

**Local TTS - Kokoro (ONLY SUPPORTED SYSTEM):**
- **Model**: Kokoro TTS with ONNX Runtime
- **Quality**: Superior to Edge-TTS/XTTS, rivals commercial APIs
- **Performance**: 31× faster than alternatives (6.5s vs 203s per passage)
- **Features**:
  - 52 preset voices (American/British, male/female)
  - Apple Silicon GPU acceleration (MPS)
  - 100% local inference (no API calls)
  - Apache 2.0 license (commercial-friendly)
  - Automatic chapter detection and combining
  - FFmpeg post-processing (normalization, MP3)
- **Chapter Detection Architecture** (Fixed Feb 2026):
  - Detects chapters from raw markdown BEFORE text cleaning
  - Preserves TOC structure and chapter markers
  - Sequential file naming (chapter_01.mp3, chapter_02.mp3)
  - Maps chapter positions accurately to clean text
- **Usage**: `python3 local_tts_kokoro.py translated.md --voice bf_emma`

**Cloud TTS (OpenAI - Optional):**
- ~$15/book, 6 voices, faster generation
- Smart chunking, playlist generation
- Used via `local_reader_audio.py` for legacy workflows

### File Organization Pattern
```
books/
├── [book_name]/
│   ├── book.md                                 # Original/source text
│   ├── book_manifest.json                     # NEW: Unified structure (chapters, checkpoints)
│   ├── metadata.json                           # Legacy metadata (being replaced by manifest)
│   ├── cover.png                               # Generated cover art
│   ├── audio_kokoro/                           # PRIMARY audio output (Kokoro TTS)
│   │   ├── raw/                               # Unprocessed WAV chunks
│   │   │   └── [book]_chunk001_raw.wav
│   │   ├── chapter_01.mp3                     # Chapter-based files (processed)
│   │   ├── chapter_02.mp3
│   │   ├── audiobook.m3u                      # Master playlist
│   │   └── metadata.json                      # Audio metadata
│   ├── chunks/                                 # Split for large books (batch translation)
│   │   ├── chunk_001.md
│   │   ├── chunk_002.md
│   │   └── translated/
│   │       ├── chunk_001_[language]_4b.md     # Raw translations
│   │       └── deduplicated/                  # Clean, no overlaps
│   │           └── chunk_001_DEDUPED.md       # Use for audio generation
│   ├── [book]_[language]_[date]_[model].md    # Single-file translations
│   ├── [book]_summarized_50pct.md             # Summarized versions
│   └── legacy_audio/                          # Old TTS outputs (deprecated)
│       ├── audio_xtts/                        # XTTS voice cloning
│       └── audio_orpheus/                     # Orpheus TTS
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