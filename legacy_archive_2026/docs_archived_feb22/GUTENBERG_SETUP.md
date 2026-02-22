# Gutenberg Book Browser - Setup Guide

Complete setup and usage instructions for the new Gutenberg book browser feature.

## Overview

The Gutenberg book browser lets you search and download books from Project Gutenberg's top 500 directly from your mobile web player.

## Setup Instructions

### 1. Build the Gutenberg Catalog (One-Time)

The catalog is a JSON file containing metadata for 500 popular books from Project Gutenberg.

```bash
# Navigate to project directory
cd /Users/pabloeder/classicsmodern/classicsmodern

# Build catalog (takes 1-2 minutes)
python3 server/gutenberg_catalog.py --build
```

**Output:**
```
📚 Building Gutenberg catalog (top 500 books)...
======================================================================
Fetching: https://www.gutenberg.org/browse/scores/top
Found 500 books

  [ 10/500] Pride and Prejudice by Jane Austen
  [ 20/500] A Christmas Carol by Charles Dickens
  ...
✓ Cataloged 500 books
✓ Catalog saved: server/gutenberg_catalog.json
```

### 2. Install Dependencies (If Not Already Installed)

```bash
pip install requests beautifulsoup4
```

### 3. Start the Server

```bash
python3 server/audiobook_server.py
```

**Expected output:**
```
============================================================
Audiobook Server Starting...
============================================================
Books directory: /Users/pabloeder/classicsmodern/classicsmodern/books
Found 3 books
Server: http://0.0.0.0:8000
API Docs: http://localhost:8000/docs
✓ Gutenberg browser available (500 books in catalog)
============================================================
```

## Usage - Mobile Workflow

### 1. Open Web Player

- Open Safari on your iPhone
- Navigate to: `http://YOUR_LOCAL_IP:8000`
- (Find your IP with `ifconfig | grep inet`)

### 2. Browse Gutenberg Books

1. In the library view, tap **"+ Browse Books"** button
2. You'll see the Gutenberg search view with top 500 books
3. Use the search bar to find books:
   - Search by title: "alice", "pride", "sherlock"
   - Search by author: "austen", "dickens", "kafka"
4. Filter by language using the dropdown:
   - All Languages
   - English
   - French
   - German
   - Spanish
   - Russian
   - Italian

### 3. Download a Book

1. Find the book you want (e.g., "Pride and Prejudice")
2. Tap **"📥 Download"** button
3. A download status panel appears at bottom-right
4. Progress updates in real-time:
   - Pending... (0%)
   - Downloading... (40%)
   - Processing... (60%)
   - Complete (100%)
5. Success notification: "✅ Pride and Prejudice downloaded!"

### 4. Process the Downloaded Book

The book is now saved to `books/{book_slug}/source.md`. To create an audiobook:

```bash
# SSH into your Mac (or use Terminal)
cd /Users/pabloeder/classicsmodern/classicsmodern

# Generate audiobook with cover art
python3 make_audiobook.py books/pride_prejudice/source.md --voice bf_emma --generate-cover

# Wait ~10-30 minutes for processing
# The book will appear in the web player when complete!
```

## Command-Line Tools

### Build/Refresh Catalog

```bash
# Build catalog (first time)
python3 server/gutenberg_catalog.py --build

# Refresh catalog (update with latest top 500)
python3 server/gutenberg_catalog.py --refresh
```

### Search Catalog (CLI)

```bash
# Search for books
python3 server/gutenberg_catalog.py --search "alice"

# Filter by language
python3 server/gutenberg_catalog.py --search "kafka" --language de

# Show statistics
python3 server/gutenberg_catalog.py --stats
```

### Download Book (CLI)

```bash
# Download by Gutenberg ID
python3 server/gutenberg_downloader.py 11 alice_adventures

# Output:
# 📥 Downloading Gutenberg #11...
# 🔄 Converting to Markdown...
# ✂️  Stripping Gutenberg boilerplate...
# ✅ Validating structure...
# 🎉 Download complete!
```

## API Endpoints

The Gutenberg browser adds these REST API endpoints:

### GET /api/gutenberg/catalog
Get full catalog (500 books)

```bash
curl http://localhost:8000/api/gutenberg/catalog
```

### GET /api/gutenberg/search?q=alice&language=en
Search with filters

```bash
curl "http://localhost:8000/api/gutenberg/search?q=alice&language=en"
```

### POST /api/gutenberg/download
Start download

```bash
curl -X POST http://localhost:8000/api/gutenberg/download \
  -H "Content-Type: application/json" \
  -d '{"gutenberg_id": 11, "book_slug": "alice_adventures"}'
```

### GET /api/gutenberg/downloads/{job_id}
Check download status

```bash
curl http://localhost:8000/api/gutenberg/downloads/abc123
```

### GET /api/gutenberg/downloads
List all downloads

```bash
curl http://localhost:8000/api/gutenberg/downloads
```

## Features

### Concurrent Downloads
- Max 3 simultaneous downloads
- Prevents server overload
- Queue system with background workers

### Auto-Validation
- Strips Project Gutenberg boilerplate
- Validates chapter structure
- Provides word count and metadata

### Resume Support
- Download jobs tracked in memory
- Poll for status updates every 2 seconds
- Graceful error handling

### Mobile-Optimized UI
- Responsive grid (1 column on phone, 3 on desktop)
- Touch-friendly buttons (min 44px)
- Real-time progress updates
- Floating download status panel

## Catalog Structure

The catalog is stored in `server/gutenberg_catalog.json`:

```json
{
  "books": [
    {
      "gutenberg_id": 11,
      "title": "Alice's Adventures in Wonderland",
      "author": "Lewis Carroll",
      "language": "en",
      "year": 1865,
      "downloads": 38450,
      "url": "https://www.gutenberg.org/ebooks/11"
    },
    ...
  ],
  "total": 500,
  "updated_at": "2026-02-03T10:30:00Z"
}
```

## File Organization

Downloaded books follow the standard structure:

```
books/
├── pride_prejudice/
│   ├── source.md                    # Downloaded text (cleaned)
│   ├── audio_kokoro/                # Generated after make_audiobook.py
│   │   ├── chapter_01.mp3
│   │   ├── chapter_02.mp3
│   │   ├── audiobook.m3u
│   │   └── pride_prejudice_cover.png
│   └── pride_prejudice_chapter_data.json
```

## Troubleshooting

### "Catalog not found" error
```bash
# Build the catalog first
python3 server/gutenberg_catalog.py --build
```

### "Failed to fetch Gutenberg catalog" in web player
- Check server logs for errors
- Restart server: `python3 server/audiobook_server.py`
- Verify catalog exists: `ls server/gutenberg_catalog.json`

### Download stuck at "Pending..."
- Check server logs for errors
- Max 3 concurrent downloads - wait for others to finish
- Restart server if needed

### Book downloaded but not showing in library
- The book is just the source text - you need to generate audio:
  ```bash
  python3 make_audiobook.py books/{book_slug}/source.md --generate-cover
  ```

### Network errors during download
- Project Gutenberg may be temporarily unavailable
- Retry after a few minutes
- Check internet connection

## Performance

### Catalog Build
- Time: 1-2 minutes (one-time)
- Network requests: ~500 (polite delays)
- Catalog size: ~2MB JSON

### Book Download
- Time: 5-30 seconds (depends on book size)
- Network: 1 HTTP request (HTML format preferred)
- Processing: HTML→Markdown, boilerplate stripping, validation

### Audiobook Generation
- Time: 10-60 minutes (depends on book length)
- CPU: High (TTS processing)
- Storage: ~1MB per minute of audio

## Next Steps

After downloading a book, you can:

1. **Generate audiobook** (recommended):
   ```bash
   python3 make_audiobook.py books/{slug}/source.md --voice bf_emma --generate-cover
   ```

2. **Translate first** (for non-English books):
   ```bash
   # See GUIDE.md for translation workflow
   python3 translator.py books/{slug}/source.md --model o3-mini-high
   ```

3. **Summarize first** (for long books):
   ```bash
   python3 book_summarizer.py books/{slug}/source.md 50
   ```

## Advanced Usage

### Automated Workflow

Create a script to download and process books automatically:

```bash
#!/bin/bash
# download_and_process.sh

BOOK_ID=$1
BOOK_SLUG=$2
VOICE=${3:-bf_emma}

# Download
python3 server/gutenberg_downloader.py $BOOK_ID $BOOK_SLUG

# Generate audiobook
python3 make_audiobook.py books/$BOOK_SLUG/source.md \
  --voice $VOICE \
  --generate-cover

echo "✅ Complete! Book available in web player."
```

Usage:
```bash
chmod +x download_and_process.sh
./download_and_process.sh 11 alice_adventures bf_emma
```

### Batch Processing

Download multiple books:

```bash
# Create list of books
cat > books_to_download.txt << EOF
11 alice_adventures
1342 pride_prejudice
84 frankenstein
98 tale_two_cities
EOF

# Process each
while read id slug; do
  python3 server/gutenberg_downloader.py $id $slug
done < books_to_download.txt
```

## Support

For issues or questions:
- Check server logs: Look for `[Gutenberg]` or `[Download]` messages
- Test API directly: Use `/api/gutenberg/` endpoints with curl
- Rebuild catalog: `python3 server/gutenberg_catalog.py --refresh`

## See Also

- [README.md](README.md) - Project overview
- [GUIDE.md](GUIDE.md) - Complete audiobook workflow
- [CLAUDE.md](CLAUDE.md) - Technical reference
