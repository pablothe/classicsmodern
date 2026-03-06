# Modern Classics

Translate classic literature and generate audiobooks using local AI.

**Works fully offline.** After initial setup (pip install, model download), no internet connection is required. The only feature that uses the internet is downloading books from Project Gutenberg (optional).

## What It Does

- Translates books from any language to any language using local AI
- Generates high-quality audiobooks with Kokoro TTS (52 voices, 100% local)
- Serves audiobooks via web player with e-reader, Karaoke mode, and AI chat
- Multi-user profiles with per-user playback positions and preferences
- Downloads books from Project Gutenberg automatically

---

## AI Models

All models run locally by default. No cloud APIs or API keys required.

Optionally, you can use **OpenAI** or **Anthropic** APIs for translation, summarization, and other text tasks (see [External LLM APIs](#optional-external-llm-apis) below).

| Model | Purpose | Runtime |
|-------|---------|---------|
| **zongwei/gemma3-translator:4b** | Translation & summarization | Ollama |
| **llama3.2:3b** | AI chat about books | Ollama |
| **Kokoro v1.0** | Text-to-speech (52 voices) | ONNX Runtime |
| **Stable Diffusion v1.5** | Cover art generation | PyTorch |
| **all-MiniLM-L6-v2** | Semantic search (RAG) | sentence-transformers |
| **WhisperX** | Word timing (Karaoke) | PyTorch (optional) |
| **OpenAI GPT models** | Translation, summarization, chat (optional) | OpenAI API |
| **Anthropic Claude models** | Translation, summarization, chat (optional) | Anthropic API |

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
| `epub_to_md.py` | Convert EPUB to Markdown |

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

## Documentation

| File | Purpose |
|------|---------|
| [GUIDE.md](GUIDE.md) | Complete workflow guide |
| [CLAUDE.md](CLAUDE.md) | Technical reference and architecture |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

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

## Design Principles

1. **Local by default** -- runs fully offline with Ollama, with optional cloud LLM support
2. **One command** -- `make_audiobook.py` handles the full pipeline
3. **Resumable** -- interrupted jobs pick up where they left off
4. **Structure-preserving** -- maintains chapters and formatting through all processing

---

## License

MIT
