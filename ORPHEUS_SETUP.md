# Orpheus-TTS Setup Guide

Complete setup instructions for integrating Orpheus-TTS into the Modern Classics audiobook pipeline.

## Overview

Orpheus-TTS is a SOTA open-source text-to-speech system built on the Llama-3b backbone that produces human-like speech with natural intonation, emotion, and rhythm. It's superior to most commercial TTS models.

## Features

- **Human-Like Speech**: Natural intonation, emotion, and rhythm
- **8 Voices**: tara, leah, jess, leo, dan, mia, zac, zoe (in order of conversational realism)
- **Emotion Control**: Add tags like `<laugh>`, `<chuckle>`, `<sigh>`, `<cough>`, `<sniffle>`, `<groan>`, `<yawn>`, `<gasp>`
- **Low Latency**: ~200ms streaming latency for realtime applications
- **Automatic Chapter Detection**: Detects Roman numerals and Markdown headers
- **Smart Audio Combining**: Merges chunks into chapter files using FFmpeg

## Installation

### 1. Install Orpheus-TTS

```bash
pip install orpheus-speech
```

**Note**: If you encounter KV cache errors or `max_model_len` property issues, revert to vllm 0.7.3:

```bash
pip install vllm==0.7.3
```

### 2. Install FFmpeg (if not already installed)

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg
```

### 3. Verify Installation

```bash
python -c "from orpheus_tts import OrpheusModel; print('✓ Orpheus-TTS installed successfully')"
```

## Usage

### Basic Usage

```bash
# Generate audiobook with default voice (tara)
python local_tts_orpheus.py books/mybook/translated.md
```

### Advanced Usage

```bash
# Use different voice
python local_tts_orpheus.py books/mybook/translated.md --voice leah

# Use pretrained model (for custom voice cloning experiments)
python local_tts_orpheus.py books/mybook/translated.md --pretrain
```

### Available Voices

Listed in order of conversational realism (subjective benchmarks):

1. **tara** (default) - Most conversational
2. **leah**
3. **jess**
4. **leo**
5. **dan**
6. **mia**
7. **zac**
8. **zoe**

### Emotion Tags

Add these tags directly in your text for expressive speech:

- `<laugh>` - Laughter
- `<chuckle>` - Light laugh
- `<sigh>` - Sighing
- `<cough>` - Coughing sound
- `<sniffle>` - Sniffling
- `<groan>` - Groaning
- `<yawn>` - Yawning
- `<gasp>` - Gasping

**Example:**
```markdown
"Well, I never <sigh> expected this to happen," she said with a <chuckle>.
```

## Output Structure

Orpheus-TTS generates the following directory structure:

```
books/mybook/audio_orpheus/
├── raw/                           # Unprocessed WAV files
│   ├── mybook_chunk001_raw.wav
│   ├── mybook_chunk002_raw.wav
│   └── ...
├── mybook_chunk001.mp3            # Processed chunks (normalized)
├── mybook_chunk002.mp3
├── mybook_chapter_01.mp3          # Combined chapters (if detected)
├── mybook_chapter_02.mp3
├── mybook_audiobook_TIMESTAMP.m3u # Master playlist
└── mybook_chunks_TIMESTAMP.m3u    # Individual chunks playlist
```

## Performance

- **Speed**: 1-2x realtime (GPU recommended)
- **Quality**: Superior to most commercial TTS models
- **Chunk Size**: 500 characters (longer than XTTS's 250 char limit)
- **Streaming Latency**: ~200ms

## Comparison: Orpheus vs XTTS

| Feature | Orpheus-TTS | XTTS-v2 |
|---------|-------------|---------|
| **Quality** | SOTA, human-like | Very good, slightly robotic |
| **Speed** | 1-2x realtime | 2-4x slower than realtime |
| **Voice Options** | 8 preset voices | Custom voice cloning (10-30s sample) |
| **Emotion Control** | Yes (8 tags) | No |
| **Chunk Size** | 500 chars | 250 chars |
| **GPU Support** | Yes (recommended) | Optional |
| **Model Type** | Llama-3b | Coqui TTS |
| **Best For** | Natural conversational speech | Matching specific voices |

## Troubleshooting

### Error: "max_model_len property does not exist"

**Solution**: Revert to vllm 0.7.3:
```bash
pip install vllm==0.7.3
```

### Error: "KV cache error"

**Solution**: Use the local package instead of PyPI version:
```python
import sys
sys.path.insert(0, 'orpheus_tts_pypi')
from orpheus_tts import OrpheusModel
```

Or update to the latest version:
```bash
pip install --upgrade orpheus-speech
```

### FFmpeg Not Found

**macOS:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt install ffmpeg
```

### Slow Generation (CPU-only)

Orpheus-TTS benefits greatly from GPU acceleration. If running on CPU:

1. Consider using XTTS-v2 instead (more CPU-optimized)
2. Use smaller chunk sizes
3. Process chapters in parallel (manual scripting required)

## Integration with Existing Workflow

### Complete Pipeline

```bash
# 1. Preprocess book
python3 book_preprocessor.py books/mybook/original.md

# 2. Translate (if needed)
python3 local_reader_batch_translator.py books/mybook/chunks/ Russian "Modern English"

# 3. Generate audio with Orpheus
python local_tts_orpheus.py books/mybook/translated/deduplicated/chunk_001_DEDUPED.md --voice tara

# 4. Play audiobook
afplay books/mybook/audio_orpheus/mybook_audiobook_*.m3u
```

### Batch Processing

For multiple books:

```bash
for book in books/*/translated.md; do
    python local_tts_orpheus.py "$book" --voice tara
done
```

## Best Practices

1. **Voice Selection**: Start with "tara" for most conversational sound
2. **Emotion Tags**: Use sparingly - too many can sound unnatural
3. **Chunk Size**: Default 500 chars works well, increase for longer contexts
4. **Post-Processing**: Always use normalization (default) for consistent volume
5. **Format**: MP3 output (default) saves significant storage vs WAV

## Resources

- [Orpheus-TTS GitHub](https://github.com/canopyai/Orpheus-TTS)
- [Original Blog Post](https://canopylabs.ai/blog/orpheus-tts)
- [Model Card (HuggingFace)](https://huggingface.co/canopylabs/orpheus-tts-0.1-finetune-prod)
- [Modern Classics CLAUDE.md](CLAUDE.md) - Full technical reference

## Support

For issues specific to:
- **Orpheus-TTS**: [GitHub Issues](https://github.com/canopyai/Orpheus-TTS/issues)
- **Modern Classics Integration**: Check [CLAUDE.md](CLAUDE.md) or file an issue in this repo
