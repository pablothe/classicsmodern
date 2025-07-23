# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**modernclassics** is a Python-based system for translating classic literature into modern languages and generating audiobooks using AI. The project processes century-old books through various AI models while preserving Markdown structure and meaning.

## Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
# Create .env file with:
OPENAI_API_KEY=your_api_key_here
```

## Core Commands

### Text Translation
```bash
# List available AI models
python translator.py --list-models

# Translate with default model (o3-mini-high recommended)
python translator.py books/alice_adventures/alices_adventures.md

# Specify model and languages
python translator.py input.md --model o3-mini-high --source-lang German --target-lang "Modern English"

# Custom output directory
python translator.py input.md --output-dir custom_output/
```

### Audio Generation
```bash
# List available voices
python audio_translator.py --list-voices

# Generate multi-part audiobook (recommended)
python audio_translator.py books/alice_adventures/alices_adventures.md --voice fable

# Single file audio (experimental, may hit API limits)
python audio_translator.py input.md --voice alloy --single-file --format mp3
```

### Book Processing Utilities
```bash
# Extract from Project Gutenberg
python gutenberg_extractor.py

# Convert EPUB to Markdown
python epub_to_md.py input.epub
```

## Architecture

### Translation System
- **Multi-Model Support**: Supports o1-mini, o1-preview, o3-mini, o3-mini-high, gpt-4o-mini
- **Smart Chunking**: Respects Markdown structure, ~250 words per chunk
- **Structure Preservation**: Maintains headers, links, tables, and formatting through translation
- **Auto-Organization**: Automatically places outputs in appropriate `books/[book_name]/` directories

### Audio Generation System  
- **Text Cleaning**: Removes Markdown formatting for natural speech
- **Voice Options**: 6 voices (alloy, echo, fable, onyx, nova, shimmer)
- **Smart Chunking**: Breaks at natural boundaries (~4000 chars), creates playlists
- **Format Support**: wav, mp3, flac with automatic playlist generation

### File Organization Pattern
```
books/
├── [book_name]/
│   ├── [original].md
│   ├── [book]_[language]_[date]_[model].md     # Translations
│   ├── [book]_part001_[voice]_[date].wav       # Audio parts
│   └── [book]_audiobook_playlist_[date].m3u    # Playlist
```

## Key Implementation Details

### Model-Specific Handling
- **O1 models**: Don't support system messages, use combined prompts
- **O3 models**: Support temperature and system messages
- **GPT models**: Standard chat completion format

### Translation Quality Features
- Markdown structure analysis and preservation
- Table of contents link ID maintenance  
- Code block and table structure retention
- Automatic post-processing cleanup and verification

### Audio Processing
- Project Gutenberg header/footer removal
- Sentence-boundary splitting for natural pauses
- Playlist creation for sequential playbook playback
- Automatic book directory detection and organization

## Development Notes

### Current Architecture Limitations
- Audio generation may hit API limits with very long texts (use multi-part)
- O1/O3 model parameters differ from standard GPT models
- Chunking strategy optimized for translation quality over speed

### File Naming Conventions
- Translations: `[original_name]_[target_language]_[YYYYMMDD]_[model].md`
- Audio: `[book]_part[XXX]_[voice]_[timestamp].[format]`
- Original files preserved with `_original.md` suffix when copied to book directories

### Legacy Scripts
Multiple translator variants exist (`translator_o1_mini.py`, `translator_o3_mini_high.py`, etc.) but `translator.py` consolidates all functionality. Legacy scripts maintained for backward compatibility.