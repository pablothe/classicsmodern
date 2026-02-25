#!/usr/bin/env python3
"""
Generate Word-Level Timing Data for Karaoke Sync

This script uses Whisper for forced alignment to create precise word-level
timestamps that map audio positions to text positions. This enables:
- Karaoke-style word highlighting during playback
- Resume playback at exact word positions
- Click-to-seek from text to audio

Methods supported:
1. WhisperX (recommended) - Fast, accurate, word-level timestamps
2. Whisper.cpp - Lightweight alternative
3. Fallback: Uniform distribution (less accurate but always works)

Usage:
    # Generate word timings for a complete audiobook
    python generate_word_timings.py books/call_cthulhu/audio_kokoro/The_CALL_of_CTHULHU_audiobook.m3u

    # Use specific text source
    python generate_word_timings.py playlist.m3u --text books/call_cthulhu/call_cthulhu.md

Output:
    books/call_cthulhu/call_cthulhu_word_timings.json
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import tempfile


def check_whisperx_available() -> bool:
    """Check if WhisperX is installed and available"""
    try:
        import whisperx
        return True
    except ImportError:
        return False


def check_whisper_cpp_available() -> bool:
    """Check if whisper.cpp is installed"""
    try:
        result = subprocess.run(
            ['whisper-cpp', '--version'],
            capture_output=True,
            timeout=2
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_audio_duration(audio_path: Path) -> Optional[float]:
    """Get audio file duration in seconds using ffprobe"""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-show_entries',
             'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
             str(audio_path)],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode == 0 and result.stdout.strip():
            return float(result.stdout.strip())
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        pass

    return None


def parse_m3u_playlist(playlist_path: Path) -> List[Path]:
    """Parse M3U playlist and return audio file paths"""
    audio_files = []
    playlist_dir = playlist_path.parent

    with open(playlist_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            # Resolve relative path
            audio_path = playlist_dir / line
            if audio_path.exists():
                audio_files.append(audio_path)
            else:
                print(f"⚠️  Warning: Audio file not found: {line}")

    return audio_files


def detect_chapter_from_filename(filename: str) -> Optional[int]:
    """Detect chapter number from audio filename"""
    patterns = [
        r'chapter[_-]?(\d+)',
        r'ch[_-]?(\d+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def extract_chapter_text(source_text: str, chapter_num: int, total_chapters: int) -> Tuple[str, int]:
    """
    Extract text for a specific chapter from source markdown.

    Uses text_extractor.detect_chapter_markers() for consistent chapter detection
    across the entire system (same patterns as the web server text sync API).

    Args:
        source_text: Full book text
        chapter_num: Chapter number to extract (1-based)
        total_chapters: Total number of chapters

    Returns:
        Tuple of (chapter_text, start_char_position)
    """
    try:
        from server.text_extractor import detect_chapter_markers, extract_chapter_text as _extract
    except ImportError:
        # Fallback: try importing from project root
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "text_extractor",
            Path(__file__).parent / "server" / "text_extractor.py"
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        detect_chapter_markers = mod.detect_chapter_markers
        _extract = mod.extract_chapter_text

    chapters = detect_chapter_markers(source_text)

    if chapters and chapter_num <= len(chapters):
        # Convert 1-based chapter_num to 0-based index
        chapter_index = chapter_num - 1
        chapter_text = _extract(source_text, chapters, chapter_index)
        start_pos = chapters[chapter_index]['start_pos']
        if chapter_text:
            return chapter_text, start_pos

    # Fallback: split text evenly
    if total_chapters > 0:
        chunk_size = len(source_text) // total_chapters
        start_pos = (chapter_num - 1) * chunk_size
        end_pos = start_pos + chunk_size if chapter_num < total_chapters else len(source_text)
        return source_text[start_pos:end_pos], start_pos

    return source_text, 0


def generate_word_timings_whisperx(
    audio_path: Path,
    text: str,
    device: str = "cpu",
    language: str = "en"
) -> List[Dict]:
    """
    Generate word timings using WhisperX (recommended method).

    Args:
        audio_path: Path to audio file
        text: Expected text content
        device: Device to run on ("cpu", "cuda", "mps")
        language: Language code for alignment model (default: "en")

    Returns:
        List of word timing dictionaries
    """
    try:
        import whisperx
    except ImportError:
        raise ImportError("WhisperX not installed. Install with: pip install whisperx")

    print(f"  Using WhisperX for alignment (language: {language})...")

    # Load audio
    audio = whisperx.load_audio(str(audio_path))

    # Load model
    model = whisperx.load_model("base", device=device, compute_type="int8")

    # Transcribe
    result = model.transcribe(audio, batch_size=16)

    # Align with reference text
    model_a, metadata = whisperx.load_align_model(language_code=language, device=device)
    result = whisperx.align(
        result["segments"],
        model_a,
        metadata,
        audio,
        device,
        return_char_alignments=False
    )

    # Extract word timings
    word_timings = []
    for segment in result["segments"]:
        if "words" in segment:
            for word_data in segment["words"]:
                word_timings.append({
                    "word": word_data["word"].strip(),
                    "start": word_data["start"],
                    "end": word_data["end"]
                })

    return word_timings


def generate_word_timings_whisper_cpp(
    audio_path: Path,
    text: str
) -> List[Dict]:
    """
    Generate word timings using whisper.cpp (lightweight alternative).

    Args:
        audio_path: Path to audio file
        text: Expected text content

    Returns:
        List of word timing dictionaries
    """
    print(f"  Using whisper.cpp for alignment...")

    # Convert audio to 16kHz WAV if needed
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_wav:
        temp_path = Path(temp_wav.name)

    try:
        # Convert to whisper.cpp format (16kHz mono WAV)
        subprocess.run(
            ['ffmpeg', '-y', '-i', str(audio_path),
             '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le',
             str(temp_path)],
            capture_output=True,
            check=True
        )

        # Run whisper.cpp with word timestamps
        result = subprocess.run(
            ['whisper-cpp', '-m', 'models/ggml-base.en.bin',
             '-f', str(temp_path), '--output-json', '--max-len', '1'],
            capture_output=True,
            text=True,
            check=True
        )

        # Parse JSON output
        output_data = json.loads(result.stdout)

        word_timings = []
        for segment in output_data.get('transcription', []):
            for word_data in segment.get('words', []):
                word_timings.append({
                    "word": word_data['text'].strip(),
                    "start": word_data['start'],
                    "end": word_data['end']
                })

        return word_timings

    finally:
        # Cleanup temp file
        if temp_path.exists():
            temp_path.unlink()


def find_chunk_manifest(playlist_path: Path) -> Optional[Path]:
    """Find chunk manifest JSON in the same directory as the playlist"""
    audio_dir = playlist_path.parent
    manifests = list(audio_dir.glob("*_chunk_manifest.json"))
    return manifests[0] if manifests else None


def _find_para_id_for_offset(chunk_paras: list, char_offset: int) -> Optional[str]:
    """
    Look up which paragraph a character offset belongs to within a chunk.

    Args:
        chunk_paras: List of paragraph annotations from chunk manifest,
                     each with para_id, char_start_in_chunk, char_end_in_chunk
        char_offset: Character offset within the chunk

    Returns:
        para_id string or None if no paragraph data available
    """
    if not chunk_paras:
        return None
    for para in chunk_paras:
        if para['char_start_in_chunk'] <= char_offset < para['char_end_in_chunk']:
            return para['para_id']
    # If offset is past all paragraphs, return last one
    if chunk_paras:
        return chunk_paras[-1]['para_id']
    return None


def _build_paragraph_timings(words: list) -> list:
    """
    Build paragraph-level timing summaries from word-level para_id assignments.

    Groups consecutive words by para_id and computes audio start/end for each
    paragraph. This is the data structure the frontend uses for sync.

    Args:
        words: List of word dicts with 'para_id', 'start', 'end' fields

    Returns:
        List of paragraph timing dicts with para_id, audio_start, audio_end,
        word_start_idx, word_end_idx
    """
    if not words:
        return []

    paragraphs = []
    current_para_id = None
    para_start_time = 0.0
    para_start_idx = 0

    for i, word in enumerate(words):
        word_para = word.get('para_id')
        if word_para != current_para_id:
            # Close previous paragraph
            if current_para_id is not None:
                paragraphs.append({
                    "para_id": current_para_id,
                    "audio_start": round(para_start_time, 3),
                    "audio_end": round(words[i - 1]['end'], 3),
                    "word_start_idx": para_start_idx,
                    "word_end_idx": i - 1
                })
            # Start new paragraph
            current_para_id = word_para
            para_start_time = word['start']
            para_start_idx = i

    # Close last paragraph
    if current_para_id is not None and words:
        paragraphs.append({
            "para_id": current_para_id,
            "audio_start": round(para_start_time, 3),
            "audio_end": round(words[-1]['end'], 3),
            "word_start_idx": para_start_idx,
            "word_end_idx": len(words) - 1
        })

    return paragraphs


def generate_word_timings_from_chunks(
    chunk_manifest_path: Path,
    playlist_path: Path
) -> Dict:
    """
    Generate word timings from the chunk manifest created during TTS generation.

    Since we know exactly which text chunks were sent to Kokoro and the duration
    of each chunk's audio, we can build accurate word timings by distributing
    words uniformly within each chunk's time window. This is much more accurate
    than distributing uniformly across an entire chapter.

    Args:
        chunk_manifest_path: Path to *_chunk_manifest.json
        playlist_path: Path to the chapter-level M3U playlist (for audio_file names)

    Returns:
        Dictionary with word timing data per chapter (same format as karaoke.js expects)
    """
    print(f"  Using chunk manifest method (per-chunk timing)...")

    # Load chunk manifest
    with open(chunk_manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    # Load clean text (saved alongside manifest during generation)
    clean_text_path = chunk_manifest_path.parent / chunk_manifest_path.name.replace(
        '_chunk_manifest.json', '_clean_text.txt'
    )
    if clean_text_path.exists():
        with open(clean_text_path, 'r', encoding='utf-8') as f:
            clean_text = f.read()
        print(f"  Loaded clean text: {len(clean_text):,} characters")
    else:
        # Fallback: try to read source markdown from the book directory
        book_dir = chunk_manifest_path.parent
        while book_dir.name in ['audio_xtts', 'audio_kokoro', 'audio_edge', 'audio']:
            book_dir = book_dir.parent
        md_files = list(book_dir.glob("*.md"))
        if md_files:
            with open(md_files[0], 'r', encoding='utf-8') as f:
                clean_text = f.read()
            print(f"  Note: Using source markdown as text reference (clean_text.txt not found)")
            print(f"  For best accuracy, regenerate the audiobook to create clean_text.txt")
        else:
            print(f"  Warning: No text source found, using truncated text_preview from manifest")
            clean_text = None

    # Parse the chapter-level playlist to get chapter audio filenames
    chapter_audio_files = parse_m3u_playlist(playlist_path)
    chapter_file_map = {}  # chapter_sequential_index -> (file_index, audio_filename)
    for i, audio_file in enumerate(chapter_audio_files):
        chapter_num = detect_chapter_from_filename(audio_file.name)
        if chapter_num:
            chapter_file_map[chapter_num] = (i, audio_file.name)

    # Group chunks by chapter
    chunks_by_chapter = {}
    for chunk in manifest['chunks']:
        ch = chunk['chapter']
        if ch not in chunks_by_chapter:
            chunks_by_chapter[ch] = []
        chunks_by_chapter[ch].append(chunk)

    # Build word timings per chapter
    word_timings_data = {}
    unique_chapters = sorted(chunks_by_chapter.keys())

    for seq_idx, chapter_num in enumerate(unique_chapters, 1):
        chapter_chunks = chunks_by_chapter[chapter_num]

        # Find this chapter's start time (cumulative_duration of first chunk)
        chapter_start_time = chapter_chunks[0]['cumulative_duration']

        # Get chapter audio file info from playlist
        if seq_idx in chapter_file_map:
            file_index, audio_filename = chapter_file_map[seq_idx]
        else:
            # Fallback: use sequential index
            file_index = seq_idx - 1
            audio_filename = f"chapter_{seq_idx:02d}.mp3"

        all_words = []
        chapter_duration = 0.0
        has_clean_text = (clean_text is not None and
                         clean_text_path.exists() and
                         chapter_chunks[-1]['text_end'] <= len(clean_text))

        if has_clean_text:
            # ACCURATE MODE: Use exact chunk text from clean_text.txt
            for chunk in chapter_chunks:
                chunk_start_in_chapter = chunk['cumulative_duration'] - chapter_start_time
                chunk_duration = chunk['duration']
                chapter_duration = chunk_start_in_chapter + chunk_duration

                chunk_text = clean_text[chunk['text_start']:chunk['text_end']]
                words = chunk_text.split()
                if not words:
                    continue

                time_per_word = chunk_duration / len(words)
                chunk_paras = chunk.get('paragraphs', [])

                for word_idx, word in enumerate(words):
                    start_time = chunk_start_in_chapter + (word_idx * time_per_word)
                    end_time = chunk_start_in_chapter + ((word_idx + 1) * time_per_word)

                    char_offset = len(' '.join(words[:word_idx])) + (1 if word_idx > 0 else 0)
                    text_pos = chunk['text_start'] + char_offset

                    # Look up paragraph ID from chunk's paragraph annotations
                    para_id = _find_para_id_for_offset(chunk_paras, char_offset)

                    all_words.append({
                        "word": word,
                        "start": round(start_time, 3),
                        "end": round(end_time, 3),
                        "text_pos": text_pos,
                        "para_id": para_id
                    })
        else:
            # FALLBACK MODE: No clean text file — distribute chapter words
            # proportionally across chunks by duration (still much better than
            # uniform across entire chapter)
            chapter_text = clean_text or ""

            # Try to extract just this chapter's text from the source markdown
            if clean_text and not clean_text_path.exists():
                # clean_text is actually the source markdown (loaded as fallback)
                try:
                    ch_text, _ = extract_chapter_text(clean_text, seq_idx, len(unique_chapters))
                    chapter_text = ch_text
                except Exception:
                    pass

            # Clean markdown from chapter text for word splitting
            chapter_text_clean = re.sub(r'^#{1,6}\s+', '', chapter_text, flags=re.MULTILINE)
            chapter_text_clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', chapter_text_clean)
            chapter_text_clean = re.sub(r'\*\*([^*]+)\*\*', r'\1', chapter_text_clean)
            chapter_text_clean = re.sub(r'\*([^*]+)\*', r'\1', chapter_text_clean)
            chapter_words = chapter_text_clean.split()

            if chapter_words:
                # Calculate total chapter duration from chunks
                for chunk in chapter_chunks:
                    chunk_start_in_chapter = chunk['cumulative_duration'] - chapter_start_time
                    chapter_duration = chunk_start_in_chapter + chunk['duration']

                # Distribute words across chunks proportionally by duration
                total_chapter_duration = sum(c['duration'] for c in chapter_chunks)
                word_cursor = 0

                for chunk in chapter_chunks:
                    chunk_start_in_chapter = chunk['cumulative_duration'] - chapter_start_time
                    chunk_duration = chunk['duration']

                    # Number of words for this chunk, proportional to its duration
                    if total_chapter_duration > 0:
                        word_share = chunk_duration / total_chapter_duration
                    else:
                        word_share = 1.0 / len(chapter_chunks)
                    n_words = max(1, round(len(chapter_words) * word_share))
                    chunk_words = chapter_words[word_cursor:word_cursor + n_words]
                    word_cursor += n_words

                    if not chunk_words:
                        continue

                    chunk_paras = chunk.get('paragraphs', [])
                    time_per_word = chunk_duration / len(chunk_words)
                    for word_idx, word in enumerate(chunk_words):
                        start_time = chunk_start_in_chapter + (word_idx * time_per_word)
                        end_time = chunk_start_in_chapter + ((word_idx + 1) * time_per_word)

                        # Estimate char_offset for text_pos (fix: was always 0)
                        char_offset = len(' '.join(chunk_words[:word_idx])) + (1 if word_idx > 0 else 0)
                        text_pos = chunk.get('text_start', 0) + char_offset

                        # Look up paragraph ID from chunk's paragraph annotations
                        para_id = _find_para_id_for_offset(chunk_paras, char_offset)

                        all_words.append({
                            "word": word,
                            "start": round(start_time, 3),
                            "end": round(end_time, 3),
                            "text_pos": text_pos,
                            "para_id": para_id
                        })

        # Build paragraph timing summaries from word-level para_id assignments
        paragraph_timings = _build_paragraph_timings(all_words)

        chapter_key = f"chapter_{seq_idx}"
        word_timings_data[chapter_key] = {
            "file_index": file_index,
            "audio_file": audio_filename,
            "chapter_number": seq_idx,
            "word_count": len(all_words),
            "duration": round(chapter_duration, 3),
            "words": all_words,
            "paragraphs": paragraph_timings
        }

        print(f"  Chapter {seq_idx}: {len(all_words)} words, {chapter_duration:.1f}s")

    return word_timings_data


def generate_word_timings_fallback(
    audio_path: Path,
    text: str
) -> List[Dict]:
    """
    Generate word timings using uniform distribution (fallback method).
    Less accurate but always works without external dependencies.

    Args:
        audio_path: Path to audio file
        text: Expected text content

    Returns:
        List of word timing dictionaries
    """
    print(f"  Using fallback method (uniform distribution)...")

    # Get audio duration
    duration = get_audio_duration(audio_path)
    if not duration:
        print(f"⚠️  Could not determine audio duration for {audio_path.name}")
        return []

    # Clean text and split into words
    # Remove markdown formatting (similar to clean_text_for_speech)
    clean_text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)  # Headers
    clean_text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean_text)  # Links
    clean_text = re.sub(r'\*\*([^*]+)\*\*', r'\1', clean_text)  # Bold
    clean_text = re.sub(r'\*([^*]+)\*', r'\1', clean_text)  # Italic

    words = clean_text.split()

    if not words:
        return []

    # Distribute words uniformly across duration
    time_per_word = duration / len(words)
    word_timings = []

    for i, word in enumerate(words):
        start_time = i * time_per_word
        end_time = (i + 1) * time_per_word
        word_timings.append({
            "word": word,
            "start": round(start_time, 3),
            "end": round(end_time, 3)
        })

    return word_timings


def generate_audiobook_word_timings(
    playlist_path: Path,
    source_text_path: Optional[Path] = None,
    method: str = "auto"
) -> Dict:
    """
    Generate word-level timings for an entire audiobook.

    Args:
        playlist_path: Path to M3U playlist
        source_text_path: Optional path to source text (auto-detected if None)
        method: Alignment method ("chunk_manifest", "whisperx", "whisper_cpp", "fallback", "auto")

    Returns:
        Dictionary with word timing data per chapter
    """
    # Determine alignment method (early, so chunk_manifest can short-circuit)
    chunk_manifest_path = find_chunk_manifest(playlist_path)

    if method == "auto":
        if chunk_manifest_path:
            method = "chunk_manifest"
        elif check_whisperx_available():
            method = "whisperx"
        elif check_whisper_cpp_available():
            method = "whisper_cpp"
        else:
            method = "fallback"

    # chunk_manifest method: uses chunk-level data directly, no source text needed
    if method == "chunk_manifest":
        if not chunk_manifest_path:
            print("⚠️  No chunk manifest found, falling back to uniform distribution")
            method = "fallback"
        else:
            print(f"✓ Using chunk manifest: {chunk_manifest_path.name}")
            return generate_word_timings_from_chunks(chunk_manifest_path, playlist_path)

    # Other methods need source text
    if not source_text_path:
        book_dir = playlist_path.parent
        while book_dir.name in ['audio_xtts', 'audio_kokoro', 'audio_edge', 'audio']:
            book_dir = book_dir.parent

        # Find markdown source
        md_files = list(book_dir.glob("*.md"))
        if md_files:
            source_text_path = md_files[0]
            print(f"✓ Auto-detected source text: {source_text_path.name}")
        else:
            print("❌ ERROR: No source text found. Please specify --text parameter.")
            sys.exit(1)

    # Read source text
    with open(source_text_path, 'r', encoding='utf-8') as f:
        source_text = f.read()

    # Parse playlist
    audio_files = parse_m3u_playlist(playlist_path)
    if not audio_files:
        print("❌ ERROR: No audio files found in playlist")
        sys.exit(1)

    print(f"✓ Found {len(audio_files)} audio files")
    print(f"✓ Using alignment method: {method}")

    # Generate word timings for each audio file
    word_timings_data = {}

    for i, audio_file in enumerate(audio_files, 1):
        print(f"\n[{i}/{len(audio_files)}] Processing: {audio_file.name}")

        # Detect chapter number from filename
        chapter_num = detect_chapter_from_filename(audio_file.name)
        if not chapter_num:
            chapter_num = i  # Fallback to file index

        # Extract corresponding text
        chapter_text, text_start_pos = extract_chapter_text(
            source_text,
            chapter_num,
            len(audio_files)
        )

        # Generate word timings using selected method
        if method == "whisperx":
            word_timings = generate_word_timings_whisperx(audio_file, chapter_text)
        elif method == "whisper_cpp":
            word_timings = generate_word_timings_whisper_cpp(audio_file, chapter_text)
        else:
            word_timings = generate_word_timings_fallback(audio_file, chapter_text)

        # Add text position by finding each word's actual position in the chapter text
        search_offset = 0
        for word_data in word_timings:
            word = word_data['word']
            # Search for the word starting from where we last found one
            pos = chapter_text.find(word, search_offset)
            if pos >= 0:
                word_data['text_pos'] = text_start_pos + pos
                search_offset = pos + len(word)
            else:
                # Fallback: estimate position if exact match not found
                word_data['text_pos'] = text_start_pos + search_offset
                search_offset += len(word) + 1

        # Store in result
        chapter_key = f"chapter_{chapter_num}"
        word_timings_data[chapter_key] = {
            "file_index": i - 1,
            "audio_file": audio_file.name,
            "chapter_number": chapter_num,
            "word_count": len(word_timings),
            "duration": word_timings[-1]['end'] if word_timings else 0.0,
            "words": word_timings
        }

        print(f"  ✓ Generated {len(word_timings)} word timings")

    return word_timings_data


def save_word_timings(data: Dict, output_path: Path):
    """Save word timing data to JSON file"""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"\n✓ Word timings saved: {output_path}")


def main():
    """Command-line interface"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate word-level timing data for audiobook karaoke sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Auto-detect everything
  python generate_word_timings.py books/call_cthulhu/audio_kokoro/audiobook.m3u

  # Specify source text explicitly
  python generate_word_timings.py audiobook.m3u --text books/call_cthulhu/call_cthulhu.md

  # Force specific alignment method
  python generate_word_timings.py audiobook.m3u --method fallback

Methods:
  whisperx      - Most accurate, requires: pip install whisperx
  whisper_cpp   - Lightweight, requires: whisper.cpp binary
  fallback      - Uniform distribution, always works (less accurate)
  auto          - Auto-select best available method (default)
        """
    )

    parser.add_argument(
        'playlist',
        help='Path to M3U audiobook playlist'
    )

    parser.add_argument(
        '--text',
        help='Path to source text file (auto-detected if not provided)'
    )

    parser.add_argument(
        '--method',
        choices=['chunk_manifest', 'whisperx', 'whisper_cpp', 'fallback', 'auto'],
        default='auto',
        help='Word alignment method (default: auto, prefers chunk_manifest)'
    )

    parser.add_argument(
        '--output',
        help='Output JSON file path (default: auto-generated)'
    )

    args = parser.parse_args()

    playlist_path = Path(args.playlist)
    if not playlist_path.exists():
        print(f"❌ ERROR: Playlist not found: {args.playlist}")
        sys.exit(1)

    source_text_path = Path(args.text) if args.text else None
    if source_text_path and not source_text_path.exists():
        print(f"❌ ERROR: Source text not found: {args.text}")
        sys.exit(1)

    print("\n" + "="*70)
    print("WORD TIMING GENERATION")
    print("="*70)

    # Generate word timings
    word_timings_data = generate_audiobook_word_timings(
        playlist_path,
        source_text_path,
        method=args.method
    )

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        # Auto-generate: books/book_name/book_name_word_timings.json
        book_dir = playlist_path.parent
        while book_dir.name in ['audio_xtts', 'audio_kokoro', 'audio_edge', 'audio']:
            book_dir = book_dir.parent

        book_name = book_dir.name
        output_path = book_dir / f"{book_name}_word_timings.json"

    # Save
    save_word_timings(word_timings_data, output_path)

    # Summary
    total_words = sum(ch['word_count'] for ch in word_timings_data.values())
    total_duration = sum(ch['duration'] for ch in word_timings_data.values())

    print("\n" + "="*70)
    print("GENERATION COMPLETE")
    print("="*70)
    print(f"Chapters: {len(word_timings_data)}")
    print(f"Total words: {total_words:,}")
    print(f"Total duration: {total_duration/60:.1f} minutes")
    print(f"Output: {output_path}")
    print("="*70)


if __name__ == "__main__":
    main()
