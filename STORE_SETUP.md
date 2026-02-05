# Store Setup Guide

The audiobook player now has a unified Library + Store interface!

## Features

- **Library Tab**: Your downloaded audiobooks with cover art and full playback
- **Store Tab**: Browse 500+ books from Project Gutenberg (no cover images until downloaded)
- **Unified Search**: Search across both Library and Store simultaneously
- **One-Click Download**: Click "Download" button to fetch books from Gutenberg

## Setup Instructions

### 1. Build the Gutenberg Catalog (One-Time)

The Store feature requires a pre-indexed catalog of Gutenberg books:

```bash
cd /Users/pabloeder/classicsmodern/classicsmodern

# Build catalog (scrapes top 500 books from Gutenberg)
python3 server/gutenberg_catalog.py --build
```

This will:
- Fetch the top 500 most popular books from Project Gutenberg
- Save catalog to `server/gutenberg_catalog.json`
- Take ~2-3 minutes to complete

### 2. Start the Server

```bash
python3 server/audiobook_server.py --host 0.0.0.0 --port 8000
```

Visit http://localhost:8000 in your browser.

### 3. Using the Store

**Search**:
- Type in the search bar to filter both Library and Store results
- Use tabs to switch between "All", "Library", and "Store" views

**Download a Book**:
1. Search for a book in the Store
2. Click the "📥 Download" button
3. Wait for download to complete (shows in status panel)
4. Book is saved to `books/{book_slug}/source.md`

**Generate Audiobook**:
After downloading a book from the Store, generate audio:

```bash
python3 make_audiobook.py books/{book_slug}/source.md --voice bf_emma --generate-cover
```

The book will then appear in your Library with full playback support!

## UI/UX Details

### Library Books
- ✅ Cover images (if generated)
- ✅ Full metadata (title, author, year)
- ✅ Multiple variants (full, summary, deduped)
- ✅ Instant playback

### Store Books
- 📚 Placeholder icon (no cover image)
- ✅ Book metadata (title, author, language, download count)
- ⬇️ "Download" button
- ⚠️ No playback until downloaded and processed

### Search Behavior
- **All Tab**: Shows both Library and Store results
- **Library Tab**: Shows only downloaded books
- **Store Tab**: Shows only Gutenberg catalog
- Real-time filtering as you type

## Refreshing the Catalog

To update the catalog (e.g., new Gutenberg rankings):

```bash
python3 server/gutenberg_catalog.py --refresh
```

## Statistics

View catalog stats:

```bash
python3 server/gutenberg_catalog.py --stats
```

Shows:
- Total books in catalog
- Languages available
- Top authors
- Last updated timestamp

---

**That's it!** You now have a unified Library + Store for discovering and downloading classic literature. 📚
