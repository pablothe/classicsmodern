# Local Book Reader & Compressor

A fully localized application for downloading, translating, compressing, and generating audiobooks from classic literature - all running on local AI models with no external API dependencies.

## Overview

This application allows users to:
1. Select a book from Project Gutenberg
2. Choose target language and available reading time
3. Get an intelligently compressed translation that fits their time budget
4. Generate a local TTS audiobook of the compressed version

**Key Feature**: Two-step translation → compression workflow allows users to adjust compression level mid-process without re-translating.

## Architecture

### User Flow
```
[Web Interface]
    ↓
[Book Selection] → [Language + Time Budget]
    ↓
[Download from Gutenberg]
    ↓
[Step 1: Translation] (ollama zongwei/gemma3-translator:1b)
    ↓
[Step 2: Compression/Summarization] (same model, adjustable)
    ↓
[Audio Generation] (Orpheus-3B TTS via GGUF)
    ↓
[Downloadable Audiobook]
```

### Technology Stack

- **Web Framework**: Flask or FastAPI (async support for long-running tasks)
- **Translation Model**: Ollama with `zongwei/gemma3-translator:1b` (upgrade to 4b later)
- **TTS Model**: Orpheus-3B TTS (GGUF format) via llama.cpp bindings
- **Temporary TTS**: OpenAI Whisper API (for initial testing only)
- **Book Source**: Project Gutenberg API/scraping
- **Frontend**: HTML/CSS/JavaScript with real-time progress updates (WebSockets/SSE)
- **Task Queue**: Background workers for long-running translation/TTS tasks

## Sub-Tasks & Implementation Phases

### Phase 1: Core Infrastructure
**Goal**: Set up local model environment and basic web interface

#### Task 1.1: Environment Setup
- [ ] Install and configure Ollama
- [ ] Pull `zongwei/gemma3-translator:1b` model
- [ ] Test model with sample translation calls
- [ ] Document hardware requirements (RAM, GPU, disk space)
- [ ] Create requirements.txt for Python dependencies

#### Task 1.2: Web Interface Foundation
- [ ] Choose Flask vs FastAPI (recommend FastAPI for async)
- [ ] Create basic HTML interface with book selection
- [ ] Implement language selection dropdown
- [ ] Add time budget input (hours:minutes)
- [ ] Set up basic routing and template rendering

#### Task 1.3: Project Gutenberg Integration
- [ ] Research Gutenberg API/scraping options
- [ ] Implement book search functionality
- [ ] Create book download module (reuse/adapt gutenberg_extractor.py)
- [ ] Add book metadata extraction (title, author, original language, word count)
- [ ] Implement book caching to avoid re-downloads

---

### Phase 2: Translation Pipeline
**Goal**: Implement two-step translation and compression workflow

#### Task 2.1: Full Translation Module
- [ ] Create Ollama API integration layer
- [ ] Adapt existing chunking logic from translator.py for local models
- [ ] Implement Markdown-aware translation (preserve structure)
- [ ] Add progress tracking for translation steps
- [ ] Store intermediate translation in database/file system
- [ ] Test with sample books (varying lengths)

#### Task 2.2: Compression/Summarization Engine
- [ ] Calculate compression ratio from time budget and word count
  - Formula: `compression_ratio = (target_minutes * avg_words_per_minute) / total_words`
  - Typical audiobook: ~150-160 words/minute
- [ ] Design compression prompts for the translation model
- [ ] Implement chapter-level summarization strategy
- [ ] Preserve narrative coherence across compressed sections
- [ ] Add quality checks (verify output makes sense)
- [ ] Allow re-compression with different ratios without re-translation

#### Task 2.3: Progress & State Management
- [ ] Create job queue system (Celery, RQ, or custom)
- [ ] Implement WebSocket/SSE for real-time progress updates
- [ ] Add pause/resume functionality for long-running tasks
- [ ] Store job state (translation complete, compression in progress, etc.)
- [ ] Handle failures gracefully with retry logic

---

### Phase 3: Local Audio Generation
**Goal**: Generate high-quality audiobooks using local TTS

#### Task 3.1: OpenAI Whisper Integration (Temporary)
- [ ] Integrate OpenAI TTS API (reuse audio_translator.py logic)
- [ ] Test with compressed book outputs
- [ ] Validate audio quality and timing
- [ ] **Note**: This is temporary scaffolding for testing

#### Task 3.2: Local TTS Setup (Orpheus-3B)
- [ ] Research Orpheus-3B TTS GGUF integration options
- [ ] Set up llama.cpp with TTS support
- [ ] Create Python bindings/wrapper for TTS generation
- [ ] Test voice quality and generation speed
- [ ] Benchmark: determine realistic audio generation time

#### Task 3.3: Audio Processing Pipeline
- [ ] Adapt text cleaning from audio_translator.py
- [ ] Implement chunk-based audio generation (avoid memory issues)
- [ ] Add silence/pauses at sentence/paragraph boundaries
- [ ] Generate playlist files (M3U) for multi-part audiobooks
- [ ] Combine audio chunks into single file option
- [ ] Support multiple audio formats (WAV, MP3, FLAC)

---

### Phase 4: User Experience & Polish
**Goal**: Create smooth, intuitive user experience

#### Task 4.1: Advanced UI Features
- [ ] Add book preview (first chapter/pages)
- [ ] Show estimated translation time before starting
- [ ] Display compression preview (show original vs compressed sample)
- [ ] Implement "favorite books" or history
- [ ] Add dark mode toggle

#### Task 4.2: Compression Adjustment Interface
- [ ] Create slider for compression ratio adjustment
- [ ] Show real-time estimate of output length
- [ ] Allow re-compression from saved translation
- [ ] Compare different compression levels side-by-side

#### Task 4.3: Download & Playback
- [ ] Implement audiobook download (single file or zip of parts)
- [ ] Add in-browser audio player with playlist support
- [ ] Include compressed text download (Markdown/PDF)
- [ ] Generate metadata files (book info, compression ratio, etc.)

#### Task 4.4: Error Handling & Validation
- [ ] Validate user inputs (reasonable time budgets, supported languages)
- [ ] Handle model failures gracefully (timeouts, OOM errors)
- [ ] Add disk space checks before processing
- [ ] Implement rate limiting for resource-intensive operations
- [ ] Create user-friendly error messages

---

### Phase 5: Optimization & Scaling
**Goal**: Improve performance and support larger books

#### Task 5.1: Model Optimization
- [ ] Benchmark 1b vs 4b parameter models (zongwei/gemma3-translator)
- [ ] Implement model switching based on book length/complexity
- [ ] Add quantization options (4-bit, 8-bit) for faster inference
- [ ] Cache common translation patterns

#### Task 5.2: Parallel Processing
- [ ] Implement parallel chunk translation (multi-GPU support)
- [ ] Add queue management for multiple concurrent users
- [ ] Optimize audio generation parallelization
- [ ] Benchmark and document hardware scaling recommendations

#### Task 5.3: Quality Improvements
- [ ] Add translation quality metrics
- [ ] Implement A/B testing for compression strategies
- [ ] Fine-tune compression prompts based on feedback
- [ ] Add post-processing for common TTS pronunciation issues

---

### Phase 6: Mobile App Development
**Goal**: Build companion mobile app for superior audiobook experience

#### Task 6.1: Backend API Layer
- [ ] Design RESTful API endpoints (see API spec above)
- [ ] Implement `/api/books` endpoints for library browsing
- [ ] Add `/api/books/{id}/download` streaming endpoint
- [ ] Create `/api/progress` endpoints for sync (optional)
- [ ] Implement mDNS/Bonjour for auto-discovery
- [ ] Add API authentication (token-based or simple PIN)
- [ ] Document API with OpenAPI/Swagger spec
- [ ] Test API endpoints with Postman/curl

#### Task 6.2: Mobile App Setup (React Native)
- [ ] Initialize React Native project with Expo
- [ ] Set up navigation (React Navigation)
- [ ] Configure audio playback library (`react-native-track-player`)
- [ ] Set up local storage (AsyncStorage + SQLite)
- [ ] Create app icon and splash screen
- [ ] Configure development environment (iOS + Android)

#### Task 6.3: Server Discovery & Connection
- [ ] Implement mDNS-based auto-discovery
- [ ] Add manual IP entry fallback
- [ ] Create server connection test/ping
- [ ] Store last connected server
- [ ] Handle connection errors gracefully
- [ ] Display connection status indicator

#### Task 6.4: Book Library & Download
- [ ] Fetch and display available books from server
- [ ] Show book metadata (title, author, duration, size)
- [ ] Implement download manager with progress bar
- [ ] Handle partial downloads and resume capability
- [ ] Store downloaded books locally
- [ ] Show local vs. remote book status

#### Task 6.5: Audio Player Implementation
- [ ] Build audio player UI (play/pause, seek, skip)
- [ ] Implement playback speed control (0.5x - 2.5x)
- [ ] Add 15-second skip forward/backward buttons
- [ ] Display current time and remaining time
- [ ] Show progress bar with seek capability
- [ ] Integrate with OS media controls (lock screen)
- [ ] Enable background playback
- [ ] Save playback position every 10 seconds

#### Task 6.6: Progress Persistence & Sync
- [ ] Store playback position locally (SQLite)
- [ ] Auto-resume from last position on app restart
- [ ] Optionally sync position to server
- [ ] Handle multiple books with separate progress
- [ ] Add "mark as finished" functionality

#### Task 6.7: Enhanced Features
- [ ] Implement sleep timer (15/30/60 min presets)
- [ ] Add bookmark functionality
- [ ] Display chapter markers (if available)
- [ ] Show cover art in library and player
- [ ] Implement dark mode
- [ ] Add settings screen (playback defaults, storage location)

#### Task 6.8: Testing & Deployment
- [ ] Test on iOS devices (iPhone, iPad)
- [ ] Test on Android devices (various screen sizes)
- [ ] Verify background playback and lock screen controls
- [ ] Test offline mode (airplane mode)
- [ ] Optimize app size and performance
- [ ] Create app store screenshots and descriptions
- [ ] Submit to Apple App Store
- [ ] Submit to Google Play Store

---

## Technical Challenges & Solutions

### Challenge 1: Compression Quality
**Problem**: Naive summarization may lose plot coherence, character development, or key scenes.

**Solutions**:
- Use chapter/section-level summarization rather than arbitrary chunks
- Maintain character and plot arc consistency across summaries
- Implement "key scene detection" to preserve critical moments
- Allow user feedback to improve compression prompts

### Challenge 2: Local TTS Quality & Speed
**Problem**: Local TTS may be slower and lower quality than commercial APIs.

**Solutions**:
- Pre-process text to remove complex formatting that confuses TTS
- Implement caching for repeated phrases/words
- Use GPU acceleration for Orpheus-3B
- Consider hybrid approach: cache common words, generate unique phrases on-demand
- Set realistic user expectations about generation time

### Challenge 3: Memory & Resource Management
**Problem**: Processing long books (e.g., War and Peace) with limited RAM/GPU memory.

**Solutions**:
- Stream processing: never load entire book into memory
- Implement smart chunking with context overlap
- Add memory usage monitoring and auto-adjustments
- Provide clear hardware requirement guidelines
- Support pagination of results

### Challenge 4: Two-Step Workflow State Management
**Problem**: Users may want to re-compress without re-translating, requiring persistent state.

**Solutions**:
- Store translations in SQLite database or file system
- Implement job IDs for tracking multi-step processes
- Add "resume from translation" option
- Cache intermediate results with expiration policy
- Provide clear UI indication of which steps are complete

### Challenge 5: Translation Model Limitations
**Problem**: 1b parameter model may struggle with complex literary language or rare languages.

**Solutions**:
- Start with common language pairs (German→English, French→English)
- Implement fallback to 4b model for complex texts
- Add pre-processing to simplify archaic language structures
- Provide quality feedback mechanism to identify problem areas
- Consider ensemble approach: multiple translation passes

---

## File Structure

```
modernclassics/
├── Backend (Desktop Server)
│   ├── local_reader_app.py              # Main Flask/FastAPI application
│   ├── local_reader_config.py           # Configuration (model paths, API keys)
│   ├── local_reader_models.py           # Database models for jobs, books, etc.
│   ├── local_reader_api.py              # REST API endpoints for mobile app
│   ├── local_reader_translation.py      # Ollama translation integration
│   ├── local_reader_compression.py      # Compression/summarization logic
│   ├── local_reader_tts.py              # TTS generation (Whisper → Orpheus-3B)
│   ├── local_reader_gutenberg.py        # Book download and parsing
│   ├── local_reader_utils.py            # Shared utilities
│   ├── templates/                       # HTML templates (web interface)
│   │   ├── index.html                   # Main interface
│   │   ├── book_select.html             # Book selection page
│   │   ├── progress.html                # Progress tracking page
│   │   └── download.html                # Download/playback page
│   ├── static/                          # CSS, JS, images
│   │   ├── css/
│   │   ├── js/
│   │   └── audio/                       # Temporary audio storage
│   └── local_reader_data/               # Persistent storage
│       ├── books/                       # Downloaded books
│       ├── translations/                # Completed translations
│       ├── compressed/                  # Compressed versions
│       ├── audio/                       # Generated audiobooks
│       └── cache/                       # Model and API caches
│
└── Mobile App (React Native - Separate Repo)
    ├── src/
    │   ├── screens/
    │   │   ├── ServerSetup.tsx          # Server discovery/connection
    │   │   ├── BookLibrary.tsx          # Browse available books
    │   │   ├── BookDetail.tsx           # Book info before download
    │   │   ├── Downloads.tsx            # Download manager
    │   │   ├── Player.tsx               # Audio playback screen
    │   │   └── Settings.tsx             # App settings
    │   ├── components/
    │   │   ├── AudioPlayer.tsx          # Player controls component
    │   │   ├── ProgressBar.tsx          # Custom progress bar
    │   │   └── BookCard.tsx             # Book display card
    │   ├── services/
    │   │   ├── api.ts                   # REST API client
    │   │   ├── storage.ts               # Local storage manager
    │   │   ├── audioPlayer.ts           # Audio playback service
    │   │   └── discovery.ts             # Server auto-discovery
    │   ├── models/
    │   │   ├── Book.ts                  # Book data model
    │   │   └── Progress.ts              # Playback progress model
    │   └── utils/
    │       ├── fileDownload.ts          # Download handler
    │       └── formatting.ts            # Time formatting, etc.
    ├── assets/                          # Images, fonts
    ├── app.json                         # Expo configuration
    └── package.json                     # Dependencies
```

---

## Getting Started (Future)

### Prerequisites
```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull translation model
ollama pull zongwei/gemma3-translator:1b

# Install Python dependencies
pip install -r requirements.txt

# Set up TTS model (details TBD)
# Download Orpheus-3B TTS GGUF model
```

### Running the Application
```bash
# Start the web server
python local_reader_app.py

# Open browser to http://localhost:5000
```

---

## Mobile Device Access Solutions

### The Core Problem
Simple file downloads to mobile devices fail for audiobooks because:
- ❌ **No progress persistence**: Closing the file loses your position
- ❌ **No background playback**: Can't listen with screen off (especially iOS)
- ❌ **No proper controls**: Missing lock screen controls, speed adjustment, sleep timer
- ❌ **Poor library management**: Files scattered across folders
- ❌ **No bookmarks or chapter navigation**: Can't mark favorite passages

### The Solution: Dedicated Mobile App
Build a companion app (like Audible) where your computer produces translations locally, then the app downloads and plays them with full audiobook features - all without cloud storage or subscriptions.

---

### Challenge
Providing a seamless audiobook experience on mobile devices with:
- **Progress tracking**: Resume from where you left off
- **Playback controls**: Speed adjustment, sleep timer, bookmarks
- **Offline playback**: Listen without internet connection
- **Library management**: Handle multiple books
- No cloud infrastructure or subscription costs

### Solution: Companion Mobile App (Recommended)

#### Architecture Overview
```
[Desktop: Local Server]           [Mobile: Native App]
├── Translation Engine      ←──────  Book Request (WiFi)
├── Audio Generation        ──────→  Book + Metadata
├── Book Library                    ├── Local Storage
└── API Server (REST)               ├── Playback Engine
                                    ├── Progress Tracking
                                    └── Sync Status
```

#### Why a Native App Instead of Browser Downloads?

**Critical Features Requiring App**:
1. ✅ **Persistent playback position** - Saves exactly where you stopped
2. ✅ **Background playback** - Continues when screen is off
3. ✅ **Lock screen controls** - Standard media controls
4. ✅ **Offline access** - Books stored locally, no network needed
5. ✅ **Speed control** - 0.5x to 2.5x playback speed
6. ✅ **Sleep timer** - Auto-pause after X minutes
7. ✅ **Bookmarks** - Mark favorite passages
8. ✅ **Chapter navigation** - Jump between sections
9. ✅ **Library view** - Manage multiple books with cover art
10. ✅ **Progress sync** - Optionally sync position across devices

**What Browser Downloads Can't Do**:
- ❌ Resume position after closing file
- ❌ Background playback (iOS especially restrictive)
- ❌ Lock screen controls integration
- ❌ Proper library organization
- ❌ Metadata/cover art display
- ❌ Cross-device sync

---

### Mobile App Implementation Strategy

#### Option A: React Native App (Recommended)
**Single codebase for iOS + Android**

**Tech Stack**:
- **Framework**: React Native with Expo
- **Audio**: `expo-av` or `react-native-track-player`
- **Storage**: SQLite for metadata + local file system for audio
- **Networking**: REST API calls to local server
- **Discovery**: mDNS/Bonjour for auto-finding server on local network

**Pros**:
- One codebase for both platforms
- Faster development
- Large community, many libraries
- Can reuse web UI components

**Cons**:
- Slightly larger app size
- Need to learn React Native if unfamiliar

**Development Time**: ~2-4 weeks for MVP

#### Option B: Flutter App
**Google's cross-platform framework**

**Tech Stack**:
- **Framework**: Flutter/Dart
- **Audio**: `just_audio` or `audioplayers`
- **Storage**: SQLite + `path_provider`
- **Networking**: `http` or `dio`

**Pros**:
- Beautiful native-like UI
- Excellent performance
- Good audio library support

**Cons**:
- Learning curve if new to Dart
- Smaller community than React Native

**Development Time**: ~2-4 weeks for MVP

#### Option C: Native Apps (iOS Swift + Android Kotlin)
**Separate apps for each platform**

**Pros**:
- Best performance
- Full access to platform features
- Smallest app size

**Cons**:
- Need to build twice (iOS + Android)
- Longer development time
- Maintain two codebases

**Development Time**: ~4-8 weeks for MVP (both platforms)

---

### Recommended Tech Stack: React Native

**Why React Native for this project**:
1. You already have a web interface - can share design patterns
2. Audio playback is well-supported (`react-native-track-player`)
3. Local network discovery is straightforward
4. Rapid iteration during development
5. Easy to publish to both app stores from single codebase

---

### Mobile App Features (MVP)

#### Core Features
- [ ] **Server Discovery**: Auto-detect local server via mDNS or manual IP entry
- [ ] **Book Browser**: View available books from server with metadata
- [ ] **Download Manager**: WiFi-based book download with progress indicator
- [ ] **Audio Player**:
  - Play/pause/seek
  - 15s skip forward/backward
  - Playback speed (0.5x - 2.5x)
  - Progress bar with time remaining
- [ ] **Progress Persistence**: Save position every 10 seconds
- [ ] **Offline Library**: View downloaded books, play without network
- [ ] **Lock Screen Controls**: Standard media player integration
- [ ] **Background Playback**: Continue playing when app is backgrounded

#### Enhanced Features (V2)
- [ ] **Sleep Timer**: Auto-pause after 15/30/60 minutes
- [ ] **Bookmarks**: Save specific timestamps with notes
- [ ] **Chapter Navigation**: Jump to chapters (if metadata available)
- [ ] **Cover Art**: Display book covers in library
- [ ] **Sync Status**: Visual indicator for server connection
- [ ] **Dark Mode**: OLED-friendly dark theme
- [ ] **CarPlay/Android Auto**: In-car playback support
- [ ] **Cross-device Sync**: Resume on different device (optional)

---

### Server-Side API Requirements

The desktop server needs these additional endpoints for mobile app:

```python
# API Endpoints for Mobile App

# Discovery
GET  /api/ping                          # Health check for auto-discovery
GET  /api/info                          # Server version, capabilities

# Library
GET  /api/books                         # List all available books
GET  /api/books/{book_id}               # Get book details + metadata
GET  /api/books/{book_id}/cover         # Download cover image

# Downloads
GET  /api/books/{book_id}/download      # Stream/download audio file
GET  /api/books/{book_id}/chapters      # Chapter metadata (if available)

# Progress Sync (Optional)
POST /api/progress/{book_id}            # Save playback position
GET  /api/progress/{book_id}            # Get last position
GET  /api/progress                      # Get all progress data

# Status
GET  /api/jobs/{job_id}                 # Check translation/audio generation status
```

**Response Example**:
```json
{
  "book_id": "zarathustra_en_20250102",
  "title": "Thus Spoke Zarathustra",
  "author": "Friedrich Nietzsche",
  "language": "Modern English",
  "duration_seconds": 3600,
  "file_size_mb": 48.5,
  "compression_ratio": 0.5,
  "chapters": [
    {"title": "Prologue", "start_time": 0},
    {"title": "Chapter 1", "start_time": 420}
  ],
  "cover_url": "/api/books/zarathustra_en_20250102/cover",
  "download_url": "/api/books/zarathustra_en_20250102/download"
}
```

---

### Alternative: Progressive Web App (PWA)

If you want to avoid app store submission initially:

**Pros**:
- No app store approval needed
- Instant updates
- Works on both iOS and Android
- Easier development (just enhanced web app)

**Cons**:
- iOS limitations: No background audio, limited storage
- Less reliable progress persistence
- Can't use native media controls as well
- Users need to "install" from browser

**Verdict**: PWA is good for **testing the concept**, but native app provides **significantly better UX** for audiobooks.

---

### Browser Download Option (Fallback)

Keep this as a simple alternative for users who don't want the app:

#### Option: Local Network File Transfer
**How it works**: Access web app from phone browser, download files

**Implementation**:
- Run Flask/FastAPI with `host='0.0.0.0'`
- Display QR code for mobile access
- Download audio files to phone's file system
- Use native audio apps (Apple Music, VLC, etc.)

**Pros**: Zero setup, works immediately
**Cons**: No progress tracking, manual file management

**Use case**: Quick testing or users who prefer their own audio apps

#### Option 2: Simple File Sharing via Syncthing
**How it works**: Syncthing creates peer-to-peer sync between devices without cloud storage.

**Implementation**:
- Install Syncthing on desktop and mobile device
- Set up shared folder pointing to `local_reader_data/audio/`
- Audiobooks automatically sync when both devices are online
- Syncthing handles versioning and partial transfers

**Pros**: Automatic sync, works across networks (including internet), open source
**Cons**: Requires installing Syncthing app, slightly more setup
**Security**: Encrypted peer-to-peer transfers

#### Option 3: Temporary Local HTTP Server
**How it works**: Generate a temporary local server just for file transfer.

**Implementation**:
- Add "Share to Phone" button that starts temporary HTTP server
- Generate unique, time-limited download link (expires in 24 hours)
- Display link as QR code and text
- Server auto-shuts down after download or timeout
- Use Python's built-in `http.server` or lightweight alternatives

**Pros**: On-demand, secure with expiring links, minimal setup
**Cons**: Manual process each time

**Code snippet**:
```python
# Temporary download endpoint with expiring token
from secrets import token_urlsafe
from datetime import datetime, timedelta

def create_download_token(book_id, expires_hours=24):
    token = token_urlsafe(32)
    expiry = datetime.now() + timedelta(hours=expires_hours)
    # Store in database: token -> (book_id, expiry)
    return token

@app.get("/mobile/download/{token}")
async def mobile_download(token: str):
    # Validate token, check expiry, serve file
    pass
```

#### Option 4: Local File Drop (USB/AirDrop Alternative)
**How it works**: Export audiobook to a standard location for easy manual transfer.

**Implementation**:
- Add "Prepare for Mobile" button
- Compress audiobook + metadata into single ZIP file
- Save to standard location (e.g., Desktop or Downloads)
- Use standard transfer methods:
  - **iOS**: AirDrop from Mac
  - **Android**: USB cable or native file sharing apps
  - **Any**: Email to yourself, save from desktop browser

**Pros**: Works offline, uses familiar transfer methods, no network required
**Cons**: Manual process, slower than network transfer

#### Option 5: Self-Hosted Lightweight "Cloud" (Advanced)
**How it works**: Run a minimal file server with public access (optional).

**Implementation**:
- Use Tailscale or ngrok to create secure tunnel to your local server
- Access web app from anywhere via secure URL
- No port forwarding or firewall configuration needed
- Download audiobooks remotely

**Pros**: Access from anywhere, still self-hosted, no data limits
**Cons**: Requires leaving computer running, slight complexity increase
**Security**: Tailscale provides encrypted mesh network

**Services**:
- **Tailscale**: Free tier, creates private network, easiest setup
- **ngrok**: Free tier, temporary public URLs, great for testing
- **Cloudflare Tunnel**: Free, permanent URLs, more setup

---

---

## Roadmap

### MVP (Desktop Server Only)
**Goal**: Prove the concept with desktop web interface

- [ ] Web interface for book selection and configuration
- [ ] Full translation using Ollama (zongwei/gemma3-translator:1b)
- [ ] Basic compression (fixed ratio: 50%)
- [ ] Audio generation using OpenAI Whisper (temporary)
- [ ] Single-file audio download via browser
- [ ] Basic API endpoints for future mobile app

**Deliverable**: Desktop user can translate and compress books, download audiobooks to computer

---

### V1.0 (Mobile App Integration)
**Goal**: Build companion mobile app with full audiobook features

#### Desktop Server Updates:
- [ ] Complete REST API implementation (library, downloads, progress)
- [ ] Add mDNS/Bonjour for auto-discovery
- [ ] Implement API authentication (token or PIN)
- [ ] Add metadata extraction (cover art, chapters, duration)
- [ ] Streaming download endpoint for large files

#### Mobile App (React Native):
- [ ] Server discovery and connection
- [ ] Book library browsing
- [ ] Download manager with progress tracking
- [ ] Full-featured audio player (play/pause, seek, speed control)
- [ ] Progress persistence (resume from last position)
- [ ] Lock screen controls and background playback
- [ ] Offline library management

**Deliverable**: Users can generate books on desktop, auto-discover server on phone, download and listen with full progress tracking

---

### V1.5 (Local TTS)
**Goal**: Remove dependency on OpenAI API

- [ ] Replace OpenAI Whisper with Orpheus-3B TTS (GGUF)
- [ ] Benchmark TTS generation speed
- [ ] Optimize TTS quality and pronunciation
- [ ] Add voice customization options (if supported by model)

**Deliverable**: Fully local system with no external API dependencies

---

### V2.0 (Enhanced Features)
**Goal**: Polish UX and add advanced capabilities

#### Desktop:
- [ ] Adjustable compression ratios (10%-90%)
- [ ] Multiple compression strategies (smart summarization, chapter selection, hybrid)
- [ ] Support for user-uploaded books (EPUB, PDF)
- [ ] Upgrade to 4b translation model option
- [ ] Multi-language UI

#### Mobile App:
- [ ] Sleep timer (15/30/60 min presets)
- [ ] Bookmarks with notes
- [ ] Chapter navigation
- [ ] CarPlay and Android Auto support
- [ ] Cross-device progress sync
- [ ] Dark mode and themes
- [ ] Export to various ebook formats

**Deliverable**: Production-ready app with Audible-like features, fully self-hosted

---

### V3.0 (Future Ideas)
- [ ] Multi-user support (family accounts)
- [ ] Book recommendations based on reading history
- [ ] Community sharing of compression strategies
- [ ] Support for podcasts and articles
- [ ] Text-to-speech voices trained on specific narrators
- [ ] Integration with calibre for ebook management

---

## Performance Benchmarks (To Be Measured)

| Book Length | Translation Time | Compression Time | Audio Generation | Total Time |
|-------------|------------------|------------------|------------------|------------|
| 50k words   | TBD              | TBD              | TBD              | TBD        |
| 100k words  | TBD              | TBD              | TBD              | TBD        |
| 200k words  | TBD              | TBD              | TBD              | TBD        |

*Benchmarks will be measured on reference hardware (to be specified)*

---

## Contributing

This is a sub-project of the modernclassics repository. Development should maintain compatibility with existing translation and audio generation scripts where possible.

### Design Principles
1. **Local-first**: Minimize external dependencies
2. **User control**: Transparent process with ability to adjust at each step
3. **Reusability**: Leverage existing modernclassics code where applicable
4. **Extensibility**: Design for future model upgrades and feature additions

---

## License

Same as parent modernclassics project.

---

## Notes

- This README represents the planning phase. Implementation details will be refined during development.
- Hardware requirements will be documented after initial benchmarking.
- Model selection (1b vs 4b) may change based on performance testing.
- The two-step workflow (translate → compress) is a key architectural decision that enables flexibility.
