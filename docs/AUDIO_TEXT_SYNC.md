# Audio-Text Synchronization

Technical guide for the audio-text sync and karaoke features. These enable real-time paragraph highlighting in the e-reader and word-level highlighting in karaoke mode as audio plays.

## How It Works

```
Source Markdown
  |
  v
BookProcessor.process()          -- assigns stable paragraph IDs (ch01_p001, ch01_p002, ...)
  |
  v
book_manifest.json (v3.0)       -- chapters with paragraph registry
  |
  v
Kokoro TTS                      -- generates audio chunks, records text boundaries
  |
  v
chunk_manifest.json             -- maps each audio chunk to text range + paragraph IDs
  |
  v
Word Timing Generator           -- distributes words across chunk durations
  |
  v
word_timings.json               -- per-word timestamps with paragraph assignments
  |
  v
Frontend (player.js / reader.js / karaoke.js)
  |-- Reader:  paragraph highlighting + click-to-seek
  |-- Karaoke: word-level highlighting + click-to-seek
```

## Key Files

| File | Role |
|------|------|
| `lib/book/processor.py` | Assigns paragraph IDs during book processing |
| `lib/audio/kokoro.py` | Generates chunk manifest during TTS |
| `lib/audio/word_timings.py` | Generates word-level timestamps |
| `server/audiobook_server.py` | Serves timing data via API |
| `server/text_extractor.py` | Provides chapter text with paragraph markup |
| `server/static/player.js` | Coordinates audio position with text highlighting |
| `server/static/reader.js` | Renders chapter text with paragraph elements |
| `server/static/karaoke.js` | Word-level sync and highlighting |

## Paragraph IDs

Deterministic IDs that flow through the entire pipeline:

- Format: `ch{chapter:02d}_p{index:03d}` (e.g., `ch01_p001`, `ch03_p042`)
- Created by `BookProcessor._extract_paragraphs()` during validation
- Stored in `book_manifest.json` per chapter
- Embedded in chunk manifest paragraph annotations
- Referenced in word timings
- Rendered as `data-para-id` attributes in the reader

## Data Formats

### Chunk Manifest

Generated during Kokoro TTS. Maps each audio chunk to its text range.

File: `audio_kokoro/{book}_chunk_manifest.json`

```json
{
  "version": "3.0",
  "total_chunks": 127,
  "total_duration": 3642.5,
  "chunks": [
    {
      "number": 1,
      "file": "chunk_001_raw.wav",
      "duration": 28.7,
      "text_start": 0,
      "text_end": 523,
      "chapter": 1,
      "cumulative_duration": 0.0,
      "paragraphs": [
        { "para_id": "ch01_p001", "char_start_in_chunk": 0, "char_end_in_chunk": 112 },
        { "para_id": "ch01_p002", "char_start_in_chunk": 114, "char_end_in_chunk": 523 }
      ]
    }
  ]
}
```

### Word Timings

Generated after audio. Per-word timestamps with paragraph assignments.

File: `{book}_word_timings.json`

```json
{
  "chapter_1": {
    "file_index": 0,
    "audio_file": "chapter_01.mp3",
    "word_count": 2543,
    "duration": 612.5,
    "words": [
      { "word": "Alice", "start": 0.0, "end": 0.4, "text_pos": 0, "para_id": "ch01_p001" }
    ],
    "paragraphs": [
      { "para_id": "ch01_p001", "audio_start": 0.0, "audio_end": 15.2, "word_start_idx": 0, "word_end_idx": 42 }
    ]
  }
}
```

## Sync Algorithm

The frontend uses a three-tier fallback to map audio time to the current paragraph:

### Tier 1: Paragraph Timings (best accuracy)

Uses pre-computed `audio_start`/`audio_end` from word timings:

```javascript
const match = timings.find(p => time >= p.audio_start && time <= p.audio_end);
```

### Tier 2: Chunk Manifest (good accuracy)

Interpolates within chunks using character distribution:

1. Find the chunk where `cumulative_duration <= time < cumulative_duration + duration`
2. Compute position within chunk as proportion of duration
3. Map to character offset, find overlapping paragraph

### Tier 3: Linear Progress (acceptable)

Maps audio progress (0-1) to paragraph index by cumulative character count. Used when no timing data is available.

## Reader Sync

The e-reader (`reader.js`) renders each paragraph as:

```html
<p class="reader-paragraph" data-chapter="0" data-para-id="ch01_p001">...</p>
```

**Audio to text:** On `timeupdate`, `player.js` determines the current `para_id` and calls `highlightCurrentParagraph()`, which adds the `reader-active` CSS class and auto-scrolls.

**Text to audio (click-to-seek):** Clicking a paragraph dispatches a `reader-seek` event. `player.js` looks up the paragraph's `audio_start` from timing data and sets `audio.currentTime`.

## Karaoke Mode

`karaoke.js` provides word-level sync:

1. Loads word timings from `/api/books/{id}/word-timings`
2. Renders each word as `<span class="karaoke-word" data-start="0.0" data-end="0.4">`
3. On `timeupdate`, binary-searches for the current word: O(log N)
4. Highlights via `karaoke-current` / `karaoke-past` CSS classes
5. Clicking a word seeks audio to `word.start`

Word spans are cached as direct references (`this.wordSpans[]`) for O(1) DOM updates.

## API Endpoints

| Endpoint | Returns |
|----------|---------|
| `GET /api/books/{id}/word-timings` | All chapters with word-level timestamps |
| `GET /api/books/{id}/word-timings/{chapter}` | Single chapter word timings |
| `GET /api/books/{id}/paragraph-timings` | Paragraph-level start/end per chapter |
| `GET /api/books/{id}/chunk-manifest` | Full chunk-to-text mapping |
| `GET /api/books/{id}/text/{chapter}` | Chapter text with paragraph structure |

## Timing Generation Methods

Word timings can be generated via multiple backends (in priority order):

1. **Chunk Manifest** (default, no extra deps) — distributes words uniformly within each chunk's time window
2. **WhisperX** (`pip install whisperx`) — forced-alignment for precise timestamps
3. **Whisper.cpp** (binary) — lightweight alternative
4. **Uniform fallback** — distributes words evenly across total duration

## Troubleshooting

**No paragraph highlighting in reader:**
- Check that `book_manifest.json` has version `3.0` with paragraph registry
- Regenerate: `python3 validate.py books/{book}/ --migrate-paragraphs`
- Re-run audiobook generation to update chunk manifest

**Karaoke not available:**
- Word timings file must exist: `{book}_word_timings.json`
- Regenerate audio with `--no-word-timings` flag removed (timings are on by default)

**Sync drifts over time:**
- Likely using Tier 3 (linear) fallback — regenerate audio to get chunk manifest
- Or install WhisperX for forced-alignment: `pip install whisperx`

**Click-to-seek jumps to wrong position:**
- Usually means paragraph timings are missing — falls back to character-proportion estimation
- Fix: regenerate word timings after updating the book manifest

**Old audiobooks (pre-Feb 2026):**
- Need regeneration to create chunk manifests:
  ```bash
  python3 make_audiobook.py books/{book_name}/book.md
  ```
