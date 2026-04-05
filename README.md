# Modern Classics

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)

Translate classic literature and generate audiobooks using local AI.

**Works fully offline.** After initial setup, no internet connection is required. The only feature that uses the internet is downloading books from Project Gutenberg (optional).

---

## What It Does

- Translates books from any language to any language using local AI
- Generates high-quality audiobooks with Kokoro TTS (52 voices, 100% local)
- Serves audiobooks via web player with e-reader, Karaoke mode, and AI chat
- Multi-user profiles with per-user playback positions and preferences
- Downloads books from Project Gutenberg automatically

---

## Prerequisites

Before installing, make sure you have:

| Requirement | Version | Install |
|-------------|---------|---------|
| **Python** | 3.11+ | [python.org](https://www.python.org/downloads/) |
| **Ollama** | Latest | [ollama.com](https://ollama.com/) |
| **FFmpeg** | Latest | `brew install ffmpeg` (macOS) / `sudo apt install ffmpeg` (Linux) |

**System requirements:**
- ~2 GB disk space for AI models (downloaded automatically on first run)
- 8 GB RAM minimum (16 GB recommended for cover art generation)
- macOS (Apple Silicon recommended) or Linux
- Windows: untested, but should work with WSL

---

## Quick Start

### 1. Install

```bash
# Clone the repository
git clone https://github.com/your-username/classicsmodern.git
cd classicsmodern

# Create virtual environment (required — see note below)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

> **Why is venv required?** The server uses `venv/bin/python3` for subprocess calls. Without venv, audio generation will fail with "kokoro-onnx library not installed".

### 2. Pull the Ollama models

```bash
ollama pull zongwei/gemma3-translator:4b
ollama pull llama3.2:3b  # optional, for AI chat
```

### 3. Create an Audiobook (one command)

```bash
python3 make_audiobook.py books/alice_adventures/alices_adventures.md --generate-cover
```

This will:
1. Strip Gutenberg boilerplate (if present)
2. Detect chapters automatically
3. Generate audio with Kokoro TTS
4. Generate cover art with Stable Diffusion
5. Output to `books/alice_adventures/audio_kokoro/`

### 4. Listen

```bash
# Start the web server
./start_server.sh

# Open in browser
# http://localhost:8000
# Or from your phone: http://[your-mac-ip]:8000
```

---

## AI Models

All models run locally by default. No cloud APIs or API keys required.

| Model | Purpose | Runtime |
|-------|---------|---------|
| **zongwei/gemma3-translator:4b** | Translation & summarization | Ollama |
| **llama3.2:3b** | AI chat about books | Ollama |
| **Kokoro v1.0** | Text-to-speech (52 voices) | ONNX Runtime |
| **Stable Diffusion v1.5** | Cover art generation | PyTorch |
| **all-MiniLM-L6-v2** | Semantic search (RAG) | sentence-transformers |
| **WhisperX** | Word timing (Karaoke) | PyTorch (optional) |

Optionally, you can use **OpenAI** or **Anthropic** APIs for text tasks (see [External LLM APIs](#optional-external-llm-apis) below).

---

## CLI Scripts

| Script | Purpose | Example |
|--------|---------|---------|
| `make_audiobook.py` | Full pipeline (validate + translate + audio + cover) | `python3 make_audiobook.py book.md --generate-cover` |
| `translate.py` | Translate a book | `python3 translate.py book.md --target-lang English` |
| `audiobook.py` | Generate audiobook from text | `python3 audiobook.py book.md --voice bf_emma` |
| `summarize.py` | Summarize a book | `python3 summarize.py book.md 50` |
| `cover.py` | Generate cover art | `python3 cover.py "fantasy scene" --output cover.png` |
| `validate.py` | Validate book structure | `python3 validate.py book.md --auto-fix` |
| `epub_to_md.py` | Convert EPUB to Markdown | `python3 epub_to_md.py book.epub output/` |

---

## Voice Options

Kokoro TTS includes 52 preset voices. Top picks:

| Voice | Description | Best for |
|-------|-------------|----------|
| `bf_emma` | British Female | Classics (default) |
| `bm_george` | British Male | Classics |
| `af_sky` | American Female | General |
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

## Web Player Features

The web player (`./start_server.sh`) includes:

- **Audible-style library** with cover art, grid/list toggle, and filter chips (Not Started / In Progress / Finished) showing time remaining
- **Audio player** with chapter navigation, progress tracking, and persistent now-playing bar
- **E-reader** with fullscreen reading, Listen/Read tabs, and sync toggle for read-while-listening
- **Multi-user profiles** -- Netflix-style profile picker with isolated playback positions and settings
- **Karaoke mode** -- synchronized text highlighting during playback
- **AI chat** -- ask questions about the book while listening (requires Ollama)
- **Multi-language tracks** -- switch between text and audio language variants
- **Job dashboard** -- monitor translation and audio generation jobs
- **Gutenberg browser** -- search and download public domain books

---

## Optional: External LLM APIs

By default everything runs locally with Ollama. To use OpenAI or Anthropic instead:

1. Install the optional package:
   ```bash
   pip install openai      # for OpenAI
   pip install anthropic   # for Anthropic
   ```

2. Configure via `.env` file (copy from `.env.example`):
   ```bash
   cp .env.example .env
   # Then edit .env:
   LLM_PROVIDER=openai          # or anthropic
   LLM_MODEL=gpt-4o-mini        # optional, uses provider default
   OPENAI_API_KEY=sk-...        # your API key
   ```

3. Or pass directly via CLI:
   ```bash
   python3 translate.py book.md --provider openai --api-key sk-...
   python3 make_audiobook.py book.md --llm-provider anthropic
   ```

4. Or configure from the web UI: Settings page (gear icon) lets you set provider, model, and API keys.

External LLM support applies to: translation, summarization, cover prompt generation, language detection, and AI chat. TTS (Kokoro) and image generation (Stable Diffusion) always run locally.

---

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| `kokoro-onnx library not installed` | venv not activated | Run `source venv/bin/activate` before starting |
| `Connection refused` on translation | Ollama not running | Run `ollama serve` in another terminal |
| Server won't start | Missing venv or dependencies | Always use `./start_server.sh`, not `python3 server/audiobook_server.py` directly |
| Cover art generation is slow | No GPU acceleration | Normal on CPU (~2 min). Apple Silicon uses MPS automatically |
| `ffmpeg: command not found` | FFmpeg not installed | `brew install ffmpeg` (macOS) or `sudo apt install ffmpeg` (Linux) |
| Audio sounds robotic | Wrong language code | Make sure `--lang` matches the text language (default: `en-us`) |

---

## Documentation

| File | Purpose |
|------|---------|
| [GUIDE.md](GUIDE.md) | Complete workflow guide |
| [CLAUDE.md](CLAUDE.md) | Technical reference and architecture |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

---

## Design Principles

1. **Local by default** -- runs fully offline with Ollama, with optional cloud LLM support
2. **One command** -- `make_audiobook.py` handles the full pipeline
3. **Resumable** -- interrupted jobs pick up where they left off
4. **Structure-preserving** -- maintains chapters and formatting through all processing

---

## Contributing

Contributions are welcome! Here's how to get started:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Make your changes
4. Run the tests: `python3 -m pytest tests/`
5. Commit and push your branch
6. Open a pull request

If you find a bug or have a feature request, please [open an issue](https://github.com/your-username/classicsmodern/issues).

---

## License

MIT
