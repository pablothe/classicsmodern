# Audiobook Chapter Architecture - Complete Guide

## 🎯 **Understanding Your System**

After analyzing your codebase, here's how everything works:

### **Book → Audio Pipeline**

```
1. Text File (.md)
   ↓
2. TTS Generation (local_tts_xtts.py)
   ├─ Detects chapters (Roman numerals, headers)
   ├─ Chunks text into ~250 char pieces
   ├─ Generates audio chunk for each piece
   └─ Combines chunks into chapter files
   ↓
3. Audio Files
   ├─ name_chapter_01.mp3 (Chapter 1)
   ├─ name_chapter_02.mp3 (Chapter 2)
   └─ name_chapter_03.mp3 (Chapter 3)
   ↓
4. Playlist (M3U)
   name_audiobook_TIMESTAMP.m3u
   Lists all chapter files in order
   ↓
5. Server (audiobook_server.py)
   Serves audio + metadata to web player
   ↓
6. Web Player (player.html + player.js)
   Shows chapters, allows navigation
```

## 📁 **File Structure Example**

```
books/
  alice_adventures/
    # Source text
    alices_adventures.md

    # Generated audio
    audio_xtts/
      # Individual chapters (combined from chunks)
      alices_adventures_chapter_01.mp3
      alices_adventures_chapter_02.mp3
      ...
      alices_adventures_chapter_12.mp3

      # Playlist pointing to chapters
      alices_adventures_audiobook_20260107_123456.m3u

      # Raw chunks (before combining)
      raw/
        alices_adventures_chunk001_raw.wav
        alices_adventures_chunk002_raw.wav
        ...

    # Chapter metadata (for web player)
    alices_adventures_chapter_data.json  ← YOU NEED THIS!
```

## 🔑 **Key Insight: How Chapters Work**

### **TTS Generation (`local_tts_xtts.py` lines 481-679)**

1. **Detects chapters** in text (line 483):
   - Looks for Roman numerals (I., II., III.)
   - Looks for Markdown headers (# Chapter 1)
   - Records chapter positions in text

2. **Chunks text** (line 505):
   - Splits into ~250 character chunks (XTTS limit)
   - Preserves chapter markers

3. **Maps chunks to chapters** (lines 515-541):
   - Tracks which chunk belongs to which chapter
   - Example: Chunks 1-5 → Chapter 1, Chunks 6-10 → Chapter 2

4. **Generates audio** (lines 574-631):
   - Creates WAV for each chunk
   - Post-processes (speed, normalize, MP3)

5. **Combines chunks into chapter files** (lines 644-679):
   - Uses FFmpeg to join chunks: `chunk001.mp3 + chunk002.mp3 → chapter_01.mp3`
   - Creates master playlist listing chapters

### **The Result**

**Each audio file = One chapter**
- `chapter_01.mp3` contains the entire Chapter 1
- `chapter_02.mp3` contains the entire Chapter 2
- etc.

**Playlist structure:**
```m3u
#EXTM3U
#EXTINF:-1,Chapter 1
alices_adventures_chapter_01.mp3
#EXTINF:-1,Chapter 2
alices_adventures_chapter_02.mp3
...
```

## 🎯 **What the Web Player Needs**

The web player displays chapters based on **`chapter_data.json`** files:

```json
{
  "title": "Alice's Adventures in Wonderland",
  "author": "Lewis Carroll",
  "chapters": [
    {
      "number": 1,
      "title": "Down the Rabbit-Hole",
      "file_index": 0,      ← Which file in playlist (0 = first)
      "timestamp": 0.0      ← When chapter starts in that file (seconds)
    },
    {
      "number": 2,
      "title": "The Pool of Tears",
      "file_index": 1,      ← Second file in playlist
      "timestamp": 0.0      ← Starts at beginning of file
    }
  ]
}
```

### **Why `file_index` and `timestamp`?**

- **`file_index`**: Which audio file in the playlist (0 = first, 1 = second, etc.)
- **`timestamp`**: Where in that file the chapter starts (in seconds)

**For chapter-based files:**
- Each chapter is its own file
- `timestamp` is always `0.0` (chapter starts at beginning of file)
- `file_index` just points to which file (0, 1, 2, ...)

**Example:**
```json
{
  "chapters": [
    {"number": 1, "file_index": 0, "timestamp": 0.0},  // chapter_01.mp3
    {"number": 2, "file_index": 1, "timestamp": 0.0},  // chapter_02.mp3
    {"number": 3, "file_index": 2, "timestamp": 0.0}   // chapter_03.mp3
  ]
}
```

## 🛠️ **How to Generate Chapter Metadata**

I've created [generate_chapter_metadata.py](generate_chapter_metadata.py) to automate this:

```bash
# Run after TTS generation
python3 generate_chapter_metadata.py books/alice_adventures/audio_xtts/alices_adventures_audiobook_*.m3u

# Or with custom title/author
python3 generate_chapter_metadata.py books/alice_adventures/audio_xtts/alices_adventures_audiobook_*.m3u "Alice's Adventures" "Lewis Carroll"
```

**What it does:**
1. Reads your M3U playlist
2. Detects chapter files (`*_chapter_01.mp3`, `*_chapter_02.mp3`)
3. Maps each chapter to its `file_index` in playlist
4. Creates `chapter_data.json` in book root directory

**Output:**
```
✓ Found 12 audio files
✓ Detected chapter-based organization (12 chapters)
  Chapter  1: file_index=0, files=1
  Chapter  2: file_index=1, files=1
  ...
✓ Chapter metadata saved: books/alice_adventures/alices_adventures_chapter_data.json
```

## 🎬 **Complete Workflow**

### **1. Generate Audiobook with Chapters**

```bash
# Make sure your book has chapter markers (I., II., III. or # Chapter 1)
python3 local_tts_xtts.py books/alice_adventures/alices_adventures.md voice_ref.wav en

# Output:
# ✓ Found 12 chapters - preserving markers during cleaning
# ✓ Mapped 156 chunks to 12 chapters
# 📚 Combining 156 chunks into 12 chapters...
# ✓ Master audiobook playlist created: alices_adventures_audiobook_20260107_123456.m3u
```

### **2. Generate Chapter Metadata**

```bash
# Run the metadata generator
python3 generate_chapter_metadata.py books/alice_adventures/audio_xtts/alices_adventures_audiobook_*.m3u "Alice's Adventures in Wonderland" "Lewis Carroll"

# Output:
# ✓ Chapter metadata saved: books/alice_adventures/alices_adventures_chapter_data.json
```

### **3. Start Server & Test**

```bash
cd server
python3 audiobook_server.py

# Open http://localhost:8000
# Select Alice's Adventures
# You'll now see:
#   - Current chapter name below book title
#   - "Chapters" button (📑)
#   - Tap to see Audible-style chapter list!
```

## 🔧 **Automatic Integration (Future)**

### **Option A: Modify `local_tts_xtts.py`**

Add chapter metadata generation at the end:

```python
# At end of generate_audiobook() function (after line 720)
if chapters and len(chapters) > 1:
    print("\n📋 Generating chapter metadata...")
    chapter_metadata = {
        "title": base_name.replace('_', ' ').title(),
        "chapters": []
    }

    for chapter_num in range(1, max(chunk_to_chapter) + 1):
        chapter_metadata["chapters"].append({
            "number": chapter_num,
            "title": f"Chapter {chapter_num}",
            "file_index": chapter_num - 1,  # 0-indexed
            "timestamp": 0.0
        })

    # Save to book root
    metadata_path = input_path.parent / f"{base_name}_chapter_data.json"
    with open(metadata_path, 'w', encoding='utf-8') as f:
        json.dump(chapter_metadata, f, indent=2, ensure_ascii=False)

    print(f"✓ Chapter metadata: {metadata_path.name}")
```

## 📊 **Current Status**

✅ Sleep timer - Working
✅ Audible-style chapter UI - Implemented
✅ Chapter metadata format - Defined
✅ Metadata generator script - Created
⏳ Your books - Need chapter metadata files

## 🎯 **Next Steps**

1. **Test with Alice:**
   ```bash
   python3 generate_chapter_metadata.py books/alice_adventures/audio_xtts/alices_adventures_audiobook_*.m3u "Alice's Adventures in Wonderland" "Lewis Carroll"
   cd server && python3 audiobook_server.py
   ```

2. **Generate for all books:**
   ```bash
   # Find all audiobook playlists
   find books -name "*_audiobook_*.m3u"

   # Run generator for each
   for playlist in $(find books -name "*_audiobook_*.m3u"); do
       python3 generate_chapter_metadata.py "$playlist"
   done
   ```

3. **Future automation:**
   - Modify `local_tts_xtts.py` to auto-generate metadata
   - Or create a post-processing script

## 💡 **Key Takeaways**

1. **Your audiobooks ARE chapter-based** - each chapter is its own MP3 file
2. **Chapters are created during TTS** - `local_tts_xtts.py` detects and combines them
3. **Web player needs metadata** - simple JSON mapping chapters to file positions
4. **Easy to generate** - just run `generate_chapter_metadata.py` on your playlists

The Audible-style chapter navigation is ready to use - you just need the metadata files!
