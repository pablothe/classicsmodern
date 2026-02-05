# Legacy TTS Scripts (Deprecated)

These scripts are **deprecated** and should **not be used** for new audiobook generation.

## Why Deprecated?

The project has standardized on **Kokoro TTS** as the ONLY supported TTS system for these reasons:

1. **Quality:** Kokoro provides superior audio quality (rivals commercial APIs)
2. **Speed:** 31× faster than alternatives like Bark
3. **License:** Apache 2.0 (commercial-friendly)
4. **Local:** 100% local inference, no API calls
5. **Voices:** 52 preset voices (American, British, male/female)

## Current TTS System

**Use these instead:**
- `make_audiobook.py` - Unified one-command workflow (uses Kokoro)
- `local_tts_kokoro.py` - Direct Kokoro TTS generation

## Scripts in This Directory

### local_tts_edge.py
- **Type:** Cloud-based (Microsoft Edge TTS API)
- **Issues:**
  - Not truly local (makes API calls to Microsoft)
  - Quality inferior to Kokoro
  - Dependent on Microsoft's service availability
- **Alternative:** Use `make_audiobook.py` with Kokoro

### local_tts_xtts.py
- **Type:** Local voice cloning (XTTS-v2 / Coqui TTS)
- **Issues:**
  - Non-commercial license (AGPL)
  - Slow (2-4× slower than realtime on CPU)
  - Requires reference voice samples
  - 250 character limit per chunk
- **Alternative:** Use `make_audiobook.py` with Kokoro's 52 preset voices

### local_tts_orpheus.py
- **Type:** Local TTS (Orpheus / Llama-3b based)
- **Issues:**
  - Requires NVIDIA GPU (not compatible with Apple Silicon)
  - Limited platform support (Linux/Windows only)
  - Slower than Kokoro
- **Alternative:** Use `make_audiobook.py` with Kokoro (Apple Silicon optimized)

## Migration Guide

**Old workflow (DEPRECATED):**
```bash
# DON'T USE THESE
python3 local_tts_edge.py translated.md
python3 local_tts_xtts.py translated.md voice.wav en
python3 local_tts_orpheus.py translated.md --voice tara
```

**New workflow (RECOMMENDED):**
```bash
# Use the unified audiobook maker (Kokoro only)
python3 make_audiobook.py books/mybook/book.md --voice bf_emma --generate-cover

# Or use Kokoro directly
python3 local_tts_kokoro.py books/mybook/book.md --voice bf_emma
```

**Top Kokoro voices:**
- `bf_emma` - British Female (classics)
- `bm_george` - British Male (classics)
- `af_sky` - American Female (default)
- `am_adam` - American Male
- `am_onyx` - American Male (deep)

**Total: 52 voices available** (af_*, am_*, bf_*, bm_*)

## Why Keep These Files?

These scripts are preserved for:
1. **Reference:** Understanding historical implementation approaches
2. **Research:** Comparing TTS systems and quality
3. **Recovery:** Emergency fallback if Kokoro unavailable (unlikely)

**Do NOT use these for production audiobook generation.**

## Questions?

See the main project documentation:
- [README.md](../README.md) - Project overview
- [GUIDE.md](../GUIDE.md) - Complete user guide
- [CLAUDE.md](../CLAUDE.md) - Technical reference
