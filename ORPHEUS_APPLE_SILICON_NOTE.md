# Orpheus-TTS on Apple Silicon (M1/M2/M3) - Known Issues

## ⚠️ Important Notice

**Orpheus-TTS currently has poor support for Apple Silicon Macs.** The library is primarily designed for NVIDIA GPUs (CUDA) and does not properly detect or utilize Apple's Metal Performance Shaders (MPS).

## Error You'll Encounter

```
AssertionError: Torch not compiled with CUDA enabled
```

This error occurs because Orpheus-TTS tries to use CUDA even on non-NVIDIA systems.

## Recommended Alternative: XTTS-v2

For **Apple Silicon Macs (M1/M2/M3)**, we **strongly recommend using XTTS-v2** instead:

```bash
# XTTS-v2 works excellently on Apple Silicon
python local_tts_xtts.py books/mybook/translated.md voice_ref.wav en
```

### Why XTTS-v2 for Apple Silicon?

✅ **Native Apple Silicon support** - Optimized for M-series chips
✅ **Voice cloning** - Use any 10-30 second voice sample
✅ **Proven reliability** - Extensively tested on macOS
✅ **Good quality** - Very natural sounding (slightly less emotional than Orpheus, but excellent)
✅ **Free and local** - No API costs
✅ **Multi-language** - Supports 16 languages

### Quality Comparison

| Feature | XTTS-v2 (Mac) | Orpheus (NVIDIA) |
|---------|---------------|------------------|
| Apple Silicon | ✅ Excellent | ❌ Broken |
| Quality | ⭐⭐⭐⭐ Very Good | ⭐⭐⭐⭐⭐ SOTA |
| Speed (M2) | 0.25-0.5x RT | N/A (doesn't work) |
| Voice Options | Custom cloning | 8 presets |
| Emotion Tags | No | Yes (if it worked) |

## When to Use Orpheus-TTS

Orpheus-TTS is **only recommended if you have**:
- **NVIDIA GPU** with CUDA support
- Linux or Windows machine
- Access to cloud GPU (Google Colab, AWS, etc.)

## Quick Test: XTTS-v2

Since you're on Apple Silicon, let's test with XTTS-v2 instead:

```bash
# Test with sample file
python3 local_tts_xtts.py test_orpheus_sample.md voice_ref.wav en

# Or with Call of Cthulhu
python3 local_tts_xtts.py books/call_cthulhu/The_CALL_of_CTHULHU_cleaned_original.md voice_ref.wav en
```

**Note**: You'll need a voice reference file. You can:
1. Record 10-30 seconds of clean speech
2. Extract audio from a YouTube video
3. Use any high-quality voice sample you like

## Future Updates

The Orpheus-TTS team may add Apple Silicon support in the future. Check their GitHub for updates:
https://github.com/canopyai/Orpheus-TTS/issues

## Summary for Apple Silicon Users

**✅ RECOMMENDED**: Use `local_tts_xtts.py` (XTTS-v2)
- Works perfectly on M1/M2/M3 Macs
- Excellent quality with voice cloning
- Proven, tested, reliable

**❌ NOT RECOMMENDED**: Use `local_tts_orpheus.py` (Orpheus-TTS)
- Broken on Apple Silicon
- Requires NVIDIA GPU
- Only works on Linux/Windows with CUDA

---

**Bottom line**: For macOS users, stick with XTTS-v2. The integration I built works perfectly, but Orpheus itself doesn't support your hardware yet.
