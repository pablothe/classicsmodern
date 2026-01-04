# Git Repository Cleanup Guide

This guide helps clean up unnecessary files from the git repository.

## Problem

The repository currently tracks many generated files that shouldn't be in version control:
- ~130+ generated/translated book files (`*_cleaned.md`, `*_original.md`, `*_To_*.md`)
- Test directories (`mini_test/`, `test_translation/`)
- Generated documentation (`TEST_RESULTS_DEDUPLICATION.md`)

These files:
- Bloat the repository size
- Create noise in diffs and commits
- Should be regenerated locally, not shared

## Solution

The `.gitignore` has been updated to prevent these files from being tracked in the future.
Now we need to remove already-tracked files from git history.

---

## Step 1: Review What Will Be Removed

Run this to see all files that should be removed:

```bash
# Generated book files (translations, cleaned, original versions)
git ls-files | grep -E '_(cleaned|original)\.md$|_To_.*\.md$|_modern_.*\.md$'

# Test directories
git ls-files | grep -E 'mini_test/|test_translation/|test_chunk/'

# Old documentation files (already in .gitignore)
git ls-files | grep -E 'AUDIOBOOK_PLAYBACK_GUIDE\.md|PROGRESS_TRACKING\.md|TRANSLATION_WORKFLOW\.md|KNOWN_ISSUES\.md'
```

**Total files to remove:** ~140+

---

## Step 2: Remove Files From Git (Keep Local Copies)

This removes files from git tracking but keeps them on your filesystem.

### Option A: Remove Generated Book Files Only (RECOMMENDED)

```bash
# Remove all generated/translated book files
git ls-files | grep -E 'books/.*(cleaned|original)\.md$' | xargs git rm --cached
git ls-files | grep -E 'books/.*_To_.*\.md$' | xargs git rm --cached
git ls-files | grep -E 'books/.*_modern_.*\.md$' | xargs git rm --cached

# Remove test directories
git rm --cached -r books/crime_punishment/mini_test/ 2>/dev/null || true
git rm --cached -r books/crime_punishment/test_translation/ 2>/dev/null || true

# Remove test results
git rm --cached TEST_RESULTS_DEDUPLICATION.md 2>/dev/null || true
git rm --cached translation.log 2>/dev/null || true
```

### Option B: Keep Only Original Books (AGGRESSIVE)

This keeps ONLY the original source books (one per book directory):

```bash
# Keep only these original books:
# - alices_adventures_in_wonderland.md
# - The_CALL_of_CTHULHU.md
# - de_brevitae_vitae.md
# - don_quijote.md
# etc.

# Remove everything else in books/
git ls-files | grep 'books/' | grep -v -E 'alice.*wonderland\.md$|CALL_of_CTHULHU\.md$|de_brevitae.*\.md$|don_quijote\.md$|Moby.*Whale\.md$|Origin.*Species|Pride.*Prejudice\.md$|Adventures.*Holmes|Time.*Machine|War.*World|Winnie.*Pooh\.md$|Zarathustra\.md$' | grep -E '\.md$' | xargs git rm --cached
```

---

## Step 3: Commit The Changes

```bash
# Stage the .gitignore changes
git add .gitignore

# Commit the removal
git commit -m "Clean up repository: remove generated files and update .gitignore

- Remove ~140+ generated translation files (_cleaned, _original, _modern_, _To_)
- Remove test directories (mini_test, test_translation)
- Update .gitignore to prevent tracking these in future
- Keep only original source books and core documentation"
```

---

## Step 4: What Should Be Tracked?

### ✅ KEEP in Git (Should be tracked):

**Core Documentation:**
- `CLAUDE.md` - Project architecture
- `LOCAL_READER_README.md` - Project overview and roadmap
- `DOCS_INDEX.md` - Documentation index
- `WORKFLOW_GUIDE.md` - Complete workflow guide
- `.gitignore` - Git configuration

**Core Code:**
- All `*.py` files (translation, audio, utils)
- `requirements.txt`
- `local_reader_config.py`

**Original Source Books:**
- One original book file per directory (e.g., `alices_adventures_in_wonderland.md`)
- Only the canonical source, not translations or variations

### ❌ DON'T TRACK (Should be ignored):

**Generated Translations:**
- `*_cleaned.md`
- `*_original.md`
- `*_modern_*.md`
- `*_To_*.md`
- `*_translated_*.md`

**Generated Audio:**
- `*.mp3`, `*.wav`, `*.m3u`, `*.flac`

**Test Files:**
- `mini_test/`, `test_translation/`, `test_chunk/`
- `TEST_RESULTS_*.md`
- `translation.log`

**Generated Documentation:**
- Test results and validation docs (can be regenerated)

**Progress Files:**
- `.translation_progress.json`
- `.audio_progress.json`

---

## Step 5: Verify Cleanup

After committing:

```bash
# Check what's tracked
git ls-files | grep 'books/'

# Should only show original source books, not generated files
```

Expected result: ~12-15 original book files, not 130+

---

## Future Prevention

The updated `.gitignore` now prevents:
- Generated translations (`*_cleaned.md`, `*_original.md`, `*_To_*.md`)
- Test directories (`mini_test/`, `test_*/`)
- Audio files (`*.mp3`, `*.wav`)
- Progress tracking files (`*.json`)

**When you generate new translations or audio, they won't be tracked by git.**

---

## Why This Matters

### Before Cleanup:
- **Repository size**: Large (130+ unnecessary files)
- **Diffs**: Noisy (changes to generated files)
- **Clones**: Slow (downloading all generated content)
- **Clarity**: Low (hard to see what's source vs. generated)

### After Cleanup:
- **Repository size**: Small (only source files)
- **Diffs**: Clean (only code and docs)
- **Clones**: Fast (minimal files)
- **Clarity**: High (obvious what's source)

---

## Rollback (If Needed)

If you accidentally remove something important:

```bash
# Restore a specific file
git restore --staged path/to/file.md

# Or reset everything before committing
git reset HEAD
```

---

## Recommended Approach

**Conservative cleanup (recommended for first pass):**

```bash
# 1. Remove obvious generated files
git ls-files | grep -E '_(cleaned|original)\.md$' | xargs git rm --cached

# 2. Remove test directories
git rm --cached -r books/crime_punishment/mini_test/ 2>/dev/null || true
git rm --cached -r books/crime_punishment/test_translation/ 2>/dev/null || true

# 3. Commit
git add .gitignore
git commit -m "chore: remove generated files and update .gitignore"

# 4. Review what's left
git ls-files | grep 'books/' | wc -l

# 5. If needed, do a second pass to remove more
```

---

## Summary

1. ✅ `.gitignore` updated to prevent future tracking
2. 🔄 Remove already-tracked generated files from git
3. ✅ Keep only source files and core documentation
4. 🎯 Result: Clean, maintainable repository

**Next:** Run the commands in Step 2, then commit!
