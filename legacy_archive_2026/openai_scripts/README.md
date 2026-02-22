# OpenAI Scripts Archive

Deprecated scripts that required the OpenAI cloud API. Archived February 22, 2026 as part of the project's commitment to 100% local operation.

## Archived Files

| File | Purpose |
|------|---------|
| `audio_generation.py` | OpenAI TTS via gpt-4o-audio-preview |
| `audio_translator.py` | OpenAI-powered translation |
| `local_reader_audio.py` | OpenAI TTS via tts-1 model |
| `o3call.py` | OpenAI o3 API wrapper |
| `simplify_further.py` | Text simplification via GPT-4o-mini |
| `translator.py` | OpenAI translator (all models) |
| `generate_audiobook.sh` | Shell wrapper for local_reader_audio.py |

## Replacements

- **Translation**: `structured_translator.py` with Ollama (100% local)
- **TTS**: `local_tts_kokoro.py` / `make_audiobook.py` with Kokoro TTS (100% local)
- **Audiobook pipeline**: `make_audiobook.py` (one command, fully local)
