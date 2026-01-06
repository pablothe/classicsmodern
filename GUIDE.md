# Complete User Guide

End-to-end guide for translating classic literature and generating audiobooks.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Translation Workflow](#translation-workflow)
3. [Audio Generation](#audio-generation)
4. [Playback Options](#playback-options)
5. [Troubleshooting](#troubleshooting)
6. [Advanced Topics](#advanced-topics)

---

## Quick Start

### Full Workflow (6 Steps)

```bash
# 0. Preprocess and validate book structure (RECOMMENDED FIRST STEP)
python3 book_preprocessor.py books/crime_punishment/book.md

# 1. Split book into chunks
python3 local_reader_smart_splitter.py books/crime_punishment/book.md

# 2. Translate with automatic deduplication
python3 local_reader_batch_translator.py books/crime_punishment/chunks/ Russian "Modern English"

# 3. Validate translation completeness
python3 book_preprocessor.py books/crime_punishment/translated/chunk_001_english.md

# 4. Generate audio from deduplicated files (auto-detects chapters)
python local_tts_xtts.py translated/deduplicated/chunk_001_DEDUPED.md voice.wav en

# 5. (Optional) Combine existing chunks into chapters retroactively
python3 combine_chapters.py translated.md audio_xtts/

# 6. (Optional) Compress for smaller file size
python3 local_reader_audio_compress.py chapter_01.mp3 96k
```

---

## Book Preprocessing (IMPORTANT!)

### Why Preprocess?

Before translating or generating audio, you should **always** preprocess your book to:
1. **Detect chapter structure** - Find all chapters and validate they're sequential
2. **Identify missing content** - Catch incomplete translations early
3. **Validate TOC** - Ensure table of contents matches actual chapters
4. **Plan audio production** - Know exactly how many chapter files to expect

### Usage

```bash
python3 book_preprocessor.py books/mybook/original.md
```

**Output:**
- Console report showing TOC, chapters, and validation results
- `original_preprocessing_report.txt` - Human-readable analysis
- `original_chapter_data.json` - Machine-readable chapter metadata

### Example Output

```
======================================================================
BOOK PREPROCESSING REPORT
======================================================================
File: crime_punishment.md
Size: 650,000 characters, 100,000 words

TABLE OF CONTENTS: 18 entries found
   1. Chapter 1: Part I (line 15)
   2. Chapter 2: Part I (line 16)
   ...

CHAPTERS IN CONTENT: 18 found
   1. I. (line 120, type: roman_standalone)
   2. II. (line 5234, type: roman_standalone)
   ...

VALIDATION:
  ✅ All 18 chapters present and sequential

TOC vs CONTENT:
  ✅ TOC and content match (18 chapters)
======================================================================
```

### When to Preprocess

✅ **ALWAYS run before translation** - Ensures source is complete
✅ **Run after translation** - Validates all chapters were translated
✅ **Run before audio** - Confirms chapter structure for proper splitting
❌ **Don't run on chunked files** - Run on complete book files only

---

## Translation Workflow

### Single File Translation (Small Books)

**Using Cloud AI (OpenAI):**
```bash
# List available models
python translator.py --list-models

# Translate with default model (o3-mini-high recommended)
python translator.py books/alice_adventures/alice.md

# Specify model and languages
python translator.py input.md \
  --model o3-mini-high \
  --source-lang German \
  --target-lang "Modern English"

# Custom output directory
python translator.py input.md --output-dir custom_output/
```

**Models available:**
- `o3-mini-high` - Best quality (recommended)
- `o3-mini` - Good quality, faster
- `o1-mini` - Older model
- `gpt-4o-mini` - Fast, good for simple text

---

### Batch Translation (Large Books)

**Step 1: Split into Chunks**

```bash
python3 local_reader_smart_splitter.py books/crime_punishment/book.md
```

**What it does:**
- Splits at natural boundaries (chapters, sections)
- Default: 10,000 words per chunk
- Creates `chunks/` directory with numbered files
- Generates manifest file with chunk summary

**Custom chunk size:**
```bash
python3 local_reader_smart_splitter.py book.md 5000  # 5,000 words per chunk
```

**Output:**
```
chunks/
├── chunk_001.md
├── chunk_002.md
├── chunk_003.md
└── chunks_manifest.txt
```

---

**Step 2: Translate Chunks**

```bash
python3 local_reader_batch_translator.py books/crime_punishment/chunks/ Russian Spanish
```

**Features:**
- **Context-aware**: Passes previous translation as context to prevent duplicates
- **Auto-deduplication**: Runs failsafe cleanup after translation
- **Resume support**: Interrupted? Re-run to continue where you left off
- **Progress tracking**: Shows ETA and completion percentage
- **Error recovery**: Continues even if one chunk fails

**What happens:**
1. Translates each chunk using local AI (Ollama)
2. Layer 1: LLM receives context from previous chunk
3. Layer 2: Automatic deduplication removes any overlaps
4. Saves to `translated/` and `translated/deduplicated/`

**Output:**
```
translated/
├── chunk_001_spanish_4b.md          # Raw translation
├── chunk_002_spanish_4b.md
├── .translation_progress.json       # Resume checkpoint
└── deduplicated/                    # ← Use these for audio!
    ├── chunk_001_DEDUPED.md         # Clean, no duplicates
    └── chunk_002_DEDUPED.md
```

**Progress tracking:**
- Saves checkpoint after each chunk
- Re-run same command to resume
- Check progress: `python check_translation_progress.py chunks/`

---

### Anti-Duplication System

Translation chunks use 20-word overlap for context, which can cause duplicate audio. The system prevents this with **two layers**:

#### Layer 1: LLM Context (Primary Prevention ~70%)

When translating chunk N+1:
1. Takes last 2 sentences from chunk N (translated)
2. Includes as "context for reference only"
3. Instructs LLM: "Do NOT translate this context"

**Result:** LLM naturally avoids repeating context.

#### Layer 2: Exact Match (Failsafe 100%)

After translation completes:
1. Compares end of chunk N with start of chunk N+1
2. Finds exact text matches
3. Removes duplicates from chunk N+1
4. Saves to `deduplicated/` directory

**Result:** Zero repetition at chunk boundaries.

**Manual deduplication (if needed):**
```bash
python3 local_reader_deduplicate.py translated/ "*_spanish.md"
```

---

## Audio Generation

### Option 1: Local TTS (Free, Voice Cloning)

**Best for:** Zero cost, voice cloning, multi-language support

#### Setup (One-time)

```bash
pip install TTS==0.27.3
brew install ffmpeg  # macOS
# or: sudo apt install ffmpeg  # Linux
```

#### Basic Usage

```bash
# Simple generation (default voice)
python local_tts_xtts.py translated_book.md

# With voice cloning (recommended)
python local_tts_xtts.py book.md voice_ref.wav en

# Multi-language examples
python local_tts_xtts.py libro.md voz.wav es    # Spanish
python local_tts_xtts.py livre.md voix.wav fr   # French
python local_tts_xtts.py buch.md stimme.wav de  # German
```

**Supported languages:** `en`, `es`, `fr`, `de`, `it`, `pt`, `pl`, `tr`, `ru`, `nl`, `cs`, `ar`, `zh-cn`, `ja`, `ko`, `hu`

**Output format:** The script automatically detects chapters (marked with Roman numerals like "I.", "II.", "III.") and combines audio into chapter-based files. Each audiobook will have one audio file per chapter, making it easy to navigate like a playlist where each "song" is a chapter.

---

#### Voice Cloning

Clone any voice with a 10-30 second sample:

```bash
# Option 1: Extract from existing audio
ffmpeg -i audiobook.mp3 -ss 00:01:00 -t 20 sample.mp3

# Option 2: Record yourself
# Use QuickTime Player: File > New Audio Recording

# Prepare reference for XTTS
python local_tts_xtts.py --prepare-voice sample.mp3 voice_ref.wav

# Generate with cloned voice
python local_tts_xtts.py book.md voice_ref.wav en
```

**Best results:**
- 10-30 seconds of clear speech
- No background music or noise
- Consistent mic distance
- Single speaker

---

#### Chapter-Based Output

**How it works:**

The script automatically detects and preserves chapters during audio generation:

1. **Before processing**: Scans source text for chapter markers (Roman numerals like "I.", "II.", "III." or Markdown headers like "# Chapter 1")
2. **During text cleaning**: Preserves chapter markers while removing other Markdown formatting
3. **During chunking**: Tracks which text chunks belong to which chapter
4. **During audio generation**: Generates 250-character chunks for optimal TTS quality
5. **After generation**: Automatically combines chunks into chapter files using FFmpeg
6. **Final output**: Creates both individual chapter MP3 files AND a master playlist

**Result:** Each audiobook is like a music album where each "song" is a chapter, allowing easy navigation in any audio player.

**Supported chapter formats:**
- Roman numerals: `I.`, `II.`, `III.`, `IV.`, `V.`, etc.
- Markdown headers: `# Chapter 1`, `## Part 2`, `# CHAPTER III`

**Example output:**
```
audio_xtts/
├── book_chapter_01.mp3  (Chapter 1 - 15 chunks combined)
├── book_chapter_02.mp3  (Chapter 2 - 12 chunks combined)
├── book_chapter_03.mp3  (Chapter 3 - 18 chunks combined)
├── book_audiobook_20260105.m3u  (Master playlist)
└── raw/  (Original 250-char chunks for re-processing)
```

---

#### Automatic Post-Processing

Every audio chunk is automatically:
1. **Speed adjusted**: 1.15x faster (reduces robotic feel)
2. **Normalized**: -16 LUFS (audiobook standard)
3. **Converted to MP3**: 128kbps (~90% smaller than WAV)

Raw unprocessed files saved in `audio_xtts/raw/` for re-processing.

**Customize defaults** in [`local_tts_xtts.py:430`](local_tts_xtts.py#L430):
```python
result = generator.generate_audiobook(
    input_file,
    chunk_size=1500,     # 500-1500 recommended
    speed=1.15,          # 1.0-2.0 (try 1.25 for faster)
    normalize=True,      # Loudness normalization
    to_mp3=True          # False to keep WAV
)
```

---

#### Performance

- **Speed**: 2-4x slower than realtime (1 min audio = 2-4 min processing)
- **Memory**: 4-6 GB RAM during generation
- **First run**: +1-2 min for model download (~1.8GB, cached after)
- **Full book (18 chunks)**: 3-6 hours (run overnight)

**Cost comparison:**
- **Local TTS**: $0, 3-6 hours
- **OpenAI TTS**: ~$36, 30-60 min

---

### Option 2: Cloud TTS (Paid, Faster)

**Best for:** Quick results, no local setup, high quality

#### Setup

```bash
# Create .env file
echo "OPENAI_API_KEY=your_key_here" > .env
```

#### Usage

```bash
# From deduplicated files
python3 local_reader_audio.py books/crime_punishment/chunks/translated/deduplicated/

# Different voice
python3 local_reader_audio.py translated/ --voice alloy
```

**Available voices:** `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`

**Cost:** ~$0.015/1000 characters (~$15-40 per full book)

**Output:**
```
audio/
├── chunk_001_part001_fable.mp3
├── chunk_001_part002_fable.mp3
└── audiobook_playlist.m3u
```

---

### Combine Audio Parts

```bash
python3 local_reader_audio_combiner.py audiobook_playlist.m3u

# Specify output name
python3 local_reader_audio_combiner.py playlist.m3u my_audiobook.mp3
```

**What it does:**
- Combines all parts using ffmpeg (fast, no re-encoding)
- Creates single MP3 file
- Preserves audio quality

**Output:** `audiobook_COMBINED.mp3`

---

### Compress Audio (Optional)

```bash
python3 local_reader_audio_compress.py audiobook_COMBINED.mp3 96k
```

**Bitrate options:**
- `64k` - Very compressed (smallest, still good)
- `96k` - **Recommended** (best balance)
- `128k` - Higher quality (larger file)

**Results:**
- Original: 72.8 MB
- Compressed (96k): 43.7 MB (40% reduction)
- Conversion to mono (speech doesn't need stereo)

---

## Playback Options

### Option 1: Web Player (Desktop)

**Best for:** Progress tracking, chapter navigation

```bash
python serve_audiobook.py books/crime_punishment/audio/
```

**Features:**
- Progress saving (localStorage)
- Speed control (0.5x - 2x)
- Skip controls (15s forward/back)
- Chapter navigation
- Keyboard shortcuts:
  - `Space`: Play/Pause
  - `←`: Skip back 15s
  - `→`: Skip forward 15s

---

### Option 2: Combined Single File

**Best for:** Mobile devices, sharing, standard players

```bash
# Already combined in previous step
# Transfer to phone via:
# - AirDrop (macOS → iOS)
# - USB cable
# - File sharing apps
# - Email to yourself

# Play in any audio app:
# - Apple Music/iTunes
# - VLC
# - Spotify (local files)
```

---

### Option 3: Playlist (M3U)

**Best for:** Quick listening, desktop media players

```bash
# macOS
open audiobook_playlist.m3u

# Or drag-and-drop into VLC, QuickTime, etc.
```

**Recommended players:**
- **macOS**: VLC, QuickTime, Music/iTunes
- **Windows**: VLC, Windows Media Player, Foobar2000
- **Linux**: VLC, Audacious, Clementine

---

### Comparison Table

| Feature | Web Player | Combined File | Playlist |
|---------|-----------|---------------|----------|
| Progress Saving | ✅ Auto | ❌ Player-dependent | ❌ Player-dependent |
| Speed Control | ✅ 0.5x-2x | ✅ Player-dependent | ✅ Player-dependent |
| Skip Controls | ✅ 15s | ✅ Player-dependent | ✅ Player-dependent |
| Chapter Navigation | ✅ Click parts | ❌ Single file | ✅ Individual parts |
| Mobile Friendly | ⚠️ Browser | ✅ Everywhere | ✅ Everywhere |
| Offline Support | ⚠️ Local only | ✅ Full | ✅ Full |
| Easy Sharing | ❌ | ✅ Single file | ⚠️ Multiple files |

---

## Troubleshooting

### Translation Issues

**Model not found**
```bash
ollama pull zongwei/gemma3-translator:4b
```

**Translation is slow**
- Expected: ~10 min per 10k-word chunk on CPU
- Solution: Run overnight or use GPU
- Alternative: Use cloud models (faster, costs money)

**Translation interrupted**
- Good news: Progress is auto-saved!
- Fix: Re-run same command to resume

**Translation quality varies**
- Use 4b model (not 1b) for better quality
- Increase chunk size for more context
- Try cloud models for critical sections

---

### Audio Issues

**Audio has duplicates at chunk boundaries**
- Check: Are you using files from `deduplicated/`?
- Fix: Regenerate audio from `translated/deduplicated/*.md`
- Manual fix: `python3 local_reader_deduplicate.py translated/`

**TTS not found**
```bash
pip install --force-reinstall TTS==0.27.3
```

**ffmpeg not found**
```bash
brew install ffmpeg           # macOS
sudo apt install ffmpeg       # Linux
```

**Out of memory (local TTS)**
- Reduce chunk_size to 800 in code
- Close other applications
- Use cloud TTS instead

**Robotic sound (local TTS)**
- Increase speed to 1.25x
- Use better reference voice (cleaner, 20-30 sec)
- Record in quiet room

**Voice doesn't match**
- Use longer reference (20-30 sec minimum)
- Ensure single speaker, no background noise
- Record at consistent distance

---

### General Issues

**Permission denied**
```bash
chmod +x local_reader_*.py
```

**No files found**
- Check file pattern matches (default: `*.md`)
- Verify you're in correct directory
- Use absolute paths

**Web player won't load**
```bash
# Check if port is in use
lsof -i :8000

# Use different port
python serve_audiobook.py audio/ 8080
```

**Progress not saving (web player)**
- Clear browser cache
- Check localStorage is enabled
- Try different browser

---

## Advanced Topics

### Custom Configuration

Edit [`local_reader_config.py`](local_reader_config.py):

```python
# Translation model
default_translation_model: str = "zongwei/gemma3-translator:4b"

# Chunk size
chunk_size_words: int = 10000  # Smaller = more chunks

# Context overlap
context_overlap_words: int = 20  # For coherent translation
```

---

### Performance Benchmarks

**Translation (Local AI, 4b model, M1 Mac):**
| Book Size | Chunks | Time |
|-----------|--------|------|
| 50k words | 5      | ~50 min |
| 100k words| 10     | ~100 min |
| 200k words| 20     | ~200 min |

**Audio Generation (Local XTTS):**
| Duration | CPU Time | GPU Time |
|----------|----------|----------|
| 1 hour   | 2-4 hrs  | ~1 hr    |
| 5 hours  | 10-20 hrs| ~5 hrs   |

**Audio Generation (Cloud OpenAI):**
| Duration | Time | Cost |
|----------|------|------|
| 1 hour   | ~5 min | ~$3 |
| 5 hours  | ~25 min | ~$15 |

---

### File Organization

```
books/
├── [book_name]/
│   ├── original.md
│   ├── chunks/                              # For large books
│   │   ├── chunk_001.md
│   │   ├── chunks_manifest.txt
│   │   └── translated/
│   │       ├── chunk_001_english_4b.md      # Raw translations
│   │       ├── .translation_progress.json   # Resume checkpoint
│   │       └── deduplicated/                # ← Use these for audio!
│   │           ├── chunk_001_DEDUPED.md     # Clean, no duplicates
│   │           ├── audio/                   # Cloud TTS output
│   │           │   ├── chunk_001_part001.mp3
│   │           │   └── audiobook_playlist.m3u
│   │           └── audio_xtts/              # Local TTS output
│   │               ├── raw/                 # Unprocessed WAV
│   │               ├── chunk_001.mp3        # Processed
│   │               └── playlist.m3u
│   └── book_english_20260105.md             # Single-file translation
```

---

### Processing Pipeline

```
Original Book (Markdown)
    ↓
[Split into Chunks] (10k words each)
    ↓
[Translate] (Local AI or Cloud)
    ↓
[Context Awareness] (Layer 1: LLM)
    ↓
[Deduplication] (Layer 2: Exact match)
    ↓
[Clean Translation Files]
    ↓
[Generate Audio] (Local TTS or Cloud)
    ↓
[Post-Process] (Speed, normalize, MP3)
    ↓
[Combine Parts] (Single file)
    ↓
[Compress] (Optional, 40% smaller)
    ↓
Final Audiobook
```

---

### Extract Books from Sources

**Project Gutenberg:**
```bash
python gutenberg_extractor.py
```

**EPUB to Markdown:**
```bash
python epub_to_md.py input.epub
```

---

### Tips & Best Practices

1. **Always use deduplicated files** for audio generation
2. **Test with first chunk** before processing entire book
3. **Compress audio** to save storage (no quality loss for speech)
4. **Let translation finish** - can take hours but resumes if interrupted
5. **Start with smaller chunks** (5k words) for easier debugging
6. **Use local TTS** for cost savings (after 2-3 books, saves money)
7. **Use cloud TTS** when speed is critical
8. **Keep original files** in case you need to re-process

---

## Next Steps

### Immediate Actions
1. Choose your translation method (cloud vs local)
2. Test with a single chapter first
3. Validate audio quality before full book
4. Experiment with different voices (local or cloud)

### Short-term Goals
1. Translate your first complete book
2. Create combined audiobook file
3. Transfer to mobile device
4. Set up automated batch processing

### Long-term Plans
1. Build personal audiobook library
2. Explore voice cloning for consistency
3. Contribute to project development
4. Try experimental features (summarization, etc.)

---

## Getting Help

- **Technical Reference**: See [CLAUDE.md](CLAUDE.md)
- **Test Results**: See [CHANGELOG.md](CHANGELOG.md)
- **Project Overview**: See [README.md](README.md)

---

**Last Updated**: January 5, 2026
