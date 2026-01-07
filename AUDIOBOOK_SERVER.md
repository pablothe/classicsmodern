# Audiobook Server Architecture

## Overview

A local WiFi-based audiobook server that allows you to produce audiobooks on your Mac and consume them on your phone without manual file transfers.

## Architecture

```
┌─────────────────┐         WiFi          ┌──────────────────┐
│  Mac (Server)   │◄─────────────────────►│  Phone (Client)  │
│                 │                        │                  │
│ • FastAPI       │   HTTP/JSON API        │ • Web Browser    │
│ • books/ dir    │   Audio Streaming      │ • PWA Player     │
│ • playback DB   │   Position Sync        │ • LocalStorage   │
└─────────────────┘                        └──────────────────┘
```

## Components

### 1. Server (Mac) - `server/audiobook_server.py`

**Purpose:** Serve audiobooks and track playback state

**Features:**
- Auto-discover books in `books/` directory
- Serve audio files with streaming support (HTTP range requests)
- REST API for book catalog and metadata
- Playback position tracking per device
- CORS enabled for phone access

**Endpoints:**
```
GET  /api/books                 # List all books with metadata
GET  /api/books/{book_id}       # Get book details + chapters
GET  /api/books/{book_id}/audio # Stream audio file
GET  /api/playback/{book_id}    # Get saved position
POST /api/playback/{book_id}    # Save position + speed
```

**Database:** `server/playback_db.json`
```json
{
  "device_123": {
    "book_crime_punishment": {
      "position": 1847.2,
      "speed": 1.25,
      "last_updated": "2026-01-07T10:30:00Z"
    }
  }
}
```

### 2. Web Player (Phone) - `server/static/player.html`

**Purpose:** Progressive Web App for audiobook playback

**Features:**
- Book browser (shows all books from server)
- HTML5 audio player with:
  - Speed control (0.5x - 2.0x)
  - Auto-save position every 5 seconds
  - Auto-resume on page load
  - Chapter navigation (skip forward/back)
  - Sleep timer
  - Offline mode (ServiceWorker caching)
- Responsive design (mobile-first)
- No installation required (PWA installable from browser)

**Local Storage:**
- Device ID (persistent identifier)
- Downloaded books (for offline mode)
- Playback preferences

### 3. Metadata System - Enhanced `book_preprocessor.py`

**Purpose:** Generate book metadata for server API

**Current Output:** `*_chapter_data.json`
```json
{
  "title": "Crime and Punishment",
  "chapters": [
    {"number": 1, "title": "Chapter I", "start_line": 45}
  ]
}
```

**Enhanced Output (Future):**
- Audio file timestamps per chapter
- Total duration
- Author, language, translation info
- Cover image path

## Workflow

### Production (Mac)

```bash
# 1. Translate book
python3 local_reader_batch_translator.py books/mybook/chunks/ Russian "Modern English"

# 2. Generate audio
python3 local_tts_xtts.py books/mybook/translated.md voice.wav en

# 3. Preprocess metadata
python3 book_preprocessor.py books/mybook/translated.md

# 4. Start server (automatic discovery)
python3 server/audiobook_server.py
# Server running at http://localhost:8000
```

### Consumption (Phone)

1. Connect to same WiFi as Mac
2. Open browser: `http://localhost:8000`
3. Browse books, tap to play
4. Player automatically:
   - Saves position every 5 sec
   - Syncs with server
   - Resumes on return
   - Works offline if downloaded

## Technology Stack

**Backend:**
- FastAPI (async Python web framework)
- uvicorn (ASGI server)
- JSON file database (simple, no dependencies)

**Frontend:**
- Vanilla JavaScript (no frameworks needed)
- HTML5 Audio API
- Service Workers (for offline)
- LocalStorage (for device ID + prefs)
- CSS Grid/Flexbox (responsive layout)

**Why this stack:**
- ✅ Zero dependencies beyond Python
- ✅ Works on any device with browser
- ✅ No app store approval needed
- ✅ Fast development
- ✅ Easy to maintain

## File Organization

```
classicsmodern/
├── books/                          # Existing audiobook files
│   └── [book_name]/
│       ├── translated.md
│       ├── *_chapter_data.json     # Preprocessor output
│       └── audio_xtts/
│           ├── *.mp3               # Audio files
│           └── *_audiobook.m3u     # Playlist
├── server/
│   ├── audiobook_server.py         # FastAPI server
│   ├── playback_db.json            # Position tracking
│   ├── static/
│   │   ├── player.html             # Web player
│   │   ├── player.js               # Player logic
│   │   ├── player.css              # Styling
│   │   └── manifest.json           # PWA manifest
│   └── requirements.txt            # fastapi, uvicorn
└── AUDIOBOOK_SERVER.md             # This file
```

## Security Considerations

**Current (LAN only):**
- No authentication (safe on home WiFi)
- Server only binds to LAN IP
- No external access

**Future (if needed):**
- Basic auth (username/password)
- HTTPS with self-signed cert
- Token-based device auth

## Future Enhancements

**Phase 2:**
- [ ] Multi-file audiobooks (combine M3U chapters)
- [ ] Bookmarking system (save multiple positions)
- [ ] Playback stats (listening time, completion %)
- [ ] Book ratings/notes

**Phase 3:**
- [ ] Multiple user support
- [ ] Sync across devices (resume on iPad where you left off on iPhone)
- [ ] Download management (offline library)
- [ ] Chapter-level progress tracking

**Phase 4:**
- [ ] Remote access (Tailscale/VPN)
- [ ] Cover image extraction/upload
- [ ] Audiobook recommendations
- [ ] Integration with existing m3u playlists

## Development Timeline

- **Phase 1 (Server):** 2-3 hours
  - FastAPI server with book discovery
  - REST API endpoints
  - Position tracking database

- **Phase 2 (Player):** 3-4 hours
  - HTML5 audio player
  - Speed control + position save
  - Responsive UI

- **Phase 3 (Chapters):** 1-2 hours
  - Chapter navigation
  - Integration with preprocessor JSON

- **Phase 4 (Offline):** 2-3 hours
  - Service Worker
  - Download management
  - Offline playback

**Total:** ~10-12 hours for complete system
