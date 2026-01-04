# Translation to Audiobook Workflow

Complete guide for translating books and generating audiobooks with the Local Reader system.

## Quick Start

```bash
# 1. Split book into chunks
python3 local_reader_smart_splitter.py books/crime_punishment/book.md

# 2. Translate chunks (with automatic deduplication)
python3 local_reader_batch_translator.py books/crime_punishment/chunks/ Russian Spanish

# 3. Generate audio from deduplicated files
python3 local_reader_audio.py books/crime_punishment/chunks/translated/deduplicated/

# 4. Combine audio parts
python3 local_reader_audio_combiner.py audiobook_playlist.m3u

# 5. Compress for smaller file size
python3 local_reader_audio_compress.py combined_audiobook.mp3 96k
```

---

## Detailed Workflow

### Step 1: Split Book into Chunks

**Why:** Large books need to be split for manageable translation.

```bash
python3 local_reader_smart_splitter.py books/crime_punishment/crime_punishment.md
```

**Output:**
- `books/crime_punishment/chunks/chunk_001.md`
- `books/crime_punishment/chunks/chunk_002.md`
- `books/crime_punishment/chunks/chunks_manifest.txt` (summary)

**Options:**
```bash
# Custom chunk size (default: 10,000 words)
python3 local_reader_smart_splitter.py book.md 5000
```

---

### Step 2: Translate Chunks

**Why:** Translate from source language to target language using local AI.

```bash
python3 local_reader_batch_translator.py books/crime_punishment/chunks/ Russian Spanish
```

**What happens:**
1. Translates each chunk sequentially
2. Passes context from previous chunk to prevent duplicates
3. Automatically runs deduplication as failsafe
4. Saves to `translated/` and `translated/deduplicated/`

**Features:**
- **Resume support:** Interrupted? Just re-run - it picks up where it left off
- **Progress tracking:** Shows ETA and completion percentage
- **Error recovery:** Continues even if one chunk fails
- **Automatic deduplication:** No overlapping text in audio

**Output:**
- `chunks/translated/chunk_001_spanish_4b.md`
- `chunks/translated/deduplicated/chunk_001_DEDUPED.md` ← **Use these!**

---

### Step 3: Generate Audio

**From deduplicated files (recommended):**

```bash
python3 local_reader_audio.py books/crime_punishment/chunks/translated/deduplicated/
```

**What happens:**
1. Finds all `.md` files in directory
2. Generates audio using OpenAI TTS (or local TTS in future)
3. Creates playlist file (`.m3u`) for sequential playback
4. Saves audio parts in `audio/` subdirectory

**Output:**
- `deduplicated/audio/chunk_001_DEDUPED_part001_fable_20260103.mp3`
- `deduplicated/audio/chunk_001_DEDUPED_audiobook_playlist_20260103.m3u`

**Options:**
```bash
# Different voice
python3 local_reader_audio.py translated/ --voice alloy

# Available voices: alloy, echo, fable, onyx, nova, shimmer
```

---

### Step 4: Combine Audio Parts

**Why:** Create a single audiobook file instead of multiple parts.

```bash
python3 local_reader_audio_combiner.py deduplicated/audio/audiobook_playlist_20260103.m3u
```

**What happens:**
1. Reads playlist file
2. Combines all parts using ffmpeg (fast, no re-encoding)
3. Creates single MP3 file

**Output:**
- `deduplicated/audio/audiobook_COMBINED.mp3`

---

### Step 5: Compress Audio (Optional)

**Why:** Reduce file size by ~40% without noticeable quality loss for speech.

```bash
python3 local_reader_audio_compress.py audiobook_COMBINED.mp3 96k
```

**What happens:**
1. Re-encodes to 96kbps mono
2. Optimized for speech (not music)
3. Saves as `*_compressed.mp3`

**Bitrate options:**
- `64k` - Very compressed (smallest, still good for speech)
- `96k` - **Recommended** - Best balance
- `128k` - Higher quality (larger file)

**Example results:**
- Original: 72.8 MB
- Compressed (96k): 43.7 MB (40% reduction)

---

## Anti-Duplication System

The system uses **two layers** to prevent duplicate audio at chunk boundaries:

### Layer 1: LLM Context Awareness (Primary Prevention)

When translating chunk N+1, the translator:
1. Takes the last 2 sentences from chunk N (translated)
2. Includes them in the prompt as "context for reference only"
3. Instructs LLM: "Do NOT translate this context, only the new text"

**Result:** LLM naturally avoids repeating the context.

### Layer 2: Exact-Match Deduplication (Failsafe)

After translation completes:
1. Compares end of chunk N with start of chunk N+1
2. Finds exact text matches
3. Removes duplicates from chunk N+1
4. Saves to `deduplicated/` directory

**Result:** Any duplicate that slipped through Layer 1 is caught and removed.

---

## File Organization

```
books/crime_punishment/
├── crime_punishment.md                    # Original book
└── chunks/
    ├── chunk_001.md                       # Split chunks
    ├── chunk_002.md
    ├── chunks_manifest.txt
    └── translated/
        ├── chunk_001_spanish_4b.md        # Raw translations
        ├── chunk_002_spanish_4b.md
        ├── .translation_progress.json     # Resume checkpoint
        └── deduplicated/                  # ← Use these for audio!
            ├── chunk_001_DEDUPED.md       # Clean, no duplicates
            ├── chunk_002_DEDUPED.md
            └── audio/
                ├── chunk_001_part001.mp3
                ├── chunk_002_part001.mp3
                ├── audiobook_playlist.m3u
                └── audiobook_COMBINED.mp3
```

---

## Common Issues

### Translation is slow
- **Expected:** ~10 minutes per 10k-word chunk on CPU
- **Solution:** Run overnight or upgrade to GPU

### Audio has duplicates
- **Check:** Are you using files from `deduplicated/`?
- **Fix:** Regenerate audio from `translated/deduplicated/*.md`

### Compression degrades quality
- **Try:** Higher bitrate (`128k` instead of `96k`)
- **Note:** Speech doesn't need high bitrate like music

### Translation interrupted
- **Good news:** Progress is auto-saved!
- **Fix:** Just re-run the same command - it resumes automatically

---

## Advanced Usage

### Translate single file
```bash
# Just one chunk
python3 local_reader_translation.py chunk_001.md Russian Spanish
```

### Manual deduplication
```bash
# If auto-dedup didn't run
python3 local_reader_deduplicate.py translated/ "*_spanish.md"
```

### Different models
Edit `local_reader_config.py`:
```python
default_translation_model: str = "zongwei/gemma3-translator:1b"  # Faster, lower quality
# or
default_translation_model: str = "zongwei/gemma3-translator:4b"  # Slower, better quality
```

---

## Next Steps After Audiobook

### For Listening
1. Copy `audiobook_COMBINED_compressed.mp3` to your device
2. Use any audio player (VLC, Apple Music, etc.)
3. **Future:** Mobile app with progress tracking (in development)

### For Summarization
Once you have clean translated text:
```bash
# Future feature (not yet implemented)
python3 local_reader_compressor.py translated_book.md 50%
```

This will create a 50% length summary while preserving key plot points.

---

## Tips & Best Practices

1. **Always use deduplicated files for audio** - prevents repetition
2. **Compress audio** - saves storage, no quality loss for speech
3. **Let translation finish** - can take hours, but resumes if interrupted
4. **Check first chunk audio** - test quality before processing entire book
5. **Start with smaller chunks** - easier to debug issues

---

## Troubleshooting

### "Model not found"
```bash
ollama pull zongwei/gemma3-translator:4b
```

### "ffmpeg not found"
```bash
brew install ffmpeg  # macOS
```

### "No files found"
- Check file pattern matches (default: `*.md`)
- Verify you're in the correct directory

### "Permission denied"
```bash
chmod +x local_reader_*.py
```

---

## Performance Benchmarks

| Book Size | Chunks | Translation Time | Audio Generation | Total |
|-----------|--------|------------------|------------------|-------|
| 50k words | 5      | ~50 min         | ~15 min          | ~65 min |
| 100k words| 10     | ~100 min        | ~30 min          | ~130 min |
| 200k words| 20     | ~200 min        | ~60 min          | ~260 min |

*Benchmarks on M1 MacBook Pro using 4b model*

---

## Support

- **Documentation:** See `LOCAL_READER_README.md`
- **Known Issues:** See `KNOWN_ISSUES.md`
- **Config:** Edit `local_reader_config.py`
