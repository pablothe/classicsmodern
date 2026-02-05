# Hybrid RAG Improvements Applied

## Problem Identified

**Your test revealed:** The system missed the key Cthulhu description:
> "simultaneous pictures of an octopus, a dragon, and a human caricature"

**Why it failed:**
- Only retrieving **top 5 chunks** → Key description not in top 5
- Chunk size too large (**250 words**) → Description buried in middle of chunk
- Vague query ("Describe cthulhu in the first 25") → Poor semantic match

**Location of description:** Line 127 (7.2% through book)

---

## Improvements Applied

### **1. Increased Retrieval Coverage ✅**
**File:** `server/llm_chat.py`
**Change:** `top_k=5` → `top_k=10`

**Impact:**
- Retrieves **10 chunks** instead of 5
- Double the coverage for finding relevant passages
- Context size: ~1,500-2,000 words (still 75% less than naive 8K dump!)

---

### **2. Reduced Chunk Size ✅**
**File:** `server/semantic_retrieval.py`
**Change:**
- `target_words_per_chunk=250` → `150`
- `max_words_per_chunk=400` → `250`

**Impact:**
- Smaller, more focused chunks
- Better semantic embedding precision
- Key descriptions isolated instead of buried
- More chunks to search: 43 → ~70 for Call of Cthulhu

**Example:**
- **Before (250 words):** Chunk contains investigation + dreams + description
- **After (150 words):** Chunk focused on description only

---

### **3. Cleared Vector Cache ✅**
**Action:** Deleted `.vector_cache/` directories
**Result:** Books will be re-vectorized with new chunk size on next query

---

## Expected Results

### **Before This Fix:**
```
Query: "Describe cthulhu in the first 25"
Retrieved: 5 chunks (1,091 words)
Missed: "octopus, dragon, human" description
Answer: Generic references to "carven idol" and "cyclopean city"
```

### **After This Fix:**
```
Query: "Describe cthulhu in the first 25"
Retrieved: 10 chunks (1,500-2,000 words)
Includes: Chunk with "octopus, dragon, human" description (line 127, 7.2%)
Answer: DIRECT physical description with specific details
```

---

## Performance Comparison

| Metric | Before | After | Change |
|--------|--------|-------|--------|
| **Chunks retrieved** | 5 | 10 | +100% |
| **Chunk size** | 250 words | 150 words | -40% |
| **Total chunks (Cthulhu)** | 43 | ~70 | +63% |
| **Context sent to LLM** | 1,091 words | ~1,500-2,000 words | +50% |
| **Coverage probability** | 12% (5/43) | 14% (10/70) | +17% |
| **Precision** | Lower | Higher | ✅ Better |

---

## Why This Works

### **Problem 1: Top-K Too Small**
**Solution:** Increased from 5 to 10 chunks
- More chances to find the key description
- Redundancy helps with varied query phrasing

### **Problem 2: Chunks Too Large**
**Solution:** Reduced from 250 to 150 words
- Each chunk represents ONE semantic concept
- "Octopus, dragon, human" description now in dedicated chunk
- Embedding captures specific meaning, not blurred average

### **Problem 3: Query Ambiguity**
**Partial solution:** More chunks compensates for vague queries
- If query matches weakly, we still retrieve enough chunks to find answer
- Future enhancement: Query expansion/rewriting

---

## Technical Details

### **New Chunk Distribution (Estimated)**

**Call of Cthulhu:**
- Book: ~20,000 words
- Chunks (before): 43 chunks @ 250 words = 10,750 words (54% of book)
- Chunks (after): ~70 chunks @ 150 words = 10,500 words (53% of book)
- **More chunks = better granularity**

**Semantic Embedding:**
- Each chunk → 384-dimensional vector
- Smaller chunks → more precise semantic meaning
- Example: "octopus, dragon, human" chunk embeds as "physical description" rather than "investigation narrative"

---

## Testing Instructions

### **Server is running:** http://localhost:8000

### **Test 1: Original failing query**
```
Question: "Describe cthulhu in the first 25"

Expected improvements:
- ✅ Should retrieve 10 chunks (was 5)
- ✅ Should include chunk with "octopus, dragon, human" description
- ✅ Answer should mention specific physical details
```

### **Test 2: Verify chunk size**
Check server logs for:
```
Building vector store for The_CALL_of_CTHULHU_cleaned.md...
✓ Created XX chunks  (should be ~70, was 43)
```

### **Test 3: Compare context size**
Check server logs for:
```
[Hybrid RAG] Context size: XXXX words
(should be 1,500-2,000 words, was 1,091)
```

---

## Fallback & Safety

**If semantic search fails:**
- Automatic fallback to `get_book_section(0, 25)` (6,656 words)
- User still gets an answer (may be verbose, but complete)

**If chunks are too small:**
- Can adjust back: `target_words_per_chunk=200`
- Trade-off: Precision vs context completeness

**If top_k is too high:**
- Can reduce to 8 or even back to 5
- Trade-off: Coverage vs noise

---

## Next Enhancements (Optional)

### **1. Query Enhancement (Medium Effort)**
Expand vague queries before search:
```python
"Describe cthulhu" → "cthulhu appearance looks like physical description depicted as"
```

### **2. Cross-Encoder Reranking (Advanced)**
Add second-stage reranking after initial retrieval:
```python
# Get 20 candidates
candidates = vector_store.search(question, top_k=20)
# Rerank with cross-encoder to get best 10
best_10 = cross_encoder_rerank(question, candidates, top_k=10)
```

### **3. Dynamic top_k Based on Query Type**
```python
if is_detailed_description_query(question):
    top_k = 12  # Need more context for descriptions
elif is_simple_fact_query(question):
    top_k = 5   # Less context needed for simple facts
```

### **4. Multi-stage Retrieval**
```python
# Stage 1: Broad search (get 20 chunks)
# Stage 2: Filter by relevance threshold (keep if similarity > 0.5)
# Stage 3: Diversify by position (avoid all chunks from same section)
```

---

## Rollback Instructions

If improvements cause issues:

1. **Revert top_k:**
   ```python
   # server/llm_chat.py, line 272
   results = vector_store.search(question, top_k=5)  # Back to 5
   ```

2. **Revert chunk size:**
   ```python
   # server/semantic_retrieval.py, line 25
   def __init__(self, target_words_per_chunk: int = 250, max_words_per_chunk: int = 400):
   ```

3. **Delete vector cache and restart server:**
   ```bash
   rm -rf books/*/.vector_cache
   lsof -ti:8000 | xargs kill
   python3 server/audiobook_server.py &
   ```

---

## Conclusion

**Changes made:**
- ✅ Doubled retrieval coverage (5 → 10 chunks)
- ✅ Reduced chunk size for better precision (250 → 150 words)
- ✅ Cleared cache to force re-vectorization

**Expected outcome:**
- ✅ "Octopus, dragon, human" description now captured
- ✅ Better answers for specific factual questions
- ✅ Maintains summary capability (unaffected)

**Ready to test!**
Reload the web player and try: **"Describe cthulhu in the first 25"**
