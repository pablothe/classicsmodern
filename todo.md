# Modern Classics — Project Todo

Audited Feb 24, 2026. Cross-referenced 30 plan files against git history.

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
- [x] Text sync: fix 5-bug chain (paragraph mapping, seek, global position) (implemented)
- [x] Netflix-style language track selection — text + audio language switching

---

## In Progress

### Phase 1: Full-Featured Reader Mode
> Plan: `zesty-swimming-corbato` — reader.js in progress

- [ ] Fullscreen reader overlay with continuous scroll across chapters
- [ ] Font size, font family, line height, theme (light/sepia/dark) controls
- [ ] Floating mini audio player at bottom of reader
- [ ] Lazy chapter loading via IntersectionObserver
- [ ] Scroll position + preference persistence in localStorage
- [ ] Karaoke integration in reader

**Files:** `server/static/reader.js` (new), `player.html`, `player.css`, `player.js`

---

## Backlog (dependency-ordered)

### Phase 2: Bug Fixes

**2a. Dr Jekyll & Hyde bug cascade** — `polymorphic-greeting-puppy`
- [ ] `book_health.py`: Save auto-recovered chapter metadata to disk (currently discarded)
- [ ] `audiobook_server.py`: Add `number` field to chunk manifest fallback chapters
- [ ] `llm_chat.py`: Defensive `.get()` for chapter fields (prevents KeyError)
- [ ] Fix `source.md` malformed TOC line, then regenerate audiobook

**2b. Error message cleanup** — `toasty-coalescing-engelbart`
- [ ] `player.js`: Replace full error dumps in variant view with brief "Check Jobs panel" message
- [ ] `player.js`: Remove truncated error text from library card badges

**2c. Job Queue remaining fixes** — `wise-toasting-moth` (toast notifications already done)
- [ ] `player.js`: Fix delete button (use `e.target.closest()` instead of `e.target.classList`)
- [ ] `audiobook_server.py`: Rename `create_download_job` endpoint function to avoid shadowing import

---

### Phase 3: Text Sync Quality
> Plan: `lucky-watching-feigenbaum` — 10 bugs across 5 files
>
> Depends on: Reader mode (Phase 1) benefits from these fixes

- [ ] Wire up KaraokeSync class in player.js (currently dead code, toggle hidden)
- [ ] Fix scroll jitter: only update DOM + scroll when paragraph changes
- [ ] Unify chapter detection between text_extractor.py and generate_word_timings.py
- [ ] Use chunk manifest data for paragraph sync instead of linear interpolation
- [ ] Optimize highlightWord() from O(n) to O(1)
- [ ] Fix source-text vs spoken-text mismatch in paragraph sync
- [ ] Fix text_pos drift in generate_word_timings.py
- [ ] Lower paragraph filter threshold from 10 to 2 chars
- [ ] Fix binary search gap handling in findWordAtTime
- [ ] Remove inline `display: none` from karaoke toggle (use CSS class instead)

**Files:** `player.js`, `player.html`, `karaoke.js`, `text_extractor.py`, `generate_word_timings.py`

---

### Phase 4: UI Improvements

**Queue Tab** — `bright-noodling-seal`
> Depends on: Phase 2c (job queue fixes)

- [ ] Add "Queue" tab alongside "Library" and "Store" with active-job count badge
- [ ] Move floating jobs-activity panel content into Queue tab section
- [ ] Remove "Jobs" header link (Queue tab replaces it)
- [ ] Hide search input when Queue tab active
- [ ] Refactor `jobsActivity` object to render in new tab section
- [ ] Show empty state when no jobs

**Files:** `player.html`, `player.js`, `player.css`

---

### Phase 5: Pipeline Reliability
> Plan: `toasty-prancing-cocoa` — 14 bugs identified
>
> **Note:** Many file references are outdated (pre-refactor into lib/). Needs re-audit against current codebase.

- [ ] Re-audit: map old file references to current lib/ paths
- [ ] Single chunk failure handling: retry 3x then skip with silence placeholder
- [ ] ffmpeg combine failure: retry with concat demuxer before falling back
- [ ] Chapter-level retry for failed chapters
- [ ] Chunk-level checkpointing (save every 10 chunks, resume on restart)
- [ ] Chapter sequence renumber warnings (visible, not verbose-only)
- [ ] Subprocess environment: explicitly set venv PATH
- [ ] Progress regex: use more specific matching
- [ ] Concurrent generation: file lock on output directory
- [ ] TTS chunk timeout (120s per chunk)

**Files:** `lib/audio/kokoro.py`, `lib/book/processor.py`, `lib/book/validator.py`, `server/audiobook_pipeline.py`

---

### Phase 6: Features

**Multi-User Profiles** — `wondrous-hugging-moonbeam`

- [ ] Server: users_db.json data model + CRUD API endpoints (`/api/users`)
- [ ] Server: Modify playback endpoints to accept `X-User-ID` header
- [ ] UI: "Who's listening?" profile picker overlay
- [ ] UI: Emoji avatar selection grid
- [ ] UI: Top-right user menu (replaces gear+moon buttons)
- [ ] Per-user settings: language prefs + dark mode stored server-side
- [ ] Migration: copy device playback data to first user profile

**Files:** `audiobook_server.py`, `player.html`, `player.js`, `player.css`

---

### Phase 7: Polish

**Documentation Update** — `wiggly-wobbling-zebra`
> Do last — after all changes settle

- [ ] Fix port 8080 → 8000 in make_audiobook.py
- [ ] CLAUDE.md: Add missing server files + static directory to project structure
- [ ] CLAUDE.md: Expand API endpoints from 7 to full 32+ set
- [ ] CLAUDE.md: Document undocumented CLI flags
- [ ] CLAUDE.md: Clarify default voice difference (make_audiobook=bf_emma, audiobook=af_sky)
- [ ] README.md: Add `zongwei/` namespace prefix to model names
- [ ] CHANGELOG.md: Add deprecation notice for pre-v3 file references

**Files:** `make_audiobook.py`, `CLAUDE.md`, `README.md`, `CHANGELOG.md`

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
