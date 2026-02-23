# Complete User Guide

End-to-end guide for creating audiobooks with Modern Classics. Everything runs locally on your machine — no internet connection required after initial setup.

---

## Table of Contents

1. [Validation](#validation)
2. [Translation](#translation)
3. [Audio Generation](#audio-generation)
4. [Summarization](#summarization)
5. [Cover Art](#cover-art)
6. [Web Server](#web-server)
7. [Troubleshooting](#troubleshooting)

---

## Validation

Always validate books before processing. This catches structural issues early and avoids wasting time on doomed workflows.

```bash
# Validate a book
python3 validate.py books/mybook/book.md

# Auto-fix common issues (Gutenberg boilerplate, missing TOC)
python3 validate.py books/mybook/book.md --auto-fix

# Check readiness for specific features
python3 validate.py books/mybook/book.md --require karaoke,ai_chat
```

**What it checks:**
- Chapter structure (TOC, sequential chapters, no gaps)
- Text quality (no Gutenberg boilerplate, minimum word count)
- Metadata (title, author)
- Feature readiness (Karaoke, AI Chat, Web Player)

**What auto-fix does:**
- Strips Gutenberg header/footer (creates `.bak` backup)
- Generates missing table of contents from chapter markers
- Normalizes structure

**When to validate:**
- Before translation (catch problems early)
- After summarization (verify chapters survived)
- Before audio generation (confirm feature support)

---

## Translation

### Option 1: Structured Translator (recommended)

Preserves chapter structure through translation. Best for most books.

```bash
python3 translate.py books/mybook/book.md \
  --source-lang Latin \
  --target-lang "Modern English" \
  --model ollama:zongwei/gemma3-translator:4b
```

How it works:
1. Pre-validates the source book
2. Parses into blocks (metadata, TOC, chapters)
3. Translates content only (preserves chapter markers)
4. Assembles clean output with auto-generated TOC

### Anti-Duplication System

Batch translation uses 20-word overlap between chunks for context. The system prevents this from creating duplicate audio:

- **Layer 1 (LLM Context):** Each chunk receives the previous chunk's ending as "reference only" context
- **Layer 2 (Exact Match):** Automatic failsafe removes any duplicate text between chunks

Result: Zero repetition at chunk boundaries.

---

## Audio Generation

### One-Command Workflow (recommended)

```bash
python3 make_audiobook.py books/mybook/book.md --voice bf_emma --generate-cover
```

This handles validation, chapter detection, TTS, cover art, and web server registration in a single command. Fully resumable if interrupted.

### Direct Kokoro TTS

For more control over the audio generation step:

```bash
# Basic
python3 audiobook.py translated.md --voice bf_emma

# With cover art
python3 audiobook.py translated.md --voice bf_emma --generate-cover

# Custom speed
python3 audiobook.py translated.md --voice bf_emma --speed 1.15
```

### Voice Options

52 preset voices available. Prefixes: `af_` (American Female), `am_` (American Male), `bf_` (British Female), `bm_` (British Male).

| Voice | Style |
|-------|-------|
| `bf_emma` | British Female — classics |
| `bm_george` | British Male — classics |
| `af_sky` | American Female — default |
| `am_adam` | American Male — general |
| `am_onyx` | American Male — deep |

### Output Structure

```
books/mybook/audio_kokoro/
├── chapter_01.mp3
├── chapter_02.mp3
├── audiobook.m3u          # Playlist
├── metadata.json          # Audio metadata
└── raw/                   # Unprocessed WAV chunks
```

---

## Summarization

Create condensed versions of long books before generating audio.

```bash
# 50% summary (auto-sizes chunks)
python3 summarize.py books/mybook/translated.md 50

# 10% summary (90% compression, larger chunks for context)
python3 summarize.py books/mybook/translated.md 10

# Then generate audio from summary
python3 make_audiobook.py books/mybook/translated_summarized_50pct.md --generate-cover
```

Or use the integrated flag:

```bash
python3 make_audiobook.py books/mybook/book.md --summarize 50 --generate-cover
```

---

## Cover Art

Cover art is generated with Stable Diffusion v1.5 (local, free).

```bash
# Integrated with audiobook generation
python3 make_audiobook.py book.md --generate-cover

# Standalone generation
python3 cover.py "whimsical Alice in Wonderland scene, fantasy illustration" --output cover.png
```

---

## Web Server

### Starting the Server

```bash
# Always use the startup script (handles venv activation)
./start_server.sh

# Server runs at http://localhost:8000
# From phone on same WiFi: http://[your-mac-ip]:8000
```

### Features

- **Book catalog** — browse all audiobooks with cover art
- **Audio player** — chapter navigation, speed control, progress tracking
- **Karaoke mode** — synchronized text highlighting during playback
- **AI chat** — ask questions about the book (requires Ollama with llama3.2:3b)
- **Job dashboard** (`/jobs`) — monitor background translation and audio jobs
- **Gutenberg browser** — search and download public domain books

### Gutenberg Integration

Download books directly from the web interface or CLI:

```bash
# Build catalog (one-time)
python3 server/gutenberg_catalog.py

# Browse and download from web UI at /jobs
# Or via API:
curl -X POST http://localhost:8000/api/jobs/download -d '{"gutenberg_id": 11}'
```

### AI Chat Setup

The AI chat feature requires Ollama running locally:

```bash
brew install ollama
ollama serve
ollama pull llama3.2:3b
```

The server checks Ollama availability on startup and gracefully disables chat if unavailable.

---

## Troubleshooting

### Translation

| Problem | Solution |
|---------|----------|
| Model not found | `ollama pull zongwei/gemma3-translator:4b` |
| Slow translation | Expected ~10 min per 10k words on CPU |
| Interrupted | Re-run same command to resume |

### Audio

| Problem | Solution |
|---------|----------|
| kokoro-onnx not installed | `pip install kokoro-tts kokoro-onnx soundfile` (in venv) |
| ffmpeg not found | `brew install ffmpeg` |
| No audio output | Check venv is activated: `source venv/bin/activate` |

### Server

| Problem | Solution |
|---------|----------|
| Port in use | `lsof -i :8000` then kill the process |
| Ollama not found | Install from https://ollama.com, then `ollama pull llama3.2:3b` |
| Books not showing | Ensure books are in `books/` with audio in `audio_kokoro/` subdirectory |

---

## Further Reading

- **[CLAUDE.md](CLAUDE.md)** — Technical reference, architecture, API endpoints
- **[CHANGELOG.md](CHANGELOG.md)** — Version history and test results
