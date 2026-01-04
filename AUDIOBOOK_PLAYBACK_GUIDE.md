# Audiobook Playback Guide

Complete guide for playing your translated audiobooks.

## Quick Start

You have **3 options** for playing your audiobooks:

### Option 1: Web Player (Recommended for Desktop)
**Best for:** Progress tracking, chapter navigation, easy access

```bash
python serve_audiobook.py books/crime_punishment/chunks/test_chunk/translated/audio/
```

This will:
- Start a local web server
- Open the audiobook player in your browser
- Save your progress automatically
- Allow speed control (0.5x - 2x)
- Chapter/part navigation
- Keyboard shortcuts (Space = play/pause, arrows = skip)

### Option 2: Combined Single File
**Best for:** Sharing, mobile devices, standard audio players

```bash
# Install ffmpeg first (if not already installed)
brew install ffmpeg

# Combine all parts into one file
python local_reader_audio_combiner.py \
  books/crime_punishment/chunks/test_chunk/translated/audio/chunk_001_modern_spanish_4b_audiobook_20260102_153057.m3u
```

This creates a single MP3 file you can play anywhere.

### Option 3: Native Playlist
**Best for:** Quick listening with any media player

```bash
# Open the M3U playlist with any player (VLC, iTunes, etc.)
open books/crime_punishment/chunks/test_chunk/translated/audio/chunk_001_modern_spanish_4b_audiobook_20260102_153057.m3u
```

---

## Detailed Instructions

### Option 1: Web Player

#### Setup
```bash
# 1. Navigate to your project directory
cd /Users/pabloeder/classicsmodern/classicsmodern

# 2. Start the web player
python serve_audiobook.py books/crime_punishment/chunks/test_chunk/translated/audio/
```

#### Features
- **Progress Saving**: Automatically saves your position every 10 seconds
- **Speed Control**: Adjust from 0.5x to 2x speed
- **Skip Controls**: 15-second skip forward/back
- **Chapter Navigation**: Click any part in the playlist
- **Keyboard Shortcuts**:
  - `Space`: Play/Pause
  - `←`: Skip back 15 seconds
  - `→`: Skip forward 15 seconds

#### How It Works
1. Server starts at `http://localhost:8000`
2. Browser opens automatically
3. Progress stored in browser's localStorage
4. Resume exactly where you left off

#### Customization
Edit `templates/audiobook_player.html` to:
- Change colors/theme
- Adjust skip intervals
- Modify UI layout
- Add bookmarks feature

---

### Option 2: Combined Single File

#### Prerequisites
```bash
# Install ffmpeg (one-time setup)
brew install ffmpeg  # macOS
# or
sudo apt install ffmpeg  # Linux
```

#### Usage
```bash
# From playlist (automatic)
python local_reader_audio_combiner.py path/to/playlist.m3u

# Specify output name
python local_reader_audio_combiner.py path/to/playlist.m3u my_audiobook.mp3
```

#### What It Does
- Reads the M3U playlist
- Combines all MP3 files in order
- Creates single output file (no re-encoding, fast!)
- Preserves audio quality

#### Example
```bash
python local_reader_audio_combiner.py \
  books/crime_punishment/chunks/test_chunk/translated/audio/chunk_001_modern_spanish_4b_audiobook_20260102_153057.m3u \
  CrimeAndPunishment_Chapter1_Spanish.mp3
```

#### Output
```
Combining 25 files...
✓ Combined audiobook created: CrimeAndPunishment_Chapter1_Spanish.mp3

File size: 82.5 MB
Location: books/crime_punishment/chunks/test_chunk/translated/audio/CrimeAndPunishment_Chapter1_Spanish.mp3
```

Now you can:
- Transfer to phone/tablet
- Share with others
- Play in any audio app
- Add to iTunes/Music library

---

### Option 3: Playlist (M3U)

#### Basic Usage
```bash
# macOS - opens in Music/iTunes
open path/to/playlist.m3u

# Or drag-and-drop into VLC, QuickTime, etc.
```

#### Recommended Players

**macOS:**
- VLC (free, best features)
- QuickTime (built-in)
- Music/iTunes (good integration)

**Windows:**
- VLC (free, recommended)
- Windows Media Player
- Foobar2000

**Linux:**
- VLC
- Audacious
- Clementine

#### Pros & Cons

**Pros:**
- Works with any media player
- No conversion needed
- Chapter markers (in some players)

**Cons:**
- No built-in progress saving (depends on player)
- Need to keep all files together
- Less portable than single file

---

## Comparison

| Feature | Web Player | Combined File | Playlist |
|---------|-----------|---------------|----------|
| Progress Saving | ✅ Automatic | ❌ Player-dependent | ❌ Player-dependent |
| Speed Control | ✅ 0.5x - 2x | ✅ Player-dependent | ✅ Player-dependent |
| Skip Controls | ✅ 15s forward/back | ✅ Player-dependent | ✅ Player-dependent |
| Chapter Navigation | ✅ Click parts | ❌ Single file | ✅ Individual parts |
| Mobile Friendly | ⚠️ Browser required | ✅ Works everywhere | ✅ Works everywhere |
| Offline Support | ⚠️ Local only | ✅ Full offline | ✅ Full offline |
| File Size | N/A (streaming) | ~80-160 MB | ~80-160 MB total |
| Easy Sharing | ❌ | ✅ Single file | ⚠️ Multiple files |

---

## Advanced: Mobile App (Future)

According to LOCAL_READER_README.md Phase 6, the ultimate solution is a dedicated mobile app:

### Planned Features
- Background playback
- Lock screen controls
- Sleep timer
- Bookmarks with notes
- CarPlay/Android Auto support
- Cross-device sync
- Offline library
- Download manager

### Tech Stack (Planned)
- React Native
- Expo
- react-native-track-player
- SQLite for progress

---

## Troubleshooting

### Web Player Won't Load
```bash
# Check if port is already in use
lsof -i :8000

# Use different port
python serve_audiobook.py audio/ 8080
```

### ffmpeg Not Found
```bash
# Install ffmpeg
brew install ffmpeg  # macOS
sudo apt install ffmpeg  # Ubuntu/Debian
```

### Audio Files Not Playing
1. Check file paths in browser console
2. Ensure all MP3 files are in audio directory
3. Try serving from parent directory

### Progress Not Saving (Web Player)
- Clear browser cache
- Check browser localStorage is enabled
- Try different browser

---

## Tips & Best Practices

### For Long Audiobooks
1. **Use web player** for progress tracking
2. **Combine into single file** for mobile devices
3. **Keep original parts** in case you need to re-edit

### For Sharing
1. **Combine files** for easy transfer
2. Include **metadata** (artist, album, cover art)
3. Consider **MP3 tags** for better organization

### For Quality
- Original files are already optimized
- Combining doesn't re-encode (preserves quality)
- Speed changes don't affect quality (pitch preserved)

---

## Next Steps

### Immediate
1. Try the web player
2. Test progress saving
3. Experiment with speed control

### Short-term
1. Combine files for mobile
2. Create cover art
3. Add metadata

### Long-term
1. Build mobile app (Phase 6)
2. Add compression/summarization
3. Implement local TTS (replace OpenAI)

---

## File Locations

### Generated Files
```
books/crime_punishment/chunks/test_chunk/translated/audio/
├── chunk_001_modern_spanish_4b_part001_fable_20260102_153057.mp3
├── chunk_001_modern_spanish_4b_part002_fable_20260102_153057.mp3
├── ... (25 parts total)
├── chunk_001_modern_spanish_4b_audiobook_20260102_153057.m3u (playlist)
└── player.html (created when you run serve_audiobook.py)
```

### Scripts
```
classicsmodern/
├── serve_audiobook.py              # Web player server
├── local_reader_audio_combiner.py  # Combine MP3 files
├── templates/
│   └── audiobook_player.html       # Web player interface
└── AUDIOBOOK_PLAYBACK_GUIDE.md     # This file
```

---

## Quick Reference

```bash
# Web player (progress saving)
python serve_audiobook.py books/crime_punishment/chunks/test_chunk/translated/audio/

# Combine into single file
python local_reader_audio_combiner.py \
  books/crime_punishment/chunks/test_chunk/translated/audio/chunk_001_modern_spanish_4b_audiobook_20260102_153057.m3u \
  CrimeAndPunishment_Ch1.mp3

# Play with default app
open books/crime_punishment/chunks/test_chunk/translated/audio/chunk_001_modern_spanish_4b_audiobook_20260102_153057.m3u
```

Enjoy your audiobook! 🎧
