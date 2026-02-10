# Translation Troubleshooting & Recovery Guide

## Overview

This guide explains how to diagnose, fix, and resume failed translations for the **De Brevitate Vitae** project (and any other book translation).

---

## 🆕 What's New (2026-02-08)

### 1. **Request Timeouts** ⏰
- **Problem**: Ollama API requests had no timeout, causing silent hangs
- **Fix**: Added 5-minute timeout to all Ollama API calls
- **Result**: Failures now trigger clear error messages instead of hanging forever

### 2. **Detailed Logging** 📝
- **Log File**: `translation_debug.log` (created in project root)
- **What's Logged**:
  - Every API request/response with timing
  - Chunk sizes and progress
  - Timeout and error details
  - Ollama health status

### 3. **Checkpoint/Resume System** 💾
- **Automatic Checkpoints**: Progress saved after each completed chapter
- **Resume Support**: Re-run same command to continue from where you left off
- **Checkpoint Files**: `.translation_checkpoint_book.json` (hidden, auto-managed)

### 4. **Ollama Health Monitoring** 🏥
- Check if Ollama is running and responsive
- Monitor loaded models
- Detect connection issues early

---

## 🔍 Diagnosing Your Failed Translation

### Step 1: Check the Debug Log

```bash
tail -50 translation_debug.log
```

**Look for**:
- `[chunk_X] TIMEOUT` - Ollama took >5 minutes
- `[chunk_X] ERROR` - API error or exception
- `Response received in X.Xs` - How long each request took

### Step 2: Check Ollama Status

```bash
# Is Ollama running?
ollama ps

# Check system resources
top -o MEM | head -20  # macOS
htop                   # Linux

# Test Ollama manually
ollama run zongwei/gemma3-translator:4b "Translate from Latin to English: vita brevis"
```

### Step 3: Find the Checkpoint

```bash
ls -la books/de_brevitate_vitae/.translation_checkpoint_*
```

**If checkpoint exists**: You can resume!
**If no checkpoint**: Translation never started or was cleaned up

---

## 🚀 Recovery Options

### Option 1: Resume from Checkpoint (Recommended)

If a checkpoint exists, just **re-run the exact same command**:

```bash
# Via web UI (http://localhost:8000)
# - Just click "Generate" again with same settings
# - It will automatically resume from last completed chapter

# Via CLI
python3 structured_translator.py books/de_brevitate_vitae/book.md \
  --source-lang Latin \
  --target-lang "Modern English" \
  --model ollama:zongwei/gemma3-translator:4b
```

**Output will show**:
```
📂 Checkpoint loaded: 13 chapters completed
⏭️  Resuming from chapter 14
```

### Option 2: Restart from Scratch

```bash
# Delete checkpoint file
rm books/de_brevitate_vitae/.translation_checkpoint_*

# Run translation again
python3 structured_translator.py books/de_brevitate_vitae/book.md \
  --source-lang Latin \
  --target-lang "Modern English" \
  --model ollama:zongwei/gemma3-translator:4b
```

### Option 3: Investigate and Fix Ollama Issue

If timeouts persist:

**1. Check Ollama memory usage**:
```bash
ollama ps  # Shows memory per model
```

**2. Restart Ollama**:
```bash
# macOS/Linux
pkill ollama
ollama serve &

# Or restart from menu bar app
```

**3. Reduce model load**:
```bash
# Unload unused models
ollama stop <model_name>
```

**4. Try smaller chunks** (edit `local_reader_config.toml`):
```toml
[chunking]
chunk_size_words = 150  # Default: 250
```

---

## 📊 Understanding the Logs

### Successful Translation
```
2026-02-08 15:21:31 [INFO] [chunk_1] Starting translation (1247 chars, 189 words)
2026-02-08 15:21:31 [INFO] [chunk_1] API: http://localhost:11434/api/generate, Model: zongwei/gemma3-translator:4b
2026-02-08 15:21:31 [INFO] [chunk_1] Attempt 1/3 - sending request to Ollama...
2026-02-08 15:21:48 [INFO] [chunk_1] Response received in 17.2s (status: 200)
2026-02-08 15:21:48 [INFO] [chunk_1] Translation received (1156 chars)
```

### Timeout (Problem)
```
2026-02-08 15:35:12 [INFO] [chunk_2] Starting translation (1534 chars, 234 words)
2026-02-08 15:35:12 [INFO] [chunk_2] Attempt 1/3 - sending request to Ollama...
2026-02-08 15:40:12 [ERROR] [chunk_2] TIMEOUT after 300.0s (attempt 1/3)
2026-02-08 15:40:12 [ERROR] [chunk_2] Chunk size: 1534 chars, 234 words
2026-02-08 15:40:12 [ERROR] [chunk_2] Check Ollama status: ollama ps
```

**Actions**:
1. Check `ollama ps` for stuck processes
2. Check system memory with `top`
3. Restart Ollama if needed
4. Resume translation

### API Error
```
2026-02-08 15:42:05 [ERROR] [chunk_3] ERROR after 2.1s (attempt 1/3): ConnectionError: Connection refused
```

**Actions**:
1. Ollama not running - start it: `ollama serve`
2. Check firewall blocking localhost:11434
3. Verify `local_reader_config.toml` has correct `ollama_host`

---

## 🎯 Specific Fix for De Brevitate Vitae

### Your Situation
- **Stopped at**: Chapter 14 (27% complete)
- **Reason**: Likely Ollama timeout (no error was logged before fix)
- **Checkpoint**: Should exist with 13 completed chapters

### Recommended Steps

**1. Check current state**:
```bash
cd /Users/pabloeder/classicsmodern/classicsmodern

# Check if checkpoint exists
ls -la books/de_brevitate_vitae/.translation_checkpoint_*

# Check last log entry
tail -20 translation_debug.log
```

**2. Verify Ollama is healthy**:
```bash
ollama ps
ollama run zongwei/gemma3-translator:4b "Test: vita brevis"
```

**3. Resume translation** (with new timeout & logging):
```bash
# Option A: Via web server (recommended)
./start_server.sh
# Then go to http://localhost:8000
# Click De Brevitate Vitae → Generate (same settings)
# Will auto-resume from chapter 14

# Option B: Via command line
python3 structured_translator.py books/de_brevitate_vitae/book.md \
  --source-lang Latin \
  --target-lang "Modern English" \
  --model ollama:zongwei/gemma3-translator:4b
```

**4. Monitor progress**:
```bash
# In another terminal, watch the logs
tail -f translation_debug.log
```

**What you'll see**:
```
📂 Checkpoint loaded: 13 chapters completed
⏭️  Resuming from chapter 14

[14/20] Translating chapter 14 (XIV.)...
[chunk_1] Starting translation (1456 chars, 221 words)
[chunk_1] Response received in 23.4s (status: 200)
[chunk_2] Starting translation (1623 chars, 247 words)
[chunk_2] Response received in 28.1s (status: 200)
[chunk_3] Starting translation (891 chars, 135 words)
[chunk_3] Response received in 14.8s (status: 200)
💾 Checkpoint saved: 14 chapters completed

[15/20] Translating chapter 15 (XV.)...
...
```

---

## 🛡️ Preventing Future Issues

### 1. Keep Ollama Healthy
```bash
# Before long translations, restart Ollama
pkill ollama
ollama serve &

# Verify it's responsive
ollama ps
```

### 2. Monitor Resources
```bash
# Watch memory during translation
watch -n 5 'ollama ps'

# Or use activity monitor
top -o MEM
```

### 3. Use Checkpoints
- Checkpoints save after **each chapter**
- Safe to Ctrl+C anytime
- Re-run to resume (no data loss)

### 4. Check Logs
```bash
# Monitor translation in real-time
tail -f translation_debug.log

# Or use grep for errors only
tail -f translation_debug.log | grep ERROR
```

---

## 📞 Still Stuck?

### Collect Debug Info
```bash
# 1. Last 100 log lines
tail -100 translation_debug.log > debug_output.txt

# 2. Ollama status
ollama ps >> debug_output.txt

# 3. System info
top -l 1 | head -20 >> debug_output.txt  # macOS
free -h >> debug_output.txt              # Linux

# 4. Checkpoint status
ls -la books/de_brevitate_vitae/.translation_checkpoint_* >> debug_output.txt 2>&1
```

### Quick Fixes

**"ConnectionRefusedError"**:
```bash
ollama serve &
```

**"Model not found"**:
```bash
ollama pull zongwei/gemma3-translator:4b
```

**"Timeout on every chunk"**:
```bash
# Reduce chunk size
# Edit local_reader_config.toml:
[chunking]
chunk_size_words = 100

# Or try different model
ollama pull gemma2:9b
```

**"Checkpoint won't load"**:
```bash
# Delete and start fresh
rm books/de_brevitate_vitae/.translation_checkpoint_*
```

---

## 📝 Summary of Improvements

| Feature | Before | After |
|---------|--------|-------|
| **Timeout** | None (hangs forever) | 5 minutes (fails fast) |
| **Logging** | Print statements only | Detailed debug log file |
| **Recovery** | Manual, error-prone | Automatic checkpoint/resume |
| **Monitoring** | Blind execution | Health checks & diagnostics |
| **User Experience** | Silent failures | Clear error messages |

**Result**: Translation jobs are now **observable**, **recoverable**, and **debuggable**!
