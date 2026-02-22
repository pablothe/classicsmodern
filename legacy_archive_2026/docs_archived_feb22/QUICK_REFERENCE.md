# Quick Reference Guide

One-page reference for Modern Classics workflows and file locations.

---

## 📚 Documentation

| File | Purpose |
|------|---------|
| **[README.md](README.md)** | Start here - Project overview & quick start |
| **[GUIDE.md](GUIDE.md)** | Complete workflow guide (translation → audio) |
| **[CLAUDE.md](CLAUDE.md)** | Technical reference for AI assistants |
| **[FEATURES.md](FEATURES.md)** | Feature roadmap & upcoming features |
| **[TESTING.md](TESTING.md)** | Testing guide & CI/CD |
| **[CHANGELOG.md](CHANGELOG.md)** | Version history & test results |

---

## ⚡ ONE COMMAND Workflows

### Create Audiobook from English Book
```bash
python3 make_audiobook.py books/alice_adventures/book.md --voice bf_emma --generate-cover
```

### Translate + Create Audiobook
```bash
# 1. Translate
python3 translator.py books/crime_punishment/book.md --model o3-mini-high

# 2. Generate audio
python3 make_audiobook.py books/crime_punishment/translated.md --generate-cover
```

### Validate Book Before Processing
```bash
python3 book_validator.py books/mybook/book.md --auto-fix
```

---

## 🎙️ Audio Generation

**Kokoro TTS (ONLY supported system):**
```bash
# Direct TTS
python3 local_tts_kokoro.py translated.md --voice bf_emma

# With cover art
python3 local_tts_kokoro.py translated.md --voice bf_emma --generate-cover

# Faster playback
python3 local_tts_kokoro.py translated.md --speed 1.15
```

**Top voices:**
- `bf_emma` - British Female (classics)
- `bm_george` - British Male (classics)
- `af_sky` - American Female (default)
- `am_adam` - American Male
- `am_onyx` - American Male (deep)

**52 voices available:** af_*, am_*, bf_*, bm_*

---

## 🌍 Translation

**Single File (Cloud):**
```bash
python3 translator.py book.md --model o3-mini-high
```

**Large Books (Local/Batch):**
```bash
# 1. Split
python3 local_reader_smart_splitter.py book.md

# 2. Translate with deduplication
python3 local_reader_batch_translator.py chunks/ Russian "Modern English"

# 3. Use deduplicated files for audio
python3 make_audiobook.py chunks/translated/deduplicated/chunk_001_DEDUPED.md
```

**Structured Translation (Preserves Chapters):**
```bash
python3 structured_translator.py book.md \
  --source-lang Latin \
  --target-lang "Modern English" \
  --model ollama:zongwei/gemma3-translator:4b
```

---

## ✅ Validation

**Check Book Quality:**
```bash
# Validate
python3 book_validator.py book.md

# Auto-fix issues
python3 book_validator.py book.md --auto-fix

# Require specific features
python3 book_validator.py book.md --require karaoke,ai_chat
```

**What it validates:**
- Chapter structure (TOC, sequential chapters)
- Text quality (no Gutenberg boilerplate)
- Metadata (title, author)
- Feature readiness (Karaoke, AI chat, Web player)

---

## 📝 Summarization

**Create Condensed Version:**
```bash
# 50% summary
python3 book_summarizer.py translated.md 50

# 10% summary (90% compression)
python3 book_summarizer.py translated.md 10
```

**Then generate audio from summary:**
```bash
python3 make_audiobook.py translated_summarized_50pct.md --generate-cover
```

---

## 🎨 Cover Art

**Generate Cover:**
```bash
# From prompt
python3 generate.py "whimsical Alice in Wonderland scene" --output cover.png

# From book title (uses catalog)
python3 generate.py "$(python3 book_prompts.py 'Moby Dick')" --output cover.png
```

**Integrated with audiobook generation:**
```bash
python3 make_audiobook.py book.md --generate-cover
```

---

## 🌐 Web Server

**Start Server:**
```bash
./start_server.sh
# Access at: http://localhost:8080
```

**Features:**
- Book catalog with cover art
- Audio player with progress tracking
- Job dashboard for processing
- AI chat (ask questions about book)
- Karaoke mode (text sync)

---

## 🧪 Testing

**Run Tests:**
```bash
# All tests
pytest

# Fast tests only
pytest -m "not slow"

# Specific test
pytest tests/unit/test_deduplication.py -v

# With coverage
pytest --cov=. --cov-report=html
```

**Test Structure:**
- `tests/unit/` - Isolated component tests
- `tests/integration/` - Multi-component workflows
- `tests/e2e/` - Complete user scenarios
- `tests/adhoc/` - Manual/exploratory tests

---

## 📂 Project Structure

```
classicsmodern/
├── README.md                          # Start here
├── GUIDE.md                           # Complete workflow guide
├── CLAUDE.md                          # Technical reference
├── make_audiobook.py                  # ONE COMMAND workflow
├── translator.py                      # Unified translator
├── local_tts_kokoro.py               # Kokoro TTS (ONLY supported)
├── book_validator.py                  # Validation tool
├── book_summarizer.py                 # Summarization tool
├── books/                             # Book library
│   └── [book_name]/
│       ├── book.md                    # Source text
│       ├── cover.png                  # Generated cover
│       └── audio_kokoro/              # Generated audio
├── server/                            # Web server
│   ├── audiobook_server.py           # Main server
│   └── static/                        # Web player
├── tests/                             # Test suite
│   ├── unit/                          # Unit tests
│   ├── integration/                   # Integration tests
│   ├── e2e/                          # End-to-end tests
│   └── adhoc/                         # Manual tests
├── legacy_tts/                        # Old TTS systems (deprecated)
└── legacy_archive_2026/              # Archived files (Feb 2026 cleanup)
```

---

## 🚫 Deprecated (Don't Use)

**Legacy TTS Systems:**
- ~~`local_tts_edge.py`~~ → Use `make_audiobook.py` (Kokoro)
- ~~`local_tts_xtts.py`~~ → Use `make_audiobook.py` (Kokoro)
- ~~`local_tts_orpheus.py`~~ → Use `make_audiobook.py` (Kokoro)

**Individual Translators:**
- ~~`translator_o3_mini_high.py`~~ → Use `translator.py --model o3-mini-high`
- ~~`translator_o1_mini.py`~~ → Use `translator.py --model o1-mini`
- (All others) → Use `translator.py --model <name>`

**See `legacy_archive_2026/` for archived files.**

---

## 🆘 Troubleshooting

**Translation Issues:**
- Model not found: `ollama pull zongwei/gemma3-translator:4b`
- Slow translation: Expected ~10 min per 10k words
- Interrupted: Re-run same command to resume

**Audio Issues:**
- TTS not found: `pip install kokoro-tts kokoro-onnx soundfile`
- ffmpeg not found: `brew install ffmpeg`
- No audio: Check venv activated (`source venv/bin/activate`)

**Server Issues:**
- Port in use: `lsof -i :8080` then kill process
- Ollama not found: Install from https://ollama.com
- Model missing: `ollama pull llama3.2:3b`

---

## 📖 Learn More

- **Workflows:** See [GUIDE.md](GUIDE.md)
- **Architecture:** See [CLAUDE.md](CLAUDE.md)
- **Features:** See [FEATURES.md](FEATURES.md)
- **Testing:** See [TESTING.md](TESTING.md)
- **Changes:** See [CHANGELOG.md](CHANGELOG.md)

---

**Last Updated:** February 10, 2026
