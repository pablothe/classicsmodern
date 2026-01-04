# Local Book Pipeline Guide

Complete end-to-end pipeline for translating classic books and generating audiobooks **100% locally** with full resume capability.

## Overview

The `local_book_pipeline.py` script handles the entire process:

1. **Auto-Chunking**: Intelligently splits book by chapters or size
2. **Translation**: Translates using local Ollama (gemma3-translator:4b)
3. **Deduplication**: Removes duplicate text at chunk boundaries
4. **Audio Generation**: Creates audiobook using XTTS-v2 voice cloning

**Key Features:**
- ✅ **Fully Resumable**: Interrupt and resume at any point
- ✅ **Detailed Progress Bars**: Track progress at every stage
- ✅ **100% Local**: No API costs, complete privacy
- ✅ **State Persistence**: Automatic checkpoint saving
- ✅ **Multi-Language**: Supports 16 languages for audio

## Prerequisites

### 1. Ollama (Translation)
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull translation model
ollama pull zongwei/gemma3-translator:4b
```

### 2. XTTS-v2 (Audio Generation)
```bash
# Activate your virtual environment
source venv/bin/activate

# Install TTS library
pip install TTS==0.27.3

# Install FFmpeg (for post-processing)
brew install ffmpeg  # macOS
# or
sudo apt install ffmpeg  # Linux
```

### 3. Voice Reference
You need a clean voice sample (10-30 seconds) for voice cloning:

```bash
# Prepare a voice reference from any audio file
python local_tts_xtts.py --prepare-voice sample_audio.m4a voice_ref_clean.wav
```

**Tips for best voice quality:**
- 10-30 seconds of clear speech
- No background music or reverb
- Consistent microphone distance
- Single speaker, no interruptions

## Quick Start

### Basic Usage

```bash
# Process a book (assumes voice_ref_clean.wav exists)
source venv/bin/activate

python local_book_pipeline.py books/crime_punishment/book.md \
    --source Russian \
    --target "Modern English"
```

### With Custom Options

```bash
python local_book_pipeline.py books/alice/alice.md \
    --source English \
    --target Spanish \
    --voice my_voice.wav \
    --words-per-chunk 5000
```

### All Options

```bash
python local_book_pipeline.py <book.md> \
    --source <SOURCE_LANG> \           # Required: Russian, Chinese, German, etc.
    --target <TARGET_LANG> \           # Required: "Modern English", Spanish, etc.
    --voice <voice.wav> \              # Optional: default is voice_ref_clean.wav
    --words-per-chunk <NUM> \          # Optional: default 10000
    --no-auto-chunk                    # Optional: always chunk regardless of size
```

## How It Works

### Stage 1: Chunking (1-5 minutes)

The script analyzes your book:

- **Small books** (<50KB): Processed as single file
- **Large books** (>50KB): Split by chapters or word count

```
STAGE 1: CHUNKING
====================================================================
Book size: 524,288 chars (over 50,000 threshold)
Splitting into chunks (~10000 words each)...

Analyzing structure...
Found 15 chapters at H2 level

Saving 15 chunks to: books/crime_punishment/chunks/

✅ Chunking complete: 15 chunks
```

### Stage 2: Translation (4-8 hours)

Each chunk is translated with context awareness:

```
STAGE 2: TRANSLATION
====================================================================
Translating 15 chunks...
This may take 4-8 hours depending on book size.
====================================================================

[1/15] Processing: chunk_001.md
File size: 12,453 characters, 2,847 words
✓ Saved: chunk_001_Modern English_4b.md
  Chunks: 8, Time: 324.2s (5.4min)

✓ Progress: [███████░░░░░░░] 1/15 (6.7%)
  Elapsed: 5m 24s | ETA: 1h 15m

[2/15] Processing: chunk_002.md
...
```

**Resume Capability:**
- Press Ctrl+C to interrupt
- Progress automatically saved
- Run same command to resume

### Stage 3: Deduplication (1-5 minutes)

Removes duplicate text at chunk boundaries:

```
STAGE 3: DEDUPLICATION
====================================================================
Removing duplicate text at chunk boundaries...
====================================================================

Deduplicating 15 chunks...
Maximum overlap to check: 30 words

Processing chunk 1/15: chunk_001_Modern English_4b.md
  ○ First chunk - no deduplication needed

Processing chunk 2/15: chunk_002_Modern English_4b.md
  ✓ Removed 23 words (147 chars)
    Preview: 'looked at him with a strange expression, as if recogniz...'

...

====================================================================
DEDUPLICATION COMPLETE
====================================================================
Total characters removed: 2,145
Output directory: books/crime_punishment/chunks/translated/deduplicated
Files created: 15

✅ Deduplication complete
```

### Stage 4: Audio Generation (6-12 hours)

Generates high-quality audiobook with voice cloning:

```
STAGE 4: AUDIO GENERATION
====================================================================
Generating audiobook with XTTS-v2...
This may take several hours for long books.
====================================================================

Language code: en
Processing 15 chunks...

====================================================================
CHUNK 1/15: chunk_001_DEDUPED.md
====================================================================
Loading XTTS-v2 model (this may take a moment)...
✓ Model loaded successfully
✓ Using reference voice: voice_ref_clean.wav

Reading: books/crime_punishment/chunks/translated/deduplicated/chunk_001_DEDUPED.md
Cleaning text for speech...
Text ready: 11,234 characters, 2,847 words
Chunking text (max 1500 chars per chunk)...
Created 8 audio chunks

[1/8] Generating audio (1,234 chars)... ✓ Saved: chunk_001_chunk001_raw.wav
  Post-processing (speed=1.15x, normalize=True)... ✓ Processed: chunk_001_chunk001.mp3
[2/8] Generating audio (1,456 chars)... ✓ Saved: chunk_001_chunk002_raw.wav
  Post-processing (speed=1.15x, normalize=True)... ✓ Processed: chunk_001_chunk002.mp3
...

✓ Playlist created: chunk_001_audiobook_20260104_153045.m3u

✓ Chunk 1 complete in 45m 23s

Audio Progress: [███░░░░░░░░░░░░] 1/15 (6.7%)
Elapsed: 45m 23s | ETA: 10h 15m

====================================================================
CHUNK 2/15: chunk_002_DEDUPED.md
====================================================================
...
```

### Final Output

```
====================================================================
🎉 PIPELINE COMPLETE!
====================================================================
Total time: 14h 32m
Chunks: 15
Audio files: 127

Outputs:
  Translated: books/crime_punishment/chunks/translated/deduplicated
  Audio: books/crime_punishment/chunks/translated/deduplicated/audio_xtts

====================================================================

🎧 Your audiobook is ready!

To play: cd books/crime_punishment/chunks/translated/deduplicated/audio_xtts && afplay *.m3u
```

## Resume After Interruption

If the process is interrupted (Ctrl+C, crash, power loss):

```bash
# Just run the exact same command again
python local_book_pipeline.py books/crime_punishment/book.md \
    --source Russian \
    --target "Modern English"

# Output:
📌 Resuming previous pipeline run
   Started: 2026-01-04T10:30:45

====================================================================
PIPELINE STATUS
====================================================================
✓ Chunking:       DONE
✓ Translation:    DONE (15/15 chunks)
✓ Deduplication:  DONE
✓ Audio:          PENDING (8/15 files)
====================================================================

# Continues from where it left off...
```

## File Organization

After completion, your directory structure will look like:

```
books/crime_punishment/
├── book.md                                      # Original book
├── chunks/                                      # Chunked files
│   ├── chunk_001.md
│   ├── chunk_002.md
│   ├── ...
│   ├── chunks_manifest.txt                      # Chunk metadata
│   └── translated/                              # Translation stage
│       ├── chunk_001_Modern English_4b.md       # Raw translations
│       ├── chunk_002_Modern English_4b.md
│       ├── ...
│       ├── .translation_progress.json           # Translation checkpoint
│       └── deduplicated/                        # Clean translations
│           ├── chunk_001_DEDUPED.md
│           ├── chunk_002_DEDUPED.md
│           ├── ...
│           └── audio_xtts/                      # Audio files
│               ├── raw/                         # Unprocessed WAV files
│               │   ├── chunk_001_chunk001_raw.wav
│               │   └── ...
│               ├── chunk_001_chunk001.mp3       # Processed audio
│               ├── chunk_001_chunk002.mp3
│               ├── ...
│               ├── chunk_001_audiobook_[timestamp].m3u  # Chapter playlists
│               ├── chunk_002_audiobook_[timestamp].m3u
│               └── book_complete_audiobook.m3u  # Master playlist
└── .pipeline_state_book.json                    # Pipeline checkpoint
```

## Time Estimates

| Book Size | Chunks | Translation | Audio | Total |
|-----------|--------|-------------|-------|-------|
| Small (100 pages) | 3-5 | 1-2 hours | 2-3 hours | 3-5 hours |
| Medium (300 pages) | 10-15 | 4-6 hours | 6-9 hours | 10-15 hours |
| Large (600 pages) | 20-30 | 8-12 hours | 12-18 hours | 20-30 hours |

**Factors affecting speed:**
- **Translation**: CPU speed, chunk size, Ollama model
- **Audio**: CPU/GPU speed, text length, voice complexity

## Tips & Best Practices

### For Best Audio Quality

1. **Prepare clean voice reference:**
   ```bash
   python local_tts_xtts.py --prepare-voice sample.m4a voice_ref_clean.wav
   ```

2. **Use consistent voice samples:**
   - Same speaker throughout
   - Clear articulation
   - No background noise

3. **Monitor first chunk:**
   - Listen to first audio chunk
   - If quality is poor, stop and try different voice reference

### For Faster Processing

1. **Reduce chunk size** (faster individual chunks, but more chunks):
   ```bash
   --words-per-chunk 5000
   ```

2. **Use GPU if available** (for audio generation):
   - XTTS auto-detects GPU
   - 3-5x faster than CPU

3. **Run overnight** for large books

### For Better Translations

1. **Check first chunk** before committing to full book:
   ```bash
   # Process just the first chunk manually
   python local_reader_smart_splitter.py book.md
   python local_reader_batch_translator.py books/book/chunks/ Russian "Modern English"

   # Review: books/book/chunks/translated/chunk_001_Modern English_4b.md
   # If good, run full pipeline
   ```

2. **Adjust chunk size** for narrative structure:
   - Smaller chunks (5000 words): More granular context
   - Larger chunks (15000 words): Better narrative flow

## Troubleshooting

### Translation Stage Fails

```bash
# Check Ollama is running
ollama list

# Check model is pulled
ollama pull zongwei/gemma3-translator:4b

# Test translation manually
python local_reader_batch_translator.py books/test/chunks/ Russian English
```

### Audio Stage Fails

```bash
# Check TTS is installed
python -c "from TTS.api import TTS; print('TTS OK')"

# Check FFmpeg is available
ffmpeg -version

# Check voice reference exists
ls -lh voice_ref_clean.wav

# Test audio generation manually
python local_tts_xtts.py translated.md voice_ref_clean.wav en
```

### Out of Memory

```bash
# Reduce chunk size
--words-per-chunk 3000

# Or process chunks individually:
for chunk in books/book/chunks/*.md; do
    python local_reader_batch_translator.py "$chunk" Russian English
done
```

### Pipeline State Corrupted

```bash
# Remove state file and restart
rm books/book/.pipeline_state_book.json

# Re-run pipeline (will start from beginning but skip completed stages)
python local_book_pipeline.py books/book/book.md --source Russian --target English
```

## Advanced Usage

### Custom Audio Settings

Edit `local_book_pipeline.py` around line 460:

```python
# Current defaults:
result = generator.generate_audiobook(
    str(chunk_file),
    chunk_size=1500,       # Change: 500-2000 (smaller = more natural pauses)
    speed=1.15,            # Change: 1.0-1.5 (1.0 = normal speed)
    normalize=True,        # Keep: True (audiobook standard)
    to_mp3=True           # Change: False for WAV (larger files)
)
```

### Process Multiple Books

```bash
#!/bin/bash
# process_all_books.sh

for book in books/*/book.md; do
    echo "Processing: $book"
    python local_book_pipeline.py "$book" \
        --source Russian \
        --target "Modern English"
done
```

### Different Voices Per Book

```bash
# Romance novel with female voice
python local_book_pipeline.py books/anna_karenina/book.md \
    --source Russian --target English \
    --voice voice_female.wav

# Action novel with male voice
python local_book_pipeline.py books/crime_punishment/book.md \
    --source Russian --target English \
    --voice voice_male.wav
```

## FAQ

**Q: Can I pause translation and resume later?**
A: Yes! Press Ctrl+C anytime. Run the same command to resume from the exact chunk you left off.

**Q: What if my computer crashes during audio generation?**
A: The pipeline saves state after each chunk. Re-run the command and it will continue from the last completed chunk.

**Q: Can I use different languages for audio?**
A: Yes! XTTS-v2 supports 16 languages: en, es, fr, de, it, pt, pl, tr, ru, nl, cs, ar, zh-cn, ja, ko, hu

**Q: How much disk space do I need?**
A: Roughly:
- Translation: ~2x original book size
- Audio (MP3): ~1MB per minute (~50MB per hour)
- Audio (WAV): ~10MB per minute (~600MB per hour)

**Q: Can I translate but skip audio?**
A: Not yet with the pipeline. For translation-only, use:
```bash
python local_reader_smart_splitter.py book.md
python local_reader_batch_translator.py books/book/chunks/ Russian English
```

**Q: How do I monitor progress remotely?**
A: Use `screen` or `tmux`:
```bash
screen -S audiobook
python local_book_pipeline.py books/book.md --source Russian --target English
# Press Ctrl+A then D to detach
# Reconnect later: screen -r audiobook
```

## Next Steps

After your audiobook is complete:

1. **Listen and verify quality:**
   ```bash
   cd books/book/chunks/translated/deduplicated/audio_xtts
   afplay *.m3u
   ```

2. **Transfer to phone/tablet:**
   ```bash
   # The .m3u playlists work with most audio players
   # Copy the audio_xtts directory to your device
   ```

3. **Adjust if needed:**
   - Different voice reference
   - Different speed setting
   - Different chunk size

## See Also

- [LOCAL_TTS_GUIDE.md](LOCAL_TTS_GUIDE.md) - Detailed XTTS audio generation guide
- [CLAUDE.md](CLAUDE.md) - Full project documentation
- [TEST_RESULTS_DEDUPLICATION.md](TEST_RESULTS_DEDUPLICATION.md) - Deduplication testing

## Support

If you encounter issues:

1. Check this guide's Troubleshooting section
2. Verify all prerequisites are installed
3. Test each component individually
4. Check the pipeline state file for clues

Enjoy your audiobooks! 🎧
