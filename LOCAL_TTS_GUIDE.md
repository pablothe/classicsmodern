# Local TTS with XTTS-v2

Free, local text-to-speech for audiobook generation using Coqui XTTS-v2. **$0 cost** vs ~$15-40 per book with OpenAI API.

## Quick Setup

```bash
# Install
pip install TTS==0.27.3
brew install ffmpeg  # macOS (or: sudo apt install ffmpeg on Linux)

# Verify
tts --version
ffmpeg -version
```

## Basic Usage

```bash
# Generate audiobook (no voice cloning)
python local_tts_xtts.py translated_book.md

# With voice cloning (recommended)
python local_tts_xtts.py translated_book.md voice_ref.wav en

# Multi-language
python local_tts_xtts.py libro.md voz.wav es  # Spanish
python local_tts_xtts.py livre.md voix.wav fr  # French
```

## Voice Cloning

Clone any voice with a 10-30 second sample:

```bash
# Option 1: Extract from existing audio
ffmpeg -i audiobook.mp3 -ss 00:01:00 -t 20 sample.mp3

# Option 2: Record yourself (macOS)
# Use QuickTime Player: File > New Audio Recording

# Prepare for XTTS-v2
python local_tts_xtts.py --prepare-voice sample.mp3 voice_ref.wav

# Use it
python local_tts_xtts.py book.md voice_ref.wav en
```

**Best results:**
- 10-30 seconds of clear speech
- No background music or noise
- Consistent mic distance
- Single speaker

## Batch Processing (Full Book)

```bash
cd books/mybook/chunks/translated/deduplicated/

# Process all chunks
for chunk in chunk_*_DEDUPED.md; do
    python ../../../../local_tts_xtts.py "$chunk" ../../../../voice_ref.wav en
done

# Combine into single audiobook
cd audio_xtts/
python ../../../../local_reader_audio_combiner.py *.m3u complete_audiobook.mp3
```

## What It Does Automatically

Every audio chunk is automatically:
1. **Speed adjusted**: 1.15x faster (reduces robotic feel)
2. **Normalized**: -16 LUFS (audiobook standard)
3. **Converted to MP3**: 128kbps (~90% smaller than WAV)

Raw unprocessed files saved in `audio_xtts/raw/` for re-processing if needed.

## Supported Languages

16 languages: `en`, `es`, `fr`, `de`, `it`, `pt`, `pl`, `tr`, `ru`, `nl`, `cs`, `ar`, `zh-cn`, `ja`, `ko`, `hu`

## Performance

- **Speed**: 2-4x slower than realtime on CPU (1 min audio = 2-4 min processing)
- **Memory**: ~4-6 GB RAM during generation
- **First run**: +1-2 min for model download (~1.8GB, cached after)
- **Full book (18 chunks)**: 3-6 hours (run overnight)

## Customization

Edit [`local_tts_xtts.py:430`](local_tts_xtts.py#L430) to change defaults:

```python
result = generator.generate_audiobook(
    input_file,
    chunk_size=1500,     # 500-1500 recommended
    speed=1.15,          # 1.0-2.0 (try 1.25 for faster)
    normalize=True,      # Loudness normalization
    to_mp3=True         # False to keep WAV
)
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "TTS not found" | `pip install --force-reinstall TTS==0.27.3` |
| "ffmpeg not found" | `brew install ffmpeg` or `sudo apt install ffmpeg` |
| Out of memory | Reduce `chunk_size` to 800 or close other apps |
| Robotic sound | Increase `speed` to 1.25x or use better reference voice |
| Voice doesn't match | Use cleaner, longer reference (20-30 sec, quiet room) |

## Cost Comparison

Crime & Punishment (18 chunks):
- **Local TTS**: $0, 3-6 hours
- **OpenAI API**: ~$36, 30-60 min

**Break-even**: After 2-3 books, local TTS setup time is justified by cost savings.

## File Output

```
audio_xtts/
├── raw/                           # Unprocessed WAV files
│   └── chunk_001_chunk001_raw.wav
├── chunk_001_chunk001.mp3         # Processed (speed + normalized)
├── chunk_002_chunk001.mp3
└── chunk_001_audiobook.m3u        # Playlist
```

---

**See also**: [CLAUDE.md](CLAUDE.md) for complete project workflow
