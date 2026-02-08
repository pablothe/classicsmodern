# Karaoke Sync - Word-Level Audio-Text Synchronization

Real-time word highlighting synchronized with audiobook playback. This feature transforms the reading experience with:

- **Word-by-word highlighting** during audio playback
- **Click-to-seek** from text to audio position
- **Auto-scroll** to keep current word centered
- **Precise position tracking** - resume mid-sentence, not just mid-chapter
- **Natural speech** - audio says "Chapter 1" not "hashtag hashtag 1"

## Overview

The karaoke sync system consists of three components:

### 1. Text Preprocessing Middleware
**File:** [audio_text_preprocessor.py](audio_text_preprocessor.py)

Transforms written text into natural spoken form before TTS generation:

```python
from audio_text_preprocessor import AudioTextPreprocessor

preprocessor = AudioTextPreprocessor()
result = preprocessor.preprocess_for_speech("## 1: The Horror in Clay")

print(result.spoken_text)  # "Chapter 1: The Horror in Clay"
```

**Transformations:**
- `## 1: Title` → `"Chapter 1: Title"`
- `## I.` → `"Chapter 1"`
- `## I. Title` → `"Chapter 1. Title"`
- Removes markdown formatting while preserving structure

**Bidirectional Mapping:**
```python
# Original character position → Spoken position
spoken_pos = result.get_spoken_pos(original_pos)

# Spoken character position → Original position
original_pos = result.get_original_pos(spoken_pos)
```

### 2. Word Timing Generator
**File:** [generate_word_timings.py](generate_word_timings.py)

Creates word-level timestamps mapping audio positions to text positions:

```bash
# Generate word timings for an audiobook
python generate_word_timings.py books/call_cthulhu/audio_kokoro/audiobook.m3u

# Output: books/call_cthulhu/call_cthulhu_word_timings.json
```

**Methods:**
1. **WhisperX** (recommended) - Most accurate, requires: `pip install whisperx`
2. **whisper.cpp** - Lightweight alternative
3. **Fallback** - Uniform distribution (always works, less accurate)

**Output Format:**
```json
{
  "chapter_1": {
    "file_index": 0,
    "word_count": 2543,
    "duration": 612.5,
    "words": [
      {"word": "Chapter", "start": 0.0, "end": 0.4, "text_pos": 0},
      {"word": "1", "start": 0.5, "end": 0.7, "text_pos": 8},
      {"word": "The", "start": 0.8, "end": 0.95, "text_pos": 11}
    ]
  }
}
```

### 3. Web Player Integration
**Files:**
- [server/static/karaoke.js](server/static/karaoke.js) - Karaoke sync engine
- [server/static/player.css](server/static/player.css) - Word highlighting styles
- [server/audiobook_server.py](server/audiobook_server.py) - Word timing API

**API Endpoints:**
```javascript
GET /api/books/{book_id}/word-timings          // All chapters
GET /api/books/{book_id}/word-timings/{chapter} // Specific chapter
POST /api/playback/{book_id}/{variant_id}       // Save position + word_index
```

## Usage

### One-Command Workflow

Generate audiobook with karaoke sync enabled:

```bash
python make_audiobook.py books/call_cthulhu/call_cthulhu.md \
  --voice bf_emma \
  --generate-cover \
  --generate-word-timings
```

This will:
1. ✓ Preprocess text (markdown → spoken form)
2. ✓ Generate audio with Kokoro TTS
3. ✓ Generate chapter metadata
4. ✓ Generate cover art
5. ✓ Generate word-level timing data
6. ✓ Register with web server

### Manual Workflow

If you already have audio files:

```bash
# Step 1: Generate word timings from existing audiobook
python generate_word_timings.py books/call_cthulhu/audio_kokoro/audiobook.m3u

# Step 2: Start web server
cd server && python audiobook_server.py

# Step 3: Open web player
open http://localhost:8000
```

### Using in Web Player

1. **Open book** in web player
2. **Click "Text Sync"** button during playback
3. **Enable Karaoke Mode** toggle
4. **Watch** words highlight in real-time as audio plays
5. **Click any word** to seek audio to that position

## File Structure

After generation with karaoke support:

```
books/
  call_cthulhu/
    call_cthulhu.md                           # Original text
    call_cthulhu_word_timings.json            # Word timing data
    call_cthulhu_chapter_data.json            # Chapter metadata
    audio_kokoro/
      The_CALL_of_CTHULHU_audiobook.m3u       # Playlist
      The_CALL_of_CTHULHU_text_mapping.json   # Preprocessing map
      The_CALL_of_CTHULHU_chapter_01.mp3      # Audio files
      ...
```

## How It Works

### 1. Text Preprocessing
```
Original:  "## 1: The Horror in Clay\n\nIn the year 1926..."
             ↓ AudioTextPreprocessor
Spoken:    "Chapter 1: The Horror in Clay\n\nIn the year 1926..."
             ↓ Mapping saved
Position:  {0: 0, 4: 8, ...}  # Original char 4 → Spoken char 8
```

### 2. Audio Generation
```
Preprocessed text → Kokoro TTS → Audio files
                      ↓
                Text still says "Chapter 1" naturally
```

### 3. Word Timing Alignment
```
Audio file + Preprocessed text → WhisperX/Fallback → Word timestamps
                                    ↓
{word: "Chapter", start: 0.0, end: 0.4, text_pos: 0}
{word: "1", start: 0.5, end: 0.7, text_pos: 8}
```

### 4. Real-time Sync
```
Audio playing at 12.5s → Binary search word timings → Word #42
                            ↓
                    Highlight word #42
                            ↓
                    Auto-scroll to keep visible
```

### 5. Click-to-Seek
```
User clicks word #100 → Get word.start (50.2s) → audio.currentTime = 50.2
                            ↓
                    Audio jumps to word position
```

## API Reference

### AudioTextPreprocessor

```python
from audio_text_preprocessor import AudioTextPreprocessor

preprocessor = AudioTextPreprocessor()
result = preprocessor.preprocess_for_speech(text)

# Access results
result.spoken_text          # Transformed text
result.original_text        # Original text
result.transformations      # List of changes made
result.get_spoken_pos(pos)  # Map original → spoken
result.get_original_pos(pos) # Map spoken → original

# Save mapping to JSON
preprocessor.save_mapping(result, "output.json")
```

### KaraokeSync (JavaScript)

```javascript
// Initialize
const karaoke = new KaraokeSync(audioElement);

// Load word timings
await karaoke.loadWordTimings(bookId);

// Set chapter
karaoke.setChapter(1);

// Render text with word spans
karaoke.renderText(textContainer);

// Enable real-time sync
karaoke.enable();

// Get current word position
const wordIndex = karaoke.getCurrentWordIndex();

// Seek to specific word
karaoke.seekToWordIndex(42);

// Clean up
karaoke.destroy();
```

## Position Tracking Schema

Playback position now includes word-level granularity:

```json
{
  "device_id": {
    "book:variant": {
      "position": 12.5,      // Seconds into audio
      "file_index": 0,       // Which audio file
      "word_index": 143,     // Which word (NEW!)
      "speed": 1.3,          // Playback speed
      "last_updated": "2026-02-08T..."
    }
  }
}
```

**Benefits:**
- Resume playback at exact word, not just file/chapter
- Restore karaoke highlight position after pause
- Sync across devices with word precision

## Performance

### Word Timing Generation Speed

| Method | Speed | Accuracy | Requirements |
|--------|-------|----------|--------------|
| WhisperX | 1-2x realtime | ★★★★★ | `pip install whisperx` |
| whisper.cpp | 2-3x realtime | ★★★★☆ | Binary download |
| Fallback | Instant | ★★☆☆☆ | None (built-in) |

**Example:** 10-minute audiobook
- WhisperX: ~5-10 minutes
- Fallback: <1 second

### Runtime Performance

- **Word lookup:** O(log n) binary search - ~1μs per update
- **Highlight update:** O(1) DOM manipulation
- **Auto-scroll:** Smooth CSS transition
- **Memory:** ~500KB per 100,000 words

## Troubleshooting

### Word timings not available

```bash
# Check if word timing file exists
ls books/*/book_name_word_timings.json

# Generate manually
python generate_word_timings.py books/book_name/audio_kokoro/audiobook.m3u
```

### Karaoke toggle not visible

- Word timings must be generated first
- Check browser console for errors
- Verify API endpoint: `GET /api/books/{book_id}/word-timings`

### Words not highlighting

- Enable karaoke mode in Text Sync panel
- Check that audio is playing (not paused)
- Verify word timings loaded (check browser console)

### Highlighting out of sync

- Use WhisperX instead of fallback for better accuracy:
  ```bash
  python generate_word_timings.py playlist.m3u --method whisperx
  ```

## Future Enhancements

Potential improvements to the karaoke system:

1. **Sentence-level highlighting** - Highlight full sentence, not just word
2. **Speed-aware timing** - Adjust word timings based on playback speed
3. **Visual waveform** - Show audio waveform with word positions
4. **Export annotations** - Save highlighted sections as bookmarks
5. **Multilingual support** - Word boundaries for non-English languages

## Examples

### Example 1: Basic Usage

```bash
# Generate audiobook with karaoke
python make_audiobook.py books/alice_adventures/alices_adventures.md \
  --voice bf_emma \
  --generate-word-timings

# Output:
# ✓ Audio generated
# ✓ Word timings generated (52 chapters, 45,213 words)
# ✓ Karaoke sync enabled
```

### Example 2: Manual Word Timing

```bash
# If you already have audio, just generate timings
python generate_word_timings.py \
  books/call_cthulhu/audio_kokoro/The_CALL_of_CTHULHU_audiobook.m3u \
  --method whisperx

# Output:
# ✓ Loaded word timings: 3 chapters
# ✓ Word timings saved: books/call_cthulhu/call_cthulhu_word_timings.json
# Chapters: 3
# Total words: 7,891
# Total duration: 62.3 minutes
```

### Example 3: Preprocessing Only

```bash
# Test text preprocessing without generating audio
python audio_text_preprocessor.py books/call_cthulhu/call_cthulhu.md output.json

# Output:
# Original text: 42,315 characters
# Spoken text:   42,401 characters
# Transformations: 3
#   1. numbered_header: '## 1: The Horror in Clay' → 'Chapter 1: The Horror in Clay'
#   2. numbered_header: '## 2: The Tale of Inspector Legrasse' → 'Chapter 2: The Tale...'
#   3. numbered_header: '## 3: The Madness from the Sea' → 'Chapter 3: The Madness...'
```

## Technical Details

### Bidirectional Position Mapping

The preprocessing system maintains bidirectional mapping to support:

1. **Audio → Text sync** - Find text position from audio timestamp
2. **Text → Audio sync** - Find audio position from text click
3. **Resume playback** - Restore exact position across restarts

```python
# Example: User clicks character 150 in UI
original_pos = 150

# Map to spoken text (after preprocessing)
spoken_pos = result.get_spoken_pos(original_pos)  # → 158

# Lookup word at spoken position
word = find_word_at_text_pos(spoken_pos)  # → word #42

# Seek audio to word start
audio.currentTime = word.start  # → 12.5 seconds
```

### Word Boundary Detection

Word timings use intelligent boundary detection:

```javascript
// Binary search for word at current audio time
findWordAtTime(12.5) {
  // Search word timings where:
  //   word.start <= 12.5 <= word.end

  // Returns word index for highlighting
}
```

## License

Apache 2.0 - Same as Kokoro TTS and the main project.

---

**Questions?** Check [GUIDE.md](GUIDE.md) or [CLAUDE.md](CLAUDE.md) for more details.
