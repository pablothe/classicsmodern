# Modern Classics — Project Todo

Updated Feb 25, 2026. Cross-referenced against uncommitted changes + git history.

---

## Completed

- [x] Remove "Failed" badge from book covers (`e4a2120`)
- [x] Thread user_language through AI chat (`77a090b`)
- [x] Delete test book directories (`8a6ed18`)
- [x] Remove all cloud/external API dependencies (`c2af29b`)
- [x] Fix lib/ package tracking in git (`48a05df`)
- [x] Chapter detection: 3-step priority chain (`a3db240`)
- [x] Chapter detection: metadata-first approach (`a3db240`)
- [x] Fix missing generate_image function (`ede34bf`)
- [x] Deduplicate overlapping chapter detections (`b961b89`)
- [x] Strip "end chapter" artifacts from Gutenberg HTML (`ca37347`)
- [x] Add markdown_roman_title chapter pattern (`a3db240`)
- [x] Fix War of the Worlds chapter detection (`a3db240`)
- [x] B&W minimalist redesign + dark mode toggle (`48a05df`)
- [x] Smoke test suite (`48a05df`)
- [x] Gutenberg language metadata as source of truth (`b1707a6`)
- [x] AI chat responds in user's language (`77a090b`)
- [x] Audiobook pipeline audit + commit (`639bb25`)
- [x] Chapter detection audit + commit (`639bb25`)
- [x] Cover generation as job type with progress tracking (`48a05df`)
- [x] Text sync: fix 5-bug chain (paragraph mapping, seek, global position)
- [x] Netflix-style language track selection — text + audio language switching

### Phase 1: Full-Featured Reader Mode (uncommitted)
- [x] Fullscreen reader overlay with continuous scroll across chapters
- [x] Font size, font family, line height, theme (light/sepia/dark) controls
- [x] Floating mini audio player at bottom of reader
- [x] Lazy chapter loading via IntersectionObserver
- [x] Scroll position + preference persistence in localStorage
- [x] Karaoke integration in reader (paragraph-level sync; word-level not in reader)

### Phase 2: Bug Fixes (uncommitted)
- [x] `book_health.py`: Save auto-recovered chapter metadata to disk
- [x] `audiobook_server.py`: Add `number` field to chunk manifest fallback chapters
- [x] `llm_chat.py`: Defensive `.get()` for chapter fields
- [x] `player.js`: Truncate error messages in variant view (80 char max)
- [x] `player.js`: Only badge running/pending jobs on library cards
- [x] `player.js`: Fix delete button with `e.target.closest()`
- [x] `audiobook_server.py`: Import alias to avoid `create_download_job` shadowing

### Phase 3: Text Sync Quality (uncommitted — paragraph ID refactor)
- [x] Wire up KaraokeSync class in player.js
- [x] Fix scroll jitter: only update DOM + scroll when paragraph changes
- [x] Unify chapter detection between text_extractor.py and word_timings.py
- [x] Use chunk manifest data for paragraph sync instead of linear interpolation
- [x] Optimize highlightWord() from O(n) to O(1) via direct array refs
- [x] Fix source-text vs spoken-text mismatch in paragraph sync
- [x] Fix text_pos drift in word_timings.py
- [x] Lower paragraph filter threshold from 10 to 2 chars
- [x] Fix binary search gap handling in findWordAtTime
- [x] Karaoke toggle uses CSS class instead of inline display:none

### Phase 4: Queue Tab UI (uncommitted)
- [x] Add "Queue" tab alongside "Library" and "Store" with active-job count badge
- [x] Move jobs-activity panel content into Queue tab section
- [x] Remove "Jobs" header link (Queue tab replaces it)
- [x] Hide search input when Queue tab active
- [x] Refactor `jobsActivity` object to render in new tab section
- [x] Show empty state when no jobs

### Phase 5: Pipeline Reliability (uncommitted)
- [x] Single chunk failure handling: retry 3x then skip with silence placeholder
- [x] ffmpeg combine failure: retry with concat demuxer before falling back
- [x] Pipeline-level retry: retry subprocess up to 3x for transient failures
- [x] Chunk-level checkpointing (save every 10 chunks, resume on restart)
- [x] Chapter sequence renumber warnings (visible, not verbose-only)
- [x] Subprocess environment: explicitly set venv PATH
- [x] Progress regex: use more specific matching
- [x] Concurrent generation: file lock on output directory
- [x] TTS chunk timeout (120s per chunk)
- [x] Error classification: permanent vs transient failures

### Paragraph ID Architecture (uncommitted — cross-cutting)
- [x] Manifest v3.0 with paragraph extraction (`lib/book/processor.py`)
- [x] Paragraph-by-paragraph translation (`lib/translation/structured.py`)
- [x] Paragraph boundary tracking in audio chunks (`lib/audio/kokoro.py`)
- [x] Word-to-paragraph mapping in timings (`lib/audio/word_timings.py`)
- [x] Paragraph timing API endpoint (`server/audiobook_server.py`)
- [x] Manifest-aware paragraph IDs in text extraction (`server/text_extractor.py`)
- [x] Paragraph timing UI in player.js + reader.js
- [x] Batch migration tool (`validate.py --migrate-paragraphs`)

---

## Backlog

### Phase 6: Multi-User Profiles
> Plan: `wondrous-hugging-moonbeam`
> **Independent** — no dependencies on other phases

- [x] Server: users_db.json data model + CRUD API endpoints (`/api/users`)
- [x] Server: Modify playback endpoints to accept `X-User-ID` header
- [x] UI: "Who's listening?" profile picker overlay
- [x] UI: Emoji avatar selection grid
- [x] UI: Top-right user menu (replaces gear+moon buttons)
- [x] Per-user settings: language prefs + dark mode stored server-side
- [x] Migration: copy device playback data to first user profile

**Files:** `server/audiobook_server.py`, `server/static/player.html`, `server/static/player.js`, `server/static/player.css`

---

### Phase 7: Documentation Polish
> Plan: `wiggly-wobbling-zebra`
> **Independent** — no dependencies, but best done last
> Can run in parallel with Phase 6

- [x] Fix port 8080 -> 8000 in make_audiobook.py (already fixed)
- [x] CLAUDE.md: Add missing server files (`users_db.py`) to project structure
- [x] CLAUDE.md: Add user API endpoints + fix parameter names (`{idx}`→`{file_index}`, `{id}`→`{job_id}`)
- [x] CLAUDE.md: Document undocumented CLI flags (audited — all flags already documented)
- [x] CLAUDE.md: Clarify default voice difference (already documented correctly)
- [x] CLAUDE.md: Document paragraph timing API + manifest v3.0 (already documented)
- [x] README.md: Fix `ollama:` prefix on model name
- [x] CHANGELOG.md: Add deprecation notice for pre-v3 manifest format

**Files:** `CLAUDE.md`, `README.md`, `CHANGELOG.md`

---

### Word-Level Karaoke in Reader (optional enhancement)
> Low priority — paragraph-level sync already works well
> **Independent** — only touches reader.js + karaoke.js

- [ ] Render word timing spans inside reader paragraphs
- [ ] Highlight words during playback (reuse KaraokeSync from karaoke.js)
- [ ] Auto-scroll to current word within active paragraph

**Files:** `server/static/reader.js`, `server/static/karaoke.js`

---

## Future Roadmap (from CHANGELOG)

### V1.0 — Q1 2026
- [ ] Mobile app (React Native)
- [ ] Server auto-discovery
- [ ] Full audiobook player (mobile)
- [ ] Background playback
- [ ] Lock screen controls

### V1.5 — Q2 2026
- [ ] Enhanced local TTS (Orpheus-3B)
- [ ] Voice customization
- [ ] Faster generation speeds

### V2.0 — Q3 2026
- [ ] Book compression/summarization
- [ ] Adjustable compression ratios
- [ ] Multi-user support (cross-device)
- [ ] CarPlay/Android Auto
- [ ] Cross-device sync
