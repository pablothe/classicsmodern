# Feature Roadmap & Implementation Plans

This document tracks planned and in-progress features for the Modern Classics audiobook platform.

---

## 🤖 AI Chat Assistant (In Progress)

**Status:** Planning → Implementation
**Priority:** High
**Target Completion:** TBD

### Overview
Interactive AI assistant that answers questions about the book using local LLM (Ollama llama3.2:3b). Users can ask about any chapter, characters, plot points, or themes while listening.

### Features
- **Tool-Calling LLM**: AI can dynamically request any chapter's text, not just current chapter
- **Context-Aware**: Knows which chapter user is listening to
- **Smart Chapter Retrieval**: Only loads chapters needed to answer question (efficient)
- **Transparent Citations**: Shows which chapters were consulted
- **No Pre-training Required**: Uses source markdown files for accurate context

### Architecture

#### Backend (FastAPI Server)

**New Files:**
1. **`server/llm_chat.py`** - Core LLM integration
   ```python
   class BookTools:
       """Tools available to LLM for querying book content"""

       def __init__(self, book_md_path, chapters_metadata):
           self.book_path = book_md_path
           self.chapters = chapters_metadata

       def get_chapter(self, chapter_num: int) -> str:
           """Retrieve text of specific chapter"""

       def get_chapters(self, start: int, end: int) -> str:
           """Retrieve range of chapters (e.g., 3-5)"""

       def list_chapters(self) -> List[Dict]:
           """Get table of contents with chapter titles"""

       def get_full_book(self) -> str:
           """Retrieve entire book text (warns if > 50k tokens)"""

   def ask_with_tools(
       question: str,
       current_chapter: int,
       tools: BookTools,
       model: str = "llama3.2:3b"
   ) -> Dict:
       """
       Main LLM query handler with tool-calling loop.

       Flow:
       1. Send question + tool definitions to LLM
       2. LLM responds with either:
          - Tool call: [TOOL: get_chapter(5)]
          - Final answer: "In Chapter 5..."
       3. If tool call, execute and send result back to LLM
       4. Repeat until LLM provides final answer (max 5 iterations)

       Returns:
           {
               'answer': str,
               'tools_used': ['get_chapter(5)', 'get_chapter(3)'],
               'iterations': 2,
               'context_tokens': 3500,
               'model': 'llama3.2:3b'
           }
       """

   def check_ollama_available() -> Dict:
       """Health check for Ollama service"""
       # Returns: {'available': bool, 'models': [...], 'error': str?}
   ```

**Modified Files:**
2. **`server/audiobook_server.py`**
   - Add new endpoint: `POST /api/ask`
     ```python
     @app.post("/api/ask")
     async def ask_ai_assistant(request: Request):
         """
         AI assistant endpoint with tool-calling support

         Request Body:
         {
             "book_id": "alice_adventures",
             "variant_id": "...",
             "current_chapter": 3,
             "question": "What happens to Alice in chapter 5?"
         }

         Response:
         {
             "answer": "In Chapter 5...",
             "tools_used": ["get_chapter(5)"],
             "iterations": 1,
             "context_tokens": 2500,
             "current_chapter": 3,
             "chapters_consulted": [5],
             "error": null
         }
         """
     ```

   - Enhance `discover_books()` to track source markdown files:
     ```python
     variant = {
         # ... existing fields ...
         'source_text_path': 'alice_adventures/alices_adventures_cleaned.md',
         'has_source_text': True,
         'chapter_count': 12
     }
     ```

   - Add chapter-to-text mapping in variant metadata

#### Frontend (Web Player)

**Modified Files:**
1. **`server/static/player.html`**
   ```html
   <!-- Add AI button to secondary controls -->
   <div class="secondary-controls-grid" id="secondary-controls-grid">
       <button id="speed-btn" class="secondary-action-btn">...</button>
       <button id="chapters-btn" class="secondary-action-btn">...</button>
       <button id="sleep-timer-btn" class="secondary-action-btn">...</button>

       <!-- NEW: AI Assistant Button -->
       <button id="ai-assistant-btn" class="secondary-action-btn">
           <span class="action-icon">🤖</span>
           <span class="action-label">AI Assistant</span>
       </button>
   </div>

   <!-- AI Chat Panel (hidden by default) -->
   <div id="ai-chat-panel" class="ai-chat-panel" style="display: none;">
       <div class="chat-header">
           <div class="chat-title">
               <span id="chat-book-title">Book Title</span>
               <span id="chat-chapter-info">Currently in Chapter 3</span>
           </div>
           <button id="close-chat-btn" class="close-btn">✕</button>
       </div>

       <div id="chat-messages" class="chat-messages">
           <!-- Messages render here -->
       </div>

       <div id="chat-tools-status" class="chat-tools-status" style="display: none;">
           <span class="spinner">⏳</span>
           <span id="tools-status-text">Loading Chapter 5...</span>
       </div>

       <form id="chat-form" class="chat-form">
           <input
               type="text"
               id="chat-input"
               placeholder="Ask about this book..."
               autocomplete="off"
           />
           <button type="submit" id="chat-submit-btn">Send</button>
       </form>

       <!-- Suggested Questions (optional) -->
       <div class="chat-suggestions">
           <button class="suggestion-btn" data-question="Summarize this chapter">
               Summarize this chapter
           </button>
           <button class="suggestion-btn" data-question="Who are the main characters?">
               Main characters
           </button>
           <button class="suggestion-btn" data-question="What are the key themes?">
               Key themes
           </button>
       </div>
   </div>
   ```

2. **`server/static/player.js`**
   ```javascript
   // Add to state object
   const state = {
       // ... existing fields ...
       chatOpen: false,
       chatHistory: [],
       lastChatClear: Date.now()
   };

   // Chat UI Functions
   function toggleChat() {
       state.chatOpen = !state.chatOpen;
       const chatPanel = document.getElementById('ai-chat-panel');
       const playerContainer = document.querySelector('.player-container');

       if (state.chatOpen) {
           chatPanel.style.display = 'block';
           playerContainer.classList.add('chat-active'); // Resize player to 50%
           updateChatHeader();
       } else {
           chatPanel.style.display = 'none';
           playerContainer.classList.remove('chat-active');
       }
   }

   function updateChatHeader() {
       document.getElementById('chat-book-title').textContent = state.currentBook.title;
       const chapterInfo = state.currentChapterIndex !== null
           ? `Currently in ${state.currentBook.chapters[state.currentChapterIndex].title}`
           : 'No chapter detected';
       document.getElementById('chat-chapter-info').textContent = chapterInfo;
   }

   async function sendChatMessage(question) {
       // Add user message to chat
       displayMessage('user', question);

       // Show loading state
       showToolsLoading('Thinking...');

       try {
           const response = await fetch(`${API.baseURL}/api/ask`, {
               method: 'POST',
               headers: {
                   'Content-Type': 'application/json'
               },
               body: JSON.stringify({
                   book_id: state.currentBook.book_id,
                   variant_id: state.currentVariant.variant_id,
                   current_chapter: state.currentChapterIndex || 0,
                   question: question
               })
           });

           if (!response.ok) {
               const error = await response.json();
               displayMessage('error', error.detail || 'Failed to get response');
               return;
           }

           const data = await response.json();

           // Hide loading
           hideToolsLoading();

           // Display AI response
           displayMessage('assistant', data.answer, {
               tools_used: data.tools_used,
               chapters_consulted: data.chapters_consulted
           });

       } catch (error) {
           hideToolsLoading();
           displayMessage('error', 'Failed to connect to AI assistant. Is Ollama running?');
       }
   }

   function displayMessage(role, text, metadata = {}) {
       const messagesDiv = document.getElementById('chat-messages');
       const messageDiv = document.createElement('div');
       messageDiv.className = `chat-message chat-message-${role}`;

       // Message bubble
       const bubbleDiv = document.createElement('div');
       bubbleDiv.className = 'message-bubble';
       bubbleDiv.textContent = text;
       messageDiv.appendChild(bubbleDiv);

       // Show tools used (if any)
       if (metadata.tools_used && metadata.tools_used.length > 0) {
           const toolsDiv = document.createElement('div');
           toolsDiv.className = 'message-tools';
           toolsDiv.textContent = `✓ Consulted: ${metadata.tools_used.join(', ')}`;
           messageDiv.appendChild(toolsDiv);
       }

       messagesDiv.appendChild(messageDiv);
       messagesDiv.scrollTop = messagesDiv.scrollHeight; // Auto-scroll

       // Store in history
       state.chatHistory.push({ role, text, timestamp: Date.now() });

       // Auto-clear old history (after 3 hours)
       clearOldChatHistory();
   }

   function clearOldChatHistory() {
       const THREE_HOURS = 3 * 60 * 60 * 1000;
       const now = Date.now();

       if (now - state.lastChatClear > THREE_HOURS) {
           state.chatHistory = [];
           document.getElementById('chat-messages').innerHTML = '';
           state.lastChatClear = now;
       }
   }

   function showToolsLoading(text) {
       const statusDiv = document.getElementById('chat-tools-status');
       document.getElementById('tools-status-text').textContent = text;
       statusDiv.style.display = 'flex';
   }

   function hideToolsLoading() {
       document.getElementById('chat-tools-status').style.display = 'none';
   }

   // Event Listeners
   document.getElementById('ai-assistant-btn').addEventListener('click', toggleChat);
   document.getElementById('close-chat-btn').addEventListener('click', toggleChat);

   document.getElementById('chat-form').addEventListener('submit', (e) => {
       e.preventDefault();
       const input = document.getElementById('chat-input');
       const question = input.value.trim();
       if (question) {
           sendChatMessage(question);
           input.value = '';
       }
   });

   // Suggested questions
   document.querySelectorAll('.suggestion-btn').forEach(btn => {
       btn.addEventListener('click', () => {
           const question = btn.dataset.question;
           sendChatMessage(question);
       });
   });

   // Keyboard shortcut: Cmd/Ctrl + K to open chat
   document.addEventListener('keydown', (e) => {
       if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
           e.preventDefault();
           toggleChat();
           if (state.chatOpen) {
               document.getElementById('chat-input').focus();
           }
       }
   });
   ```

3. **`server/static/player.css`** (or inline styles)
   ```css
   /* AI Chat Panel */
   .ai-chat-panel {
       position: fixed;
       bottom: 0;
       left: 0;
       right: 0;
       height: 50%;
       background: #fff;
       border-top: 1px solid #ddd;
       display: flex;
       flex-direction: column;
       z-index: 100;
   }

   .player-container.chat-active {
       height: 50%;
       overflow-y: auto;
   }

   .chat-header {
       padding: 15px;
       border-bottom: 1px solid #eee;
       display: flex;
       justify-content: space-between;
       align-items: center;
   }

   .chat-messages {
       flex: 1;
       overflow-y: auto;
       padding: 15px;
   }

   .chat-message {
       margin-bottom: 15px;
       display: flex;
       flex-direction: column;
   }

   .chat-message-user {
       align-items: flex-end;
   }

   .chat-message-assistant {
       align-items: flex-start;
   }

   .message-bubble {
       max-width: 70%;
       padding: 10px 15px;
       border-radius: 18px;
       background: #f0f0f0;
   }

   .chat-message-user .message-bubble {
       background: #007aff;
       color: white;
   }

   .message-tools {
       font-size: 0.8em;
       color: #666;
       margin-top: 5px;
   }

   .chat-form {
       display: flex;
       padding: 15px;
       border-top: 1px solid #eee;
   }

   .chat-form input {
       flex: 1;
       padding: 10px;
       border: 1px solid #ddd;
       border-radius: 20px;
       margin-right: 10px;
   }

   .chat-tools-status {
       padding: 10px;
       background: #f9f9f9;
       border-top: 1px solid #eee;
       display: flex;
       align-items: center;
       gap: 10px;
   }
   ```

#### Chapter-to-Text Mapping

**Strategy:**
1. During `discover_books()`, detect source markdown file:
   - Priority: `*_cleaned.md` > `*_original.md` > `*.md`
   - Store path in variant metadata: `source_text_path`
2. Parse chapters from markdown using existing `book_preprocessor.py` logic
3. Store chapter boundaries (start/end line numbers or byte offsets)
4. When tool calls `get_chapter(N)`, extract lines from source file

**Fallback:**
- If no source text found, show error: "Source text not available for this book"
- Suggest user upload original markdown file

### Dependencies

**Backend:**
- Add to `requirements.txt`: `ollama>=0.1.0` (Python client)

**System Requirements:**
- Ollama installed and running: `ollama serve`
- Model downloaded: `ollama pull llama3.2:3b` (~2GB)

**Auto-check on startup:**
```python
# In audiobook_server.py startup
try:
    ollama_status = check_ollama_available()
    if not ollama_status['available']:
        print("⚠️  WARNING: Ollama not available. AI Assistant will be disabled.")
        print("   Install: https://ollama.com/download")
        print("   Then run: ollama serve && ollama pull llama3.2:3b")
except Exception as e:
    print(f"⚠️  WARNING: Ollama check failed: {e}")
```

### User Experience Flow

1. **User clicks "🤖 AI Assistant" button**
   - Chat panel slides up from bottom (50% of screen)
   - Player controls move to top 50%
   - Input box auto-focuses

2. **User asks: "What happens to Alice in chapter 5?"**
   - Message appears in chat (right-aligned, blue bubble)
   - Loading indicator: "⏳ Thinking..."

3. **Backend processing:**
   - LLM receives question + tool definitions
   - LLM requests: `get_chapter(5)`
   - Backend extracts Chapter 5 text from markdown
   - Sends back to LLM
   - LLM generates answer

4. **Response appears:**
   ```
   [AI Assistant]
   In Chapter 5 "Advice from a Caterpillar", Alice encounters
   a hookah-smoking caterpillar sitting on a mushroom. The
   caterpillar asks her "Who are you?" and she struggles to
   explain her identity after all her transformations...

   ✓ Consulted: get_chapter(5)
   ```

5. **User can ask follow-up:**
   - "What about chapter 3?"
   - "Summarize the entire book"
   - "Who are the main characters?"

### Error Handling

**Ollama not running:**
```
[Error]
AI Assistant unavailable. Please start Ollama:

1. Install: https://ollama.com/download
2. Run: ollama serve
3. Download model: ollama pull llama3.2:3b
4. Refresh this page
```

**Source text not found:**
```
[Error]
Source text not available for this book. The AI Assistant
needs the original markdown file to answer questions.

Please ensure the book's source file exists in:
books/alice_adventures/*_cleaned.md
```

**LLM timeout (> 30 seconds):**
```
[Error]
The AI is taking too long to respond. This might be because:
- Your question requires analyzing many chapters
- Ollama is running on CPU (very slow)
- The model is still loading

Try a simpler question or check Ollama status.
```

### Testing Checklist

- [ ] Ollama health check on server startup
- [ ] Chat UI opens/closes correctly
- [ ] Current chapter detection works
- [ ] LLM can retrieve any chapter via tools
- [ ] Tool usage displayed in chat
- [ ] Suggested questions work
- [ ] Keyboard shortcut (Cmd+K) works
- [ ] Chat history auto-clears after 3 hours
- [ ] Error handling for all failure modes
- [ ] Works on mobile (responsive layout)
- [ ] Test with multiple books (Alice, Cthulhu, Crime & Punishment)

### Future Enhancements (v2)

- **RAG with vector embeddings** for semantic search across entire book
- **Multi-turn context memory** (remember previous questions)
- **Voice input/output** (speak question, hear answer via TTS)
- **Export chat transcript** as markdown
- **Persistent chat history** per book (stored in playback_db.json)
- **Multiple LLM models** (let user switch: llama3.2:3b, deepseek-r1:7b, etc.)
- **Streaming responses** (show answer as it's being generated)
- **Citation links** (click chapter reference to jump to that chapter in player)

---

## 📖 Karaoke Mode / Text Sync (Planned)

**Status:** Planning
**Priority:** Medium
**Target Completion:** TBD

### Overview
Display the book's text in sync with the audio playback, like karaoke subtitles. Users can read along while listening, with auto-scrolling and word-level highlighting.

### Features
- **Text Display**: Show current paragraph/page being narrated
- **Auto-Scroll**: Text automatically follows audio position
- **Word Highlighting** (stretch goal): Highlight current word being spoken
- **Manual Navigation**: Click on text to jump to that point in audio
- **Toggle On/Off**: Button to show/hide text panel

### UI Design

**Layout:**
```
┌─────────────────────────────────────┐
│  Player Controls (Top 30%)          │
│  🎧 Book Title                      │
│  ━━━━━━●─────────── 12:45 / 45:30  │
│  ▶️  ⏮  ⏭  Speed  🤖 AI  📖 Text   │
└─────────────────────────────────────┘
┌─────────────────────────────────────┐
│  Text Panel (Bottom 70%)            │
│                                     │
│  Chapter 3: A Caucus-Race          │
│                                     │
│  They were indeed a queer-looking  │
│  assembly—the birds with draggled  │
│  feathers, the animals with their  │
│  fur clinging close to them, and   │
│  all dripping wet, cross, and      │
│  uncomfortable.                     │
│                                     │
│  [Current paragraph highlighted]   │
└─────────────────────────────────────┘
```

**Button in secondary controls:**
```html
<button id="text-sync-btn" class="secondary-action-btn">
    <span class="action-icon">📖</span>
    <span class="action-label">Text Sync</span>
</button>
```

### Technical Challenges

#### Challenge 1: Audio-to-Text Synchronization

**Problem:** How to know which word/paragraph corresponds to which audio timestamp?

**Possible Solutions:**

**Option A: Timestamp Metadata (Most Accurate)**
- During TTS generation, store timestamps for each sentence/paragraph
- Example: `{"text": "Alice was beginning...", "start": 0.0, "end": 3.5}`
- Store in JSON file alongside audio: `chapter_01_timestamps.json`
- Pro: Pixel-perfect sync
- Con: Requires modifying TTS pipeline to capture timestamps

**Option B: Estimated Sync (Simpler, Less Accurate)**
- Calculate average speaking rate (words per minute)
- Estimate timestamp based on word position
- Formula: `timestamp = (word_index / total_words) * audio_duration`
- Pro: No TTS changes needed, works with existing audio
- Con: Drift over time (speed varies by sentence complexity)

**Option C: Forced Alignment (Best Quality, Complex)**
- Use speech recognition to align audio with text
- Tools: Aeneas, Gentle, Montreal Forced Aligner
- Generate precise word-level timestamps
- Pro: Works with any audio, very accurate
- Con: Requires additional processing step, CPU-intensive

**Recommendation for MVP:** Start with **Option B** (estimated sync), upgrade to **Option A** (timestamp metadata) in TTS scripts later.

#### Challenge 2: Text Chunking

**How much text to show at once?**

**Option 1: Paragraph-level**
- Show 3-5 paragraphs at a time
- Highlight current paragraph
- Auto-scroll when moving to next paragraph
- Pro: Easy to implement, readable
- Con: Less precise, can't click on specific word

**Option 2: Sentence-level**
- Show current sentence highlighted
- Pro: More precise
- Con: Constant scrolling (distracting)

**Option 3: Page-level (recommended)**
- Show full "page" (500-800 words)
- Highlight current paragraph
- Auto-scroll only when current paragraph goes off-screen
- Pro: Best reading experience, minimal distraction
- Con: Need to calculate page boundaries

**Recommendation:** **Option 3** (page-level with paragraph highlighting)

### Implementation Plan

#### Phase 1: Basic Text Display (MVP)

**Backend Changes:**

1. **Add text content to variant metadata** (`audiobook_server.py`)
   ```python
   variant = {
       # ... existing fields ...
       'source_text_path': 'alice_adventures/alices_adventures_cleaned.md',
       'has_text_sync': True,  # Does this variant have source text?
   }
   ```

2. **New API endpoint: Get text for chapter**
   ```python
   @app.get("/api/books/{book_id}/text/{chapter_num}")
   async def get_chapter_text(book_id: str, chapter_num: int):
       """
       Get markdown text for specific chapter

       Returns:
       {
           "chapter_num": 3,
           "title": "A Caucus-Race and a Long Tale",
           "text": "They were indeed a queer-looking...",
           "paragraphs": [
               {"id": 0, "text": "They were indeed..."},
               {"id": 1, "text": "The first question..."}
           ],
           "word_count": 1250,
           "estimated_duration": 375  // seconds (assuming 200 WPM)
       }
       """
   ```

**Frontend Changes:**

1. **Add "📖 Text Sync" button** to secondary controls (`player.html`)

2. **Add text panel div** (`player.html`)
   ```html
   <div id="text-sync-panel" class="text-sync-panel" style="display: none;">
       <div class="text-header">
           <h3 id="text-chapter-title">Chapter Title</h3>
           <button id="close-text-btn">✕</button>
       </div>

       <div id="text-content" class="text-content">
           <!-- Paragraphs render here -->
           <p class="text-paragraph" data-para-id="0">First paragraph...</p>
           <p class="text-paragraph active" data-para-id="1">Second paragraph (highlighted)...</p>
           <p class="text-paragraph" data-para-id="2">Third paragraph...</p>
       </div>
   </div>
   ```

3. **Text sync logic** (`player.js`)
   ```javascript
   const textSync = {
       enabled: false,
       chapterText: null,
       paragraphs: [],
       currentParagraphIndex: 0,

       async loadChapter(chapterNum) {
           const response = await fetch(
               `${API.baseURL}/api/books/${state.currentBook.book_id}/text/${chapterNum}`
           );
           this.chapterText = await response.json();
           this.renderParagraphs();
       },

       renderParagraphs() {
           const contentDiv = document.getElementById('text-content');
           contentDiv.innerHTML = this.chapterText.paragraphs.map((p, i) => `
               <p class="text-paragraph" data-para-id="${i}">
                   ${p.text}
               </p>
           `).join('');
       },

       updateHighlight(audioTime) {
           // Estimate which paragraph we're in
           const totalDuration = ui.audio.duration;
           const progress = audioTime / totalDuration;
           const paragraphIndex = Math.floor(progress * this.paragraphs.length);

           if (paragraphIndex !== this.currentParagraphIndex) {
               this.currentParagraphIndex = paragraphIndex;
               this.highlightParagraph(paragraphIndex);
           }
       },

       highlightParagraph(index) {
           // Remove previous highlight
           document.querySelectorAll('.text-paragraph').forEach(p => {
               p.classList.remove('active');
           });

           // Add highlight to current paragraph
           const currentPara = document.querySelector(
               `.text-paragraph[data-para-id="${index}"]`
           );
           if (currentPara) {
               currentPara.classList.add('active');
               currentPara.scrollIntoView({ behavior: 'smooth', block: 'center' });
           }
       }
   };

   // Update on audio timeupdate
   ui.audio.addEventListener('timeupdate', () => {
       if (textSync.enabled) {
           textSync.updateHighlight(ui.audio.currentTime);
       }
   });

   // Toggle text sync
   document.getElementById('text-sync-btn').addEventListener('click', () => {
       textSync.enabled = !textSync.enabled;
       const panel = document.getElementById('text-sync-panel');

       if (textSync.enabled) {
           panel.style.display = 'block';
           document.querySelector('.player-container').classList.add('text-sync-active');
           textSync.loadChapter(state.currentChapterIndex);
       } else {
           panel.style.display = 'none';
           document.querySelector('.player-container').classList.remove('text-sync-active');
       }
   });
   ```

4. **Styling** (`player.css`)
   ```css
   .text-sync-panel {
       position: fixed;
       bottom: 0;
       left: 0;
       right: 0;
       height: 70%;
       background: #fafafa;
       border-top: 1px solid #ddd;
       display: flex;
       flex-direction: column;
       z-index: 99;
   }

   .player-container.text-sync-active {
       height: 30%;
   }

   .text-content {
       flex: 1;
       overflow-y: auto;
       padding: 30px;
       font-family: Georgia, serif;
       font-size: 18px;
       line-height: 1.8;
       max-width: 800px;
       margin: 0 auto;
   }

   .text-paragraph {
       margin-bottom: 20px;
       transition: background 0.3s ease;
       padding: 10px;
       border-radius: 5px;
   }

   .text-paragraph.active {
       background: #fff3cd;  /* Yellow highlight */
       border-left: 4px solid #ffc107;
   }

   .text-paragraph:hover {
       cursor: pointer;
       background: #f0f0f0;
   }
   ```

#### Phase 2: Click-to-Seek

**Feature:** User clicks on paragraph → audio jumps to that timestamp

```javascript
// In renderParagraphs()
document.querySelectorAll('.text-paragraph').forEach(para => {
    para.addEventListener('click', () => {
        const paraId = parseInt(para.dataset.paraId);
        const estimatedTime = (paraId / textSync.paragraphs.length) * ui.audio.duration;
        ui.audio.currentTime = estimatedTime;
    });
});
```

#### Phase 3: Accurate Timestamps (Future)

**Option A: Modify TTS Scripts**

Add timestamp capture to `local_tts_kokoro.py`:
```python
def generate_with_timestamps(text, voice):
    """Generate audio and return timestamps for each sentence"""
    sentences = split_into_sentences(text)
    timestamps = []
    current_time = 0.0

    for sentence in sentences:
        audio_data = kokoro.generate(sentence, voice)
        duration = len(audio_data) / sample_rate

        timestamps.append({
            'text': sentence,
            'start': current_time,
            'end': current_time + duration
        })

        current_time += duration

    # Save timestamps alongside audio
    with open(f'{output_file}_timestamps.json', 'w') as f:
        json.dump(timestamps, f, indent=2)

    return audio_data, timestamps
```

**Option B: Forced Alignment (Post-processing)**

Run alignment tool after TTS generation:
```bash
# Using Aeneas (Python library)
python -m aeneas.tools.execute_task \
    chapter_01.mp3 \
    chapter_01.txt \
    "task_language=eng|is_text_type=plain|os_task_file_format=json" \
    chapter_01_sync.json
```

Output: Precise word-level timestamps
```json
{
    "fragments": [
        {"begin": "0.000", "end": "2.340", "text": "Alice was beginning to get very tired"},
        {"begin": "2.340", "end": "5.670", "text": "of sitting by her sister on the bank"}
    ]
}
```

### Advanced Features (v2)

**Word-Level Highlighting:**
- Split paragraphs into individual words
- Highlight current word based on precise timestamps
- Requires forced alignment or word-level TTS timestamps

**Reading Mode Options:**
- Font size adjustment
- Dark mode
- Serif vs sans-serif font
- Reading speed indicator (words/min)

**Bookmarks:**
- Click bookmark icon on paragraph
- Save position for later
- Show bookmarked sections in list

**Dual Language Mode:**
- Show original text + translation side-by-side
- Example: German on left, English on right
- Sync both to audio

### Dependencies

**Backend:**
- No new dependencies for MVP (uses existing markdown files)
- Optional (Phase 3): `aeneas` for forced alignment

**Frontend:**
- No new dependencies (vanilla JS)

### Testing Checklist

- [ ] Text panel opens/closes correctly
- [ ] Current paragraph highlights in sync with audio
- [ ] Auto-scroll keeps highlighted paragraph in view
- [ ] Click on paragraph seeks to correct audio position
- [ ] Works with all books that have source text
- [ ] Graceful degradation if source text missing
- [ ] Mobile responsive (text readable on small screens)
- [ ] Keyboard shortcut to toggle text (e.g., Cmd+T)
- [ ] Test with different chapter structures (short/long paragraphs)

### File Structure After Implementation

```
server/
├── audiobook_server.py (add /api/books/{id}/text/{chapter})
└── static/
    ├── player.html (add text sync panel + button)
    ├── player.js (add textSync object + logic)
    └── player.css (add text panel styles)

books/
└── alice_adventures/
    ├── alices_adventures_cleaned.md (source text)
    └── audio_kokoro/
        ├── chapter_01.mp3
        └── chapter_01_timestamps.json (future, Phase 3)
```

---

## Priority Matrix

| Feature | Status | Priority | Complexity | Dependencies |
|---------|--------|----------|-----------|--------------|
| AI Chat Assistant | Planning → Implementation | High | Medium | Ollama, llama3.2:3b |
| Karaoke/Text Sync (Basic) | Planning | Medium | Low | Source markdown files |
| Karaoke/Text Sync (Accurate) | Future | Low | High | TTS timestamp capture or forced alignment |
| AI with RAG/Vector DB | Future | Low | High | ChromaDB, embeddings model |
| Voice Q&A (speak questions) | Future | Low | Medium | Web Speech API, browser TTS |

---

## Notes for Parallel Implementation

Since you're implementing both features in parallel:

### Shared Components
- Both features need access to source markdown files
- Both modify the player layout (split screen)
- Both add buttons to secondary controls

### Avoid Conflicts
- **UI Layout**: Decide if both can be open simultaneously or mutually exclusive
  - Recommendation: Mutually exclusive (either chat OR text sync, not both)
  - When user clicks AI button while text sync is open → close text sync, open chat

- **State Management**: Add feature flags to state object
  ```javascript
  const state = {
      chatOpen: false,
      textSyncOpen: false,
      // Only one can be true at a time
  };
  ```

- **CSS Classes**: Use different classes
  - Chat: `.chat-active`
  - Text Sync: `.text-sync-active`

### Integration Points
- Both features could share the same text extraction backend
- Later: AI could reference text sync position in answers
  - "You're currently reading about Alice meeting the Caterpillar..."

---

## Getting Started

### For AI Chat Assistant:
1. Install Ollama: https://ollama.com/download
2. Run: `ollama serve`
3. Download model: `ollama pull llama3.2:3b`
4. Add `ollama` to `requirements.txt`
5. Implement `server/llm_chat.py`
6. Add `/api/ask` endpoint
7. Build frontend chat UI

### For Karaoke/Text Sync:
1. Ensure source markdown files exist in `books/*/`
2. Add `/api/books/{id}/text/{chapter}` endpoint
3. Build text panel UI
4. Implement paragraph highlighting logic
5. Test sync accuracy, adjust algorithm

Good luck with the implementation! 🚀
