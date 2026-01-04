## Known Issues & Solutions

### 1. Audio Chunk Overlap/Repetition ⚠️

**Issue:** When playing sequential audio parts, you may hear the same phrase repeated at chunk boundaries.

**Why it happens:**
- Translation uses 20-word context overlap to maintain translation quality
- This overlap ensures coherent translation across chunks
- When audio files are generated from overlapping text, the TTS reads the same content twice

**Example:**
```
Chunk 1 ends with: "...y él siguió adelante sin mirar atrás."
Chunk 2 starts with: "sin mirar atrás. Mientras caminaba..."
```

**Solutions:**

#### Option A: Skip First Few Seconds of Each Part (Quick Fix)
When combining files, trim the first 3-5 seconds of each subsequent part:

```bash
# Manual trim with ffmpeg
ffmpeg -i part002.mp3 -ss 00:00:03 -acodec copy part002_trimmed.mp3
```

#### Option B: Reduce Translation Overlap (Permanent Fix)
Edit `local_reader_config.py`:

```python
class TranslationConfig:
    context_overlap_words: int = 5  # Reduced from 20
```

Then re-translate. Trade-off: Less overlap = potentially less coherent translation.

#### Option C: Smart Deduplication (Advanced) ✅ IMPLEMENTED & AUTOMATED

**NEW: Automatic Prevention + Failsafe Cleanup**

The system now uses a **two-layer approach** to prevent duplicates:

**Layer 1: LLM-Guided Context (Primary)**
- Translation now includes context from previous chunk
- LLM is instructed: "Here's the previous ending for reference, DON'T translate it again"
- Prevents most duplicates before they happen

**Layer 2: Exact-Match Cleanup (Failsafe)**
- After translation completes, automatic deduplication runs
- Finds any exact text matches at chunk boundaries
- Removes duplicates that slipped through Layer 1

**How to use:**
```bash
# Batch translation now includes automatic deduplication
python3 local_reader_batch_translator.py books/crime_punishment/chunks/ Russian Spanish

# This will:
# 1. Translate with context awareness (prevents duplicates)
# 2. Auto-run deduplication as failsafe
# 3. Create clean files in translated/deduplicated/
```

**Manual deduplication (if needed):**
```bash
python3 local_reader_deduplicate.py books/your_book/chunks/translated/
```

#### Option D: Use Combined File Only
The repetition is less noticeable in a combined single file if you're not stopping between parts.

**Current Recommendation:**
- ✅ **Fully automated!** Batch translator now prevents + removes duplicates automatically
- Just use `local_reader_batch_translator.py` - deduplication happens automatically
- Generate audio from `translated/deduplicated/` files

---

### 2. Table of Contents in Wrong Language

**Issue:** First few audio parts may include Russian/mixed language table of contents.

**Why it happens:**
- Original file had Russian table of contents
- Translation partially translated it
- Audio generation reads everything

**Solution:**
✅ **Fixed:** Use `chunk_001_CLEANED_spanish.md` which has proper Spanish table of contents.

**For future translations:**
1. Remove table of contents before translation
2. Or create proper translated TOC manually
3. Or start audio from Part 4-5 (where actual story begins)

---

### 3. Large File Sizes

**Issue:** Combined audiobook is 72.8 MB for ~1 hour of content.

**Why it happens:**
- OpenAI TTS generates high-quality stereo audio
- Default bitrate is higher than necessary for speech

**Solution:**
✅ **Fixed:** Compression script reduces by 40%

```bash
python local_reader_audio_compress.py audiobook.mp3 96k
# 72.8 MB → 43.7 MB (40% reduction)
```

**Compression options:**
- `64k` - Very compressed (smaller, adequate for speech)
- `96k` - Good balance (**RECOMMENDED**)
- `128k` - Higher quality
- Conversion to MONO automatically (speech doesn't need stereo)

---

### 4. No Cross-Device Progress Sync

**Issue:** Progress doesn't sync between devices.

**Why it happens:**
- Web player uses browser localStorage (local only)
- No cloud backend implemented yet

**Workarounds:**
1. **Export/Import progress** (manual):
   ```javascript
   // In browser console - Export
   console.log(localStorage.getItem('audiobook_track'))

   // Import on other device
   localStorage.setItem('audiobook_track', '5')
   ```

2. **Use same device** for listening

3. **Note progress manually** before switching

**Future Solution:**
- Phase 6: Mobile app with cloud sync
- Or add simple progress export/import UI

---

### 5. Translation Quality Varies

**Issue:** Some translations may sound awkward or unnatural.

**Why it happens:**
- Local model (gemma3-translator:4b) is good but not perfect
- Literary Russian → Modern Spanish is challenging
- Context window limitations

**Solutions:**
1. **Use 4b model** (not 1b) - higher quality
2. **Increase chunk size** for more context:
   ```python
   chunk_size_words: int = 500  # Instead of 250
   ```
3. **Manual post-editing** of important sections
4. **Future:** Try different models (OpenAI GPT-4, Claude, etc.)

---

### 6. API Costs for Audio Generation

**Issue:** OpenAI TTS API costs money.

**Current cost:** ~$0.015/1000 characters
- 10,000-word chapter ≈ 60,000 chars ≈ $0.90

**Solutions:**
1. **Short term:** Just use for important books
2. **Long term:** Implement local TTS (Orpheus-3B, Coqui TTS)
3. **Alternative:** Use free TTS (lower quality):
   - Google TTS (via gTTS library)
   - pyttsx3 (offline, robotic)
   - Mozilla TTS

**Future Goal (per README):**
Replace OpenAI with local Orpheus-3B TTS - fully free and offline.

---

### 7. Translation Takes Long Time

**Issue:** Translating full book (18 chunks) takes ~3 hours.

**Why:**
- Local model runs on CPU/GPU
- ~10 minutes per 10k-word chunk
- Sequential processing

**Solutions:**
1. **Accept it** - still faster than manual translation!
2. **Upgrade hardware** - better GPU = faster
3. **Run overnight** - let it process while sleeping
4. **Parallel processing** (future enhancement):
   - Translate multiple chunks simultaneously
   - Requires multi-GPU or distributed setup

---

## Roadmap for Fixes

### Priority 1 (Next Sprint)
- [x] Smart overlap detection/removal for audio ✅
- [ ] Progress export/import UI buttons
- [ ] Better error handling for API failures

### Priority 2 (Future)
- [ ] Local TTS integration (remove OpenAI dependency)
- [ ] Parallel chunk translation
- [ ] Translation quality improvements

### Priority 3 (Long-term)
- [ ] Mobile app (Phase 6)
- [ ] Cloud progress sync
- [ ] Advanced compression options

---

## Workarounds Summary

| Issue | Quick Fix | Permanent Fix |
|-------|-----------|---------------|
| Chunk overlap | Use combined file | Smart deduplication ✅ |
| File size | Compress with 96k bitrate | Already implemented ✅ |
| Progress sync | Manual export/import | Cloud sync (future) |
| Translation time | Run overnight | Parallel processing |
| API costs | Use sparingly | Local TTS |
| Table of contents | Use CLEANED version | Pre-process files |

---

## Reporting New Issues

If you find new issues:
1. Note the exact error message
2. Check this file for known issues
3. Try the suggested workarounds
4. Document steps to reproduce

**For this project, document issues in:**
- This file (KNOWN_ISSUES.md)
- GitHub Issues (if using git)
- Project notes
