# Modern Classics

Translate classic literature into modern languages and generate audiobooks using local AI models.

## Overview

**Modern Classics** is a Python-based system for:
- Translating century-old books while preserving their structure
- Generating high-quality audiobooks with voice cloning
- Running entirely on local AI models (no cloud costs)

**Key Features:**
- 🌍 Multi-language translation (16+ languages supported)
- 🎙️ Voice cloning from 10-30 second samples
- 💰 Free local processing (or ~$15/book with cloud TTS)
- 🔄 Smart chunking with automatic deduplication
- 📱 Progress tracking and resume capability

---

## Quick Start

### Installation

```bash
# 1. Install core dependencies
pip install -r requirements.txt

# 2. Install Kokoro TTS (recommended - fast, free, commercial-friendly)
pip install kokoro-tts kokoro-onnx soundfile
brew install ffmpeg  # macOS
# Note: Kokoro models (~335MB) auto-download to ~/.cache/kokoro/ on first use

# 3. (Optional) Set up local translation model for non-English books
brew install ollama  # macOS
ollama pull zongwei/gemma3-translator:4b

# 4. (Optional) For cloud TTS/translation, create .env file
echo "OPENAI_API_KEY=your_key_here" > .env
```

### Create Audiobook - ONE COMMAND! ⭐

**For most books (English, ready to read):**
```bash
# Single command creates complete audiobook with cover art
python3 make_audiobook.py books/alice_adventures/alices_adventures.md --generate-cover

# That's it! Output will be in: books/alice_adventures/audio_kokoro/
# - Chapter MP3 files
# - Cover art PNG
# - Playlist M3U
# - Metadata JSON (for web player)
```

**Common options:**
```bash
# British female voice (recommended for classics)
python3 make_audiobook.py INPUT.md --voice bf_emma --generate-cover

# American male voice + faster playback
python3 make_audiobook.py INPUT.md --voice am_adam --speed 1.15 --generate-cover

# With summarization (50% of original length - great for long books)
python3 make_audiobook.py INPUT.md --summarize 50 --generate-cover
```

**What it does automatically:**
1. ✅ Strips Project Gutenberg boilerplate (if present)
2. ✅ Detects chapters (Roman numerals, numbered lists, markdown headers)
3. ✅ Generates high-quality audio with Kokoro TTS
4. ✅ Creates cover art (if --generate-cover flag used)
5. ✅ Organizes output and registers with web server
6. ✅ Fully resumable (if interrupted, re-run same command)

---

## Advanced Workflows

### For Non-English Books (Translation Required)

**Option 1: Cloud-based (single file)**
```bash
python translator.py books/alice_adventures/alice.md
```

**Option 2: Local AI (large books, recommended)**
```bash
# Split into chunks
python3 local_reader_smart_splitter.py books/crime_punishment/book.md

# Translate with automatic deduplication
python3 local_reader_batch_translator.py books/crime_punishment/chunks/ Russian "Modern English"

# Then create audiobook
python3 make_audiobook.py books/crime_punishment/chunks/translated/deduplicated/chunk_001_DEDUPED.md --generate-cover
```

### Alternative Audio Generation Methods

**Option 1: Local TTS with Kokoro (RECOMMENDED - fast, free, commercial-friendly)**
```bash
# Basic usage (American Female voice)
python3 local_tts_kokoro.py translated.md

# British voice (great for classics)
python3 local_tts_kokoro.py translated.md --voice bf_emma

# With cover art generation
python3 local_tts_kokoro.py translated.md --voice bf_emma --generate-cover
```

**Option 2: Local TTS with XTTS (voice cloning, non-commercial)**
```bash
python local_tts_xtts.py translated.md voice_sample.wav en
# Automatically creates chapter files (e.g., chapter_01.mp3, chapter_02.mp3)
# Plus master playlist for the complete audiobook
```

**Option 2: Cloud TTS (paid, faster)**
```bash
python local_reader_audio.py translated/deduplicated/
python local_reader_audio_combiner.py playlist.m3u
python local_reader_audio_compress.py combined.mp3 96k
```

---

## Documentation

- **[GUIDE.md](GUIDE.md)** - Complete workflow guide (translation + audio)
- **[CLAUDE.md](CLAUDE.md)** - Technical reference and architecture
- **[CHANGELOG.md](CHANGELOG.md)** - Test results and version history

---

## Project Vision

### Current Status (MVP Complete ✅)
- ✅ Full translation pipeline with anti-duplication
- ✅ Local TTS with voice cloning (XTTS-v2)
- ✅ Cloud TTS integration (OpenAI)
- ✅ Audio combining and compression
- ✅ Progress tracking and resume
- 🔄 Web interface (planned)

### Roadmap

**V1.0 - Mobile App** (In Progress)
- React Native app for iOS/Android
- Server auto-discovery on local network
- Full audiobook player with progress tracking
- Background playback and lock screen controls

**V1.5 - Enhanced Local TTS**
- Optimized Orpheus-3B integration
- Voice customization options
- Faster generation speeds

**V2.0 - Advanced Features**
- Adjustable book compression/summarization
- Multi-user support
- CarPlay/Android Auto integration
- Cross-device progress sync

---

## Core Technologies

### Translation
- **Cloud**: OpenAI models (o1-mini, o3-mini-high, gpt-4o-mini)
- **Local**: Ollama with zongwei/gemma3-translator:4b
- **Smart chunking**: ~10k words per chunk with context overlap
- **Anti-duplication**: Two-layer system (LLM context + exact match)

### Audio Generation
- **Local TTS**: XTTS-v2 (free, 16 languages, voice cloning)
- **Cloud TTS**: OpenAI TTS ($15/book, 6 voices)
- **Post-processing**: Speed adjustment, loudness normalization, MP3 conversion

### File Organization
```
books/
├── [book_name]/
│   ├── original.md
│   ├── chunks/
│   │   ├── chunk_001.md
│   │   └── translated/
│   │       ├── chunk_001_english_4b.md      # Raw
│   │       └── deduplicated/                # Clean, use these!
│   │           ├── chunk_001_DEDUPED.md
│   │           └── audio_xtts/
│   │               ├── chunk_001.mp3
│   │               └── playlist.m3u
│   └── book_english_20260105.md             # Single-file translation
```

---

## Key Features

### Anti-Duplication System
Translation chunks use 20-word overlap for context, which can cause duplicate audio. The system prevents this with:

1. **LLM Context (Layer 1)**: Translator receives previous chunk's ending as reference-only context
2. **Exact Match (Layer 2)**: Automatic failsafe removes any duplicate text between chunks

**Result**: Zero repetition at chunk boundaries (validated in [CHANGELOG.md](CHANGELOG.md))

### Voice Cloning
Create audiobooks in any voice with just a 10-30 second sample:
```bash
# 1. Prepare reference voice
python local_tts_xtts.py --prepare-voice sample.m4a voice_ref.wav

# 2. Generate audiobook with cloned voice
python local_tts_xtts.py book.md voice_ref.wav en
```

### Progress Tracking
All long-running operations support resume:
- Translation progress saved to `.translation_progress.json`
- Audio generation can be restarted mid-process
- Re-run the same command to continue where you left off

---

## Common Commands

```bash
# List available AI models
python translator.py --list-models

# Translate with specific model
python translator.py book.md --model o3-mini-high

# Generate audio with voice cloning (local)
python local_tts_xtts.py translated.md voice.wav es

# Generate audio with cloud TTS
python local_reader_audio.py deduplicated/ --voice fable

# Combine audio parts
python local_reader_audio_combiner.py playlist.m3u

# Compress for smaller size
python local_reader_audio_compress.py combined.mp3 96k

# Check translation progress
python check_translation_progress.py books/crime_punishment/chunks/
```

---

## Performance Benchmarks

### Translation (Local AI, 4b model)
| Book Size | Chunks | Time (M1 Mac) |
|-----------|--------|---------------|
| 50k words | 5      | ~50 min       |
| 100k words| 10     | ~100 min      |
| 200k words| 20     | ~200 min      |

### Audio Generation (Local XTTS)
| Duration | Time (CPU) | Time (GPU) |
|----------|------------|------------|
| 1 hour   | ~2-4 hours | ~1 hour    |
| 5 hours  | ~10-20 hrs | ~5 hours   |

### Audio Generation (Cloud OpenAI)
| Duration | Time   | Cost  |
|----------|--------|-------|
| 1 hour   | ~5 min | ~$3   |
| 5 hours  | ~25 min| ~$15  |

---

## Mobile Device Access

### Current: Manual Transfer
- Export audiobook file
- Transfer via AirDrop, USB, or file sharing
- Play in any audio app

### Future: Native Mobile App (V1.0)
- Auto-discover server on local network
- Download books with WiFi
- Full playback controls (speed, sleep timer, bookmarks)
- Progress persistence and sync
- Background playback and lock screen controls

---

## Book Sources

### Project Gutenberg
```bash
python gutenberg_extractor.py
```

### EPUB to Markdown
```bash
python epub_to_md.py input.epub
```

---

## Contributing

### Design Principles
1. **Local-first**: Minimize external dependencies
2. **Structure preservation**: Maintain Markdown formatting
3. **User control**: Transparent process with adjustable parameters
4. **Extensibility**: Support for new models and languages

### Development Setup
```bash
# Clone repository
git clone https://github.com/yourusername/modernclassics.git

# Install dev dependencies
pip install -r requirements.txt

# Run tests
python -m pytest
```

---

## License

MIT License - See LICENSE file for details

---

## Support

- **Issues**: Open an issue on GitHub
- **Documentation**: See [GUIDE.md](GUIDE.md)
- **Examples**: Check `books/` directory for samples

---

**Last Updated**: January 5, 2026
