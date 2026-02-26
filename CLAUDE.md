# CLAUDE.md

Technical reference for AI assistants working with this repository.

## Project Overview

**Modern Classics** translates classic literature and generates audiobooks using 100% local AI. No cloud services, no API keys, no external calls.

**Documentation:**
- [README.md](README.md) - Project overview and quick start
- [GUIDE.md](GUIDE.md) - Complete user guide (read this for workflow details)
- [CHANGELOG.md](CHANGELOG.md) - Test results and version history

## AI Models Used

All models run 100% locally. No cloud APIs, no API keys.

| Model | Purpose | Runtime | Notes |
|-------|---------|---------|-------|
| **zongwei/gemma3-translator:4b** | Translation & summarization | Ollama | Primary translation model, ~16-20 words/sec |
| **zongwei/gemma3-translator:1b** | Translation (lightweight) | Ollama | Faster alternative, lower quality |
| **llama3.2:3b** | AI chat / Q&A about books | Ollama | Used by web player's chat feature |
| **Kokoro v1.0** | Text-to-speech (52 voices) | ONNX Runtime | Apache 2.0, ~335MB, auto-downloaded |
| **Stable Diffusion v1.5** | Cover art generation | PyTorch (MPS/CUDA/CPU) | runwayml/stable-diffusion-v1-5 |
| **all-MiniLM-L6-v2** | Semantic embeddings (RAG) | sentence-transformers | Used by AI chat for context retrieval |
| **WhisperX base** | Word-level timing (Karaoke) | PyTorch | Optional, for karaoke text sync |

**Required services:**
- **Ollama** must be running locally (`ollama serve`) for translation, summarization, and AI chat
- All other models are loaded directly (no server needed)

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

# 6. Optional: EPUB conversion support
pip install ebooklib markdownify
```

**Why venv is required:**
- The audiobook server runs inside venv and uses `venv/bin/python3` for subprocess calls
- Kokoro TTS dependencies (`kokoro-onnx`, `soundfile`) must be installed in venv
- Without venv, audio generation will fail with "kokoro-onnx library not installed"

**Offline operation:**
After initial setup, the entire system works offline:
- **Translation**: Ollama runs locally (no API calls)
- **TTS**: Kokoro runs locally via ONNX Runtime (no API calls)
- **Cover Art**: Stable Diffusion runs locally (no API calls)
- **Web Server**: Serves on local network only
- The only feature requiring internet is **Gutenberg downloads** (optional)

**Server startup (ALWAYS use start_server.sh):**
```bash
# Correct (uses venv automatically)
./start_server.sh

# Incorrect (will fail - missing dependencies)
python3 server/audiobook_server.py
```

## Quick Start - ONE COMMAND WORKFLOW

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
# - bf_emma (British Female - default for make_audiobook.py)
# - bm_george (British Male - classics)
# - af_sky (American Female - default for audiobook.py)
# - am_adam (American Male)
# - am_onyx (American Male - deep)
# Total: 52 voices (af_*, am_*, bf_*, bm_*)
```

---

## CLI Scripts

Seven thin CLI wrappers at the project root, each importing from `lib/`:

| Script | Purpose | Example |
|--------|---------|---------|
| `make_audiobook.py` | Full pipeline (validate + translate + audio + cover) | `python3 make_audiobook.py book.md --generate-cover` |
| `translate.py` | Translate a book (Ollama, local) | `python3 translate.py book.md --source-lang Latin --target-lang English` |
| `audiobook.py` | Generate audiobook (Kokoro TTS) | `python3 audiobook.py translated.md --voice bf_emma` |
| `summarize.py` | Summarize a book (Ollama, local) | `python3 summarize.py book.md 50` |
| `cover.py` | Generate cover art (Stable Diffusion) | `python3 cover.py "fantasy scene" --output cover.png` |
| `validate.py` | Validate book structure | `python3 validate.py book.md --auto-fix` |
| `epub_to_md.py` | Convert EPUB to Markdown | `python3 epub_to_md.py book.epub output_dir/` |

## Advanced Workflows

### Book Validation

```bash
# Validate book for all features
python3 validate.py books/mybook/book.md

# Auto-fix common issues (Gutenberg boilerplate, missing TOC)
python3 validate.py books/mybook/book.md --auto-fix

# Require specific features
python3 validate.py books/mybook/book.md --require karaoke,ai_chat

# JSON output for scripting
python3 validate.py books/mybook/book.md --json

# Validate all books recursively
python3 validate.py books/ --recursive --verbose

# Auto-fix without creating .bak backup
python3 validate.py books/mybook/book.md --auto-fix --no-backup

# Migrate older manifests to v3.0 (adds paragraph registry)
python3 validate.py books/ --recursive --migrate-paragraphs
```

**What it validates:**
- Chapter structure - TOC, sequential chapters, no gaps
- Text quality - No Gutenberg boilerplate, minimum length
- Metadata - Title, author detection
- Feature readiness - Karaoke, AI chat, web player support

**Feature requirements:**
- **Karaoke Mode** - Requires: clean text + chapters
- **AI Chat** - Requires: 3+ sequential chapters
- **Web Player** - Requires: 1+ chapter

**Auto-fix capabilities:**
- Strip Gutenberg boilerplate (header/footer)
- Generate missing table of contents
- Suggest metadata additions

### Text Translation

```bash
# Translate a book (structured, chapter-preserving)
python3 translate.py books/mybook/book.md \
  --source-lang Latin \
  --target-lang "Modern English" \
  --model zongwei/gemma3-translator:4b

# Skip translating title/author metadata
python3 translate.py books/mybook/book.md \
  --target-lang "Modern English" --no-translate-metadata

# What it does:
# 1. PRE-VALIDATES source (fails fast if incomplete)
# 2. PARSES into blocks (metadata, TOC, chapters)
# 3. TRANSLATES content ONLY (preserves chapter markers)
# 4. ASSEMBLES clean output (auto-generates TOC)
# Result: All chapters present, structure preserved
```

### Text Summarization

```bash
# 50% summary (auto uses 2000-word chunks)
python3 summarize.py books/mybook/translated.md 50

# 10% summary / 90% compression (auto uses 5000-word chunks)
python3 summarize.py books/mybook/translated.md 10

# Custom chunk size (override auto-calculation)
python3 summarize.py books/mybook/translated.md 30 1500
```

**Auto-scaling chunk sizes:**
- 10% target (90% compression) -> 5000 words/chunk (~10 pages)
- 20% target (80% compression) -> 4000 words/chunk (~8 pages)
- 30% target (70% compression) -> 3000 words/chunk (~6 pages)
- 50% target (50% compression) -> 2000 words/chunk (~4 pages)
- 70%+ target (light compression) -> 1000 words/chunk (~2 pages)

### Cover Art Generation

```bash
# Generate cover from any prompt
python3 cover.py "whimsical Alice in Wonderland scene, fantasy illustration" --output alice.png

# Custom size and quality
python3 cover.py "dark Victorian mystery" --output cover.png --width 512 --height 768 --steps 50

# Auto-generate prompt from book name (prompt arg required but overridden by --book)
python3 cover.py "" --book "Alice in Wonderland" --output cover.png
```

### Audio Generation

```bash
# Use the unified audiobook maker (recommended)
python3 make_audiobook.py books/mybook/book.md --voice bf_emma --generate-cover

# Additional make_audiobook.py options:
# --lang en-us          Language code (default: en-us)
# --chunk-size 800      Audio chunk size (default: 800)
# --no-normalize        Skip text normalization
# --no-mp3              Keep WAV format (skip MP3 conversion)
# --output-dir DIR      Custom output directory
# --no-word-timings     Skip karaoke timing generation
# --non-interactive     No prompts (for scripting)

# Or use audiobook.py directly
python3 audiobook.py translated.md --voice bf_emma

# audiobook.py options:
# --voice VOICE         Voice ID (default: af_sky)
# --speed SPEED         Playback speed multiplier (default: 1.0)
# --language LANG       Language code (default: en-us)
# --output-dir DIR      Output directory (default: auto)

# Custom speed
python3 audiobook.py translated.md --speed 1.15

# Top voices:
# - bf_emma (British Female - default for make_audiobook.py)
# - af_sky (American Female - default for audiobook.py)
# - bm_george (British Male - George, classics)
# - am_adam (American Male - Adam)
# - am_onyx (American Male - Onyx, deep)
# Total: 52 voices available (af_*, am_*, bf_*, bm_*, etc.)
```

### Web Server & Mobile Access

```bash
# ALWAYS use the startup script (handles venv activation)
./start_server.sh

# Server runs on http://localhost:8000
# Access from phone: http://[your-mac-ip]:8000
```

**Web Interface Features:**
- **Book Catalog** (`/`) - Browse audiobooks with cover art, grid/list view, filter chips (Not Started / In Progress / Finished)
- **Audio Player** - Chapter-based playback with progress tracking, persistent now-playing bar
- **E-Reader** - Fullscreen reader with Listen/Read tabs, sync toggle for read-while-listening
- **Multi-User Profiles** - Netflix-style profile picker with isolated playback and settings
- **Job Dashboard** (`/jobs`) - Monitor translation/audio generation jobs
- **AI Chat** - Ask questions about book content (requires 3+ chapters)
- **Karaoke Mode** - Synchronized text highlighting during playback

**API Endpoints:**
```
# Books
GET  /api/books                                              # List all books
GET  /api/books/{book_id}                                    # Get book details
GET  /api/books/{book_id}/variants/{variant_id}/audio/{file_index}  # Stream audio
GET  /api/books/{book_id}/cover                              # Get cover image
GET  /api/books/{book_id}/text                               # Get all chapter text
GET  /api/books/{book_id}/text/{chapter_num}                 # Get chapter text
GET  /api/books/{book_id}/chunk-manifest                     # Chapter metadata
GET  /api/books/{book_id}/word-timings                       # Karaoke sync data
GET  /api/books/{book_id}/word-timings/{chapter}             # Per-chapter timings
GET  /api/books/{book_id}/paragraph-timings                  # Paragraph timing data
DELETE /api/books/{book_id}/variants/{variant_id}            # Delete variant

# Playback
GET  /api/playback/{book_id}/{variant_id}                    # Get playback position
POST /api/playback/{book_id}/{variant_id}                    # Save playback position
GET  /api/playback/all                                       # All positions (library progress)

# Users
GET  /api/users                                              # List all users
POST /api/users                                              # Create new user
GET  /api/users/{user_id}                                    # Get user details
PATCH /api/users/{user_id}                                   # Update user profile
DELETE /api/users/{user_id}                                  # Delete user

# Jobs
GET  /api/jobs                     # List jobs
GET  /api/jobs/stats               # Job statistics
GET  /api/jobs/{job_id}            # Job details
POST /api/jobs/download            # Download from Gutenberg
POST /api/jobs/translate           # Start translation job
POST /api/jobs/audiobook           # Generate audiobook
POST /api/jobs/cover               # Generate cover art
POST /api/jobs/cleanup             # Clean up old jobs
DELETE /api/jobs/{job_id}          # Delete a job

# Pipeline (alternative audiobook generation)
POST /api/pipeline/generate                                  # Start generation
GET  /api/pipeline/jobs                                      # List pipeline jobs
GET  /api/pipeline/jobs/{job_id}                             # Job status
DELETE /api/pipeline/jobs/{job_id}                           # Cancel job
POST /api/pipeline/cleanup                                   # Cleanup
GET  /api/pipeline/detect-language/{book_id}/{file_name}     # Detect language
GET  /api/pipeline/source-files/{book_id}                    # List source files

# Gutenberg
GET  /api/gutenberg/catalog        # Browse catalog
GET  /api/gutenberg/search         # Search books
POST /api/gutenberg/download       # Download a book
GET  /api/gutenberg/downloads      # List downloads
GET  /api/gutenberg/downloads/{job_id} # Download status
GET  /api/gutenberg/stats          # Catalog stats

# Other
POST /api/ask                      # AI chat about books
GET  /api/health                   # Health check
```

## Architecture

### Project Structure

```
classicsmodern/
├── make_audiobook.py          # CLI: Full pipeline
├── translate.py               # CLI: Translation
├── audiobook.py               # CLI: Audio generation
├── summarize.py               # CLI: Summarization
├── cover.py                   # CLI: Cover art
├── validate.py                # CLI: Book validation
├── epub_to_md.py              # CLI: EPUB to Markdown conversion
├── start_server.sh            # Server startup
├── requirements.txt
│
├── lib/                       # Core library package
│   ├── config.py              # Configuration (models, paths)
│   ├── utils.py               # Shared utilities
│   ├── book/
│   │   ├── processor.py       # BookProcessor (chapter detection, TOC, Gutenberg stripping)
│   │   ├── manifest.py        # ManifestManager (checkpoints, resume)
│   │   ├── validator.py       # Book validation (structure, features)
│   │   ├── metadata.py        # Metadata extraction
│   │   ├── catalog.py         # Book catalog for server
│   │   └── normalizer.py      # Markdown normalization
│   ├── translation/
│   │   ├── engine.py          # OllamaTranslator (core translation)
│   │   ├── structured.py      # Structure-preserving translation
│   │   ├── splitter.py        # Smart text splitting
│   │   └── deduplicate.py     # Chunk deduplication
│   ├── audio/
│   │   ├── kokoro.py          # KokoroAudioGenerator (TTS)
│   │   ├── preprocessor.py    # Audio text preprocessing
│   │   ├── word_timings.py    # Word-level timing (Karaoke)
│   │   └── chapter_metadata.py # Chapter metadata generation
│   ├── cover/
│   │   ├── generator.py       # Stable Diffusion cover generation
│   │   └── prompts.py         # Book-specific prompt catalog
│   └── summarize/
│       └── engine.py          # BookSummarizer (LLM summarization)
│
├── server/                    # Web server (FastAPI)
│   ├── audiobook_server.py    # Main server + API routes
│   ├── audiobook_pipeline.py  # Audiobook pipeline
│   ├── book_health.py         # Book health checks
│   ├── job_queue.py           # Background job queue
│   ├── job_database.py        # SQLite job persistence
│   ├── job_handlers/          # Job processing handlers
│   │   ├── translate_handler.py
│   │   ├── download_handler.py
│   │   ├── pipeline_handler.py
│   │   └── cover_handler.py
│   ├── language_detector.py   # Language detection
│   ├── text_extractor.py      # Text extraction
│   ├── llm_chat.py            # AI chat (Ollama)
│   ├── hybrid_rag.py          # RAG retrieval
│   ├── question_classifier.py # Question classification
│   ├── semantic_retrieval.py  # Embedding search
│   ├── gutenberg_downloader.py # Gutenberg download
│   ├── gutenberg_catalog.py   # Gutenberg catalog
│   ├── users_db.py            # Multi-user profile database
│   └── static/                # Web UI assets
│       ├── player.html/css/js # Audio player + library
│       ├── reader.js          # Fullscreen e-reader
│       ├── jobs.html/css/js   # Job dashboard
│       ├── pipeline.js        # Pipeline UI
│       ├── karaoke.js         # Karaoke mode
│       └── manifest.json      # PWA manifest
│
├── scripts/                   # Utility scripts
│   └── reset_books.py         # Reset book data
├── templates/                 # HTML templates (legacy)
├── books/                     # Book data
└── tests/                     # Test suite
```

### Book Manifest System

The project uses a unified manifest system for consistent chapter handling:

- **`lib/book/processor.py`** - Single source of truth for book structure
  - Detects chapters using 14+ patterns (Roman numerals, markdown headers, numbered lists, etc.)
  - Strips Gutenberg boilerplate automatically
  - Generates table of contents when missing
  - Creates JSON manifest with all metadata and checkpoints

- **`book_manifest.json`** - Per-book structure file (v3.0):
  ```json
  {
    "version": "3.0",
    "chapters": [...],
    "checkpoints": { "translation": {...}, "audio": {...} },
    "metadata": { "title": "...", "author": "...", "language": "..." },
    "toc_markdown": "..."
  }
  ```
  v3.0 adds a paragraph registry per chapter with stable IDs (`ch01_p001`, etc.), character offsets, word counts, and content hashes. These flow through translation, audio generation, and word timings to enable paragraph-level audio sync.

### Translation System
- **Model**: zongwei/gemma3-translator:4b via Ollama (100% local)
- **Smart Chunking**: Respects Markdown structure, ~10k words per chunk
- **Structure Preservation**: Maintains headers, links, tables, and formatting
- **Context-Aware Translation**: Each chunk receives context from previous chunk
- **Two-Layer Deduplication**:
  - Layer 1 (LLM Context): Previous chunk ending as "reference only"
  - Layer 2 (Exact Match): Automatic failsafe catches remaining duplicates

### Audio System
- **Model**: Kokoro v1.0 via ONNX Runtime
- **Quality**: Superior to Edge-TTS/XTTS, rivals commercial APIs
- **Performance**: 31x faster than alternatives
- **Features**: 52 voices, Apple Silicon GPU (MPS), Apache 2.0 license
- **Chapter Detection**: Detects from raw markdown before text cleaning
- **Audio Intros**: Generates spoken front matter (title, author, epigraphs, dedications)

### Summarization System
- **Model**: zongwei/gemma3-translator:4b via Ollama (same as translation)
- **Adaptive Chunking**: Auto-scales chunk size based on compression ratio
- **Context-Aware**: Each chunk receives context from previous summary

### Cover Art System
- **Model**: Stable Diffusion v1.5 (runwayml/stable-diffusion-v1-5)
- **Hardware**: Apple Silicon GPU (MPS) or CPU fallback
- **Output**: 512x512 PNG, customizable

### File Organization Pattern
```
books/
├── [book_name]/
│   ├── book.md                    # Original/source text
│   ├── book_manifest.json         # Unified structure (chapters, checkpoints)
│   ├── cover.png                  # Generated cover art
│   ├── audio_kokoro/              # Audio output (Kokoro TTS)
│   │   ├── raw/                   # Unprocessed WAV chunks
│   │   ├── chapter_01.mp3         # Chapter-based files (processed)
│   │   ├── audiobook.m3u          # Master playlist
│   │   └── metadata.json          # Audio metadata
│   ├── chunks/                    # Split for large books (batch translation)
│   │   ├── chunk_001.md
│   │   └── translated/
│   │       └── deduplicated/      # Clean, no overlaps
│   ├── [book]_[language]_[date]_[model].md   # Single-file translations
│   └── [book]_summarized_50pct.md             # Summarized versions
```

## Technical Details

### Anti-Duplication System
**Problem:** 20-word overlap causes duplicate audio

**Solution:**
1. Layer 1 (LLM): Context from previous chunk marked "reference only"
2. Layer 2 (Exact Match): Automatic cleanup of any duplicates

**Result:** Zero repetition at boundaries (validated in [CHANGELOG.md](CHANGELOG.md))

### File Naming Conventions
- Translations: `[book]_[language]_[YYYYMMDD]_[model].md`
- Audio: `chapter_[XX].mp3`
- Deduplicated: `chunk_XXX_DEDUPED.md`
