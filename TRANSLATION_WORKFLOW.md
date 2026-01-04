# Local Reader Translation Workflow

Complete guide for translating large books using local AI models.

> **Note**: For a more comprehensive guide including audio generation, see [WORKFLOW_GUIDE.md](WORKFLOW_GUIDE.md)

## Overview

This workflow enables translation of large books (100k+ words) by:
1. **Splitting** books into manageable chunks
2. **Translating** each chunk with context awareness (prevents duplicates)
3. **Auto-deduplication** as failsafe (catches any remaining duplicates)
4. **Resuming** from interruptions automatically
5. **Monitoring** progress with real-time feedback

**NEW (Jan 2026)**: Two-layer anti-duplication system ensures clean audio with zero repetition!

## Quick Start

### Prerequisites

```bash
# 1. Ensure Ollama is installed and running
ollama list

# 2. Verify translation model is available
ollama pull zongwei/gemma3-translator:4b

# 3. Activate virtual environment
source venv/bin/activate
```

### Complete Translation Process

```bash
# Step 1: Split large book into chunks (~10,000 words each)
python3 local_reader_smart_splitter.py "books/YOUR_BOOK/book.md" 10000

# Step 2: Translate all chunks with automatic deduplication
python3 local_reader_batch_translator.py books/YOUR_BOOK/chunks/ "Source Language" "Target Language"

# This will:
# - Translate with context awareness (Layer 1: prevents duplicates)
# - Auto-run deduplication as failsafe (Layer 2: catches remaining duplicates)
# - Create clean files in translated/deduplicated/ directory
# - Save progress after each chunk

# Step 3: If interrupted, simply run the same command again to resume
# Progress is automatically saved after each completed chunk

# Step 4: Use deduplicated files for audio generation
python3 local_reader_audio.py books/YOUR_BOOK/chunks/translated/deduplicated/
```

## Detailed Workflow

### 1. Book Preparation

**Split a large book into chunks:**

```bash
python local_reader_smart_splitter.py "books/crime_punishment/Преступление_и_наказание.md" 10000
```

**Output:**
- Creates `books/crime_punishment/chunks/` directory
- Generates `chunk_001.md`, `chunk_002.md`, etc. (~10,000 words each)
- Creates `chunks_manifest.txt` with metadata

**Example output:**
```
Book: Преступление_и_наказание
Size: 1,087,265 characters, 176,782 words
Splitting by word count (10000 words/chunk)

Chunks created: 18
Average words/chunk: 9,821
```

### 2. Translation Execution

**Translate all chunks:**

```bash
python local_reader_batch_translator.py \
  books/crime_punishment/chunks/ \
  "Russian" \
  "Modern Spanish"
```

**What happens:**
1. Finds all `.md` files in the chunks directory
2. Checks for previous progress (resume capability)
3. Translates each chunk sequentially
4. Saves progress after each successful translation
5. Shows real-time progress bar with ETA

**Example output:**
```
======================================================================
BATCH TRANSLATION
======================================================================
Input directory:  books/crime_punishment/chunks
Output directory: books/crime_punishment/chunks/translated
Files to translate: 18
Source language: Russian
Target language: Modern Spanish
Model: zongwei/gemma3-translator:4b
======================================================================

[1/18] Processing: chunk_001.md
----------------------------------------------------------------------
File size: 67,039 characters, 9,741 words
Translating 42 chunks from Russian to Modern Spanish...
  Chunk 1/42 completed
  Chunk 2/42 completed
  ...
  Chunk 42/42 completed
✓ Saved: chunk_001_modern_spanish_4b.md
  Chunks: 42, Time: 638.4s (10.6min)

✓ Progress: [████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 1/18 (5.6%)
  Elapsed: 10m 38s | ETA: 3h 10m
```

### 3. Resume Capability

**If translation is interrupted:**
- Press `Ctrl+C` to stop gracefully
- Progress is automatically saved
- Run the same command again to resume

**Example resume:**
```bash
# Run the same command again
python local_reader_batch_translator.py books/crime_punishment/chunks/ "Russian" "Modern Spanish"

# Output:
📌 Resuming previous translation: 5 files already completed
Already completed: 5
Remaining to translate: 13
```

**Progress tracking:**
- Saved in `chunks/translated/.translation_progress.json`
- Updated after each successful chunk
- Skips already-completed files on resume

### 4. Output Organization

**Translated files location:**
```
books/crime_punishment/
├── chunks/                          # Original chunks
│   ├── chunk_001.md
│   ├── chunk_002.md
│   └── ...
└── chunks/translated/               # Translated chunks
    ├── chunk_001_modern_spanish_4b.md
    ├── chunk_002_modern_spanish_4b.md
    ├── ...
    └── .translation_progress.json   # Checkpoint file
```

## Performance Benchmarks

Based on actual test results:

### Single Chunk (10,000 words)
- **Translation time**: ~10-11 minutes
- **Chunks processed**: ~42 (250 words each)
- **Translation speed**: 15-16 words/second

### Full Book Estimates

| Book Size | Chunks | Estimated Time |
|-----------|--------|----------------|
| 50k words | 5 | ~50-60 minutes |
| 100k words | 10 | ~1.5-2 hours |
| 180k words | 18 | **~3-3.5 hours** |
| 250k words | 25 | ~4-5 hours |

**Crime and Punishment (176,782 words):**
- 18 chunks
- Estimated total time: **3 hours 12 minutes**
- Can be paused/resumed at any time

## Advanced Usage

### Test Single Chunk First

Before translating an entire book, test with one chunk:

```bash
# Create test directory
mkdir -p books/YOUR_BOOK/chunks/test_chunk
cp books/YOUR_BOOK/chunks/chunk_001.md books/YOUR_BOOK/chunks/test_chunk/

# Translate single chunk
python local_reader_batch_translator.py \
  books/YOUR_BOOK/chunks/test_chunk/ \
  "Source Lang" \
  "Target Lang"
```

### Custom Chunk Size

Adjust chunk size based on needs:

```bash
# Smaller chunks (5,000 words) - faster per chunk, more total chunks
python local_reader_smart_splitter.py "books/book.md" 5000

# Larger chunks (20,000 words) - slower per chunk, fewer total chunks
python local_reader_smart_splitter.py "books/book.md" 20000
```

**Trade-offs:**
- **Smaller chunks**: More granular progress, easier to resume, more API calls
- **Larger chunks**: Fewer files, potentially better context, longer per-chunk time

### Monitor Progress While Running

In a separate terminal:

```bash
# Check how many chunks completed
ls books/YOUR_BOOK/chunks/translated/*.md | wc -l

# View checkpoint file
cat books/YOUR_BOOK/chunks/translated/.translation_progress.json

# Monitor Ollama
ollama ps
```

## Troubleshooting

### Translation Appears Incomplete

**Issue**: Some parts of the file aren't translated (still in original language)

**Cause**: This is expected - the file might contain:
- Table of contents (often kept in original)
- Headers and metadata
- Mixed content

**Verify**: Check the main body text - it should be translated. The table of contents and headers are sometimes intentionally preserved.

### Translation is Slow

**Normal behavior**:
- ~10-15 minutes per 10,000-word chunk
- ~15-16 words/second translation speed

**To speed up**:
1. Use smaller model: `zongwei/gemma3-translator:1b` (faster but lower quality)
2. Increase chunk size to reduce API overhead
3. Ensure Ollama has enough RAM/GPU resources

### Out of Memory

If Ollama runs out of memory:

```bash
# Check Ollama memory usage
ollama ps

# Restart Ollama
killall ollama
ollama serve
```

Reduce chunk size to 5,000 words.

### Resume Not Working

If resume doesn't detect completed files:

```bash
# Check progress file exists
cat books/YOUR_BOOK/chunks/translated/.translation_progress.json

# Manually check what's been translated
ls books/YOUR_BOOK/chunks/translated/
```

## File Structure

Complete directory layout after workflow:

```
books/crime_punishment/
├── Преступление_и_наказание.md       # Original book (large)
├── chunks/                           # Split into manageable pieces
│   ├── chunks_manifest.txt           # Metadata about chunks
│   ├── chunk_001.md                  # ~10k words
│   ├── chunk_002.md
│   ├── ...
│   ├── chunk_018.md
│   └── translated/                   # Translation output
│       ├── .translation_progress.json  # Resume checkpoint
│       ├── chunk_001_modern_spanish_4b.md   # Raw translations
│       ├── chunk_002_modern_spanish_4b.md
│       ├── ...
│       └── deduplicated/             # ← Clean files (use for audio!)
│           ├── chunk_001_DEDUPED.md  # No overlaps
│           ├── chunk_002_DEDUPED.md
│           └── ...
```

## Next Steps

After translation completes:

1. **Combine chunks** (if desired) into single file
2. **Review quality** - spot-check translations
3. **Generate audio** using TTS (future step)
4. **Compress/summarize** for time-constrained listening

## Anti-Duplication System (NEW)

### The Problem
Translation chunks use 20-word overlap for context continuity. This creates duplicate audio at boundaries:
```
Chunk 1 ends: "...and he walked away without looking back."
Chunk 2 starts: "without looking back. While he was walking..."
                ^^^^^^^^^^^^^^^^^^ DUPLICATE AUDIO
```

### The Solution: Two-Layer Approach

**Layer 1: LLM Context (Primary Prevention)**
- Each chunk (except first) receives context from previous chunk's translation
- Translator is instructed: "Here's the previous ending for reference - DON'T translate it again"
- Prevents ~70% of duplicates during translation

**Layer 2: Exact-Match Deduplication (Failsafe)**
- After all translations complete, automatically detects exact text matches at boundaries
- Removes duplicates from start of each chunk
- Catches 100% of remaining duplicates
- Creates clean files in `deduplicated/` directory

### Result
✅ Clean, seamless audio with **zero repetition** at chunk boundaries

**Validation**: See [TEST_RESULTS_DEDUPLICATION.md](TEST_RESULTS_DEDUPLICATION.md) for test results with 5-chunk suite.

## Summary

This workflow successfully handles:
- ✅ **Large books** (100k+ words) by chunking
- ✅ **Progress tracking** with real-time updates
- ✅ **Resume capability** after interruptions
- ✅ **Quality translation** using local Ollama models
- ✅ **Anti-duplication** with two-layer system (NEW)
- ✅ **No external API costs** - fully local

**Tested successfully on:**
- Crime and Punishment (Russian → Modern Spanish)
- Crime and Punishment (Russian → Modern English) - mini test with deduplication
- 9,741 words translated in 10.6 minutes
- Resume functionality verified
- Two-layer deduplication validated
