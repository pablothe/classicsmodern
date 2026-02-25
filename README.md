# Modern Classics

Translate classic literature and generate audiobooks using local AI.

**Works fully offline.** After initial setup (pip install, model download), no internet connection is required. The only feature that uses the internet is downloading books from Project Gutenberg (optional).

## What It Does

- Translates books from any language to any language using local AI
- Generates high-quality audiobooks with Kokoro TTS (52 voices, 100% local)
- Serves audiobooks via web player with Karaoke mode and AI chat
- Downloads books from Project Gutenberg automatically

---

## AI Models

All models run locally. No cloud APIs, no API keys required.

| Model | Purpose | Runtime |
|-------|---------|---------|
| **zongwei/gemma3-translator:4b** | Translation & summarization | Ollama |
| **llama3.2:3b** | AI chat about books | Ollama |
| **Kokoro v1.0** | Text-to-speech (52 voices) | ONNX Runtime |
| **Stable Diffusion v1.5** | Cover art generation | PyTorch |
| **all-MiniLM-L6-v2** | Semantic search (RAG) | sentence-transformers |
| **WhisperX** | Word timing (Karaoke) | PyTorch (optional) |

---

## Quick Start

### Install

```bash
# Create virtual environment (required)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install kokoro-tts kokoro-onnx soundfile
brew install ffmpeg  # macOS
```

### Create an Audiobook (one command)

```bash
python3 make_audiobook.py books/alice_adventures/alices_adventures.md --generate-cover
```

This will:
1. Strip Gutenberg boilerplate (if present)
2. Detect chapters automatically
3. Generate audio with Kokoro TTS
4. Generate cover art
5. Output to `books/alice_adventures/audio_kokoro/`

### Listen

```bash
# Start web server
./start_server.sh

# Open http://localhost:8000 in browser
# Or from phone: http://[your-mac-ip]:8000
```

---

## CLI Scripts

| Script | Purpose |
|--------|---------|
| `make_audiobook.py` | Full pipeline (validate + translate + audio + cover) |
| `translate.py` | Translate a book |
| `audiobook.py` | Generate audiobook from text |
| `summarize.py` | Summarize a book |
| `cover.py` | Generate cover art |
| `validate.py` | Validate book structure |

---

## Voice Options

Kokoro TTS includes 52 preset voices. Top picks:

| Voice | Description | Best for |
|-------|-------------|----------|
| `bf_emma` | British Female | Classics |
| `bm_george` | British Male | Classics |
| `af_sky` | American Female | Default |
| `am_adam` | American Male | General |
| `am_onyx` | American Male (deep) | Drama |

```bash
python3 make_audiobook.py book.md --voice bf_emma --generate-cover
python3 make_audiobook.py book.md --voice am_adam --speed 1.15
```

---

## Translation

For non-English books:

```bash
# Translate with local AI (Ollama)
python3 translate.py books/mybook/book.md \
  --source-lang Latin --target-lang "Modern English" \
  --model zongwei/gemma3-translator:4b

# Then generate audiobook from translation
python3 make_audiobook.py books/mybook/translated.md --generate-cover
```

---

## Summarization

Create condensed audiobooks from long books:

```bash
# 50% of original length
python3 make_audiobook.py book.md --summarize 50 --generate-cover

# Or standalone
python3 summarize.py book.md 50
```

---

## Web Server Features

The web player (`./start_server.sh`) includes:

- **Book catalog** with cover art and search
- **Audio player** with chapter navigation and progress tracking
- **Karaoke mode** -- synchronized text highlighting during playback
- **AI chat** -- ask questions about the book while listening (requires Ollama)
- **Job dashboard** -- monitor translation and audio generation jobs
- **Gutenberg browser** -- search and download public domain books

---

## Documentation

| File | Purpose |
|------|---------|
| [GUIDE.md](GUIDE.md) | Complete workflow guide |
| [CLAUDE.md](CLAUDE.md) | Technical reference and architecture |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

---

## Design Principles

1. **100% local** -- no cloud services, no API keys, no external calls
2. **One command** -- `make_audiobook.py` handles the full pipeline
3. **Resumable** -- interrupted jobs pick up where they left off
4. **Structure-preserving** -- maintains chapters and formatting through all processing

---

## License

MIT
