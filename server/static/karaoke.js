/**
 * Karaoke Sync - Word-level highlighting synchronized with audio playback
 *
 * Features:
 * - Real-time word highlighting based on audio timestamp
 * - Bidirectional sync (click word → seek audio, audio → highlight text)
 * - Auto-scroll to keep current word centered
 * - Save exact word position for resumable playback
 */

class KaraokeSync {
    constructor(audioElement) {
        this.audio = audioElement;
        this.wordTimings = null;
        this.currentChapter = null;
        this.currentWordIndex = 0;
        this.textContainer = null;
        this.isEnabled = false;
        this.wordSpans = [];  // Direct references for O(1) highlight updates

        // Bind event handlers
        this.onTimeUpdate = this.onTimeUpdate.bind(this);
        this.onWordClick = this.onWordClick.bind(this);
    }

    /**
     * Load word timing data for a book
     */
    async loadWordTimings(bookId) {
        try {
            const response = await fetch(`/api/books/${bookId}/word-timings`);
            if (!response.ok) {
                console.log('Word timings not available for this book');
                return false;
            }

            const data = await response.json();
            this.wordTimings = data.chapters;
            console.log('✓ Loaded word timings:', Object.keys(this.wordTimings).length, 'chapters');
            return true;
        } catch (error) {
            console.error('Failed to load word timings:', error);
            return false;
        }
    }

    /**
     * Set the chapter to sync with
     */
    setChapter(chapterNumber) {
        if (!this.wordTimings) {
            console.warn('Word timings not loaded');
            return false;
        }

        const chapterKey = `chapter_${chapterNumber}`;
        if (!this.wordTimings[chapterKey]) {
            console.warn(`Chapter ${chapterNumber} not found in word timings`);
            return false;
        }

        this.currentChapter = this.wordTimings[chapterKey];
        this.currentWordIndex = 0;

        console.log(`✓ Set karaoke chapter ${chapterNumber} (${this.currentChapter.word_count} words)`);
        return true;
    }

    /**
     * Render text with word-level spans for highlighting
     */
    renderText(textContainer) {
        if (!this.currentChapter) {
            console.warn('No chapter set');
            return;
        }

        this.textContainer = textContainer;
        this.textContainer.innerHTML = '';
        this.wordSpans = [];

        // Create word spans with direct references for O(1) highlighting
        const words = this.currentChapter.words;
        words.forEach((wordData, index) => {
            const wordSpan = document.createElement('span');
            wordSpan.className = 'karaoke-word';
            wordSpan.textContent = wordData.word;
            wordSpan.dataset.index = index;
            wordSpan.dataset.start = wordData.start;
            wordSpan.dataset.end = wordData.end;
            wordSpan.dataset.textPos = wordData.text_pos || 0;

            // Click to seek
            wordSpan.addEventListener('click', this.onWordClick);

            this.textContainer.appendChild(wordSpan);
            this.wordSpans.push(wordSpan);

            // Add space after word (except last word)
            if (index < words.length - 1) {
                this.textContainer.appendChild(document.createTextNode(' '));
            }
        });

        console.log(`✓ Rendered ${words.length} words for karaoke sync`);
    }

    /**
     * Enable karaoke sync (start listening to audio events)
     */
    enable() {
        if (!this.currentChapter) {
            console.warn('Cannot enable karaoke: no chapter set');
            return false;
        }

        this.isEnabled = true;
        this.audio.addEventListener('timeupdate', this.onTimeUpdate);
        console.log('✓ Karaoke sync enabled');
        return true;
    }

    /**
     * Disable karaoke sync
     */
    disable() {
        this.isEnabled = false;
        this.audio.removeEventListener('timeupdate', this.onTimeUpdate);
        console.log('✓ Karaoke sync disabled');
    }

    /**
     * Handle audio timeupdate event - highlight current word
     */
    onTimeUpdate() {
        if (!this.isEnabled || !this.currentChapter || !this.textContainer) {
            return;
        }

        const currentTime = this.audio.currentTime;
        const words = this.currentChapter.words;

        // Find the word at current time using binary search
        let wordIndex = this.findWordAtTime(currentTime);

        if (wordIndex !== this.currentWordIndex) {
            this.highlightWord(wordIndex);
            this.currentWordIndex = wordIndex;
        }
    }

    /**
     * Binary search to find word at given time.
     * Handles gaps between words (silence/pauses) by returning the nearest word.
     */
    findWordAtTime(time) {
        const words = this.currentChapter.words;
        if (!words.length) return 0;

        let left = 0;
        let right = words.length - 1;

        while (left <= right) {
            const mid = Math.floor((left + right) / 2);
            const word = words[mid];

            if (time >= word.start && time <= word.end) {
                return mid;
            } else if (time < word.start) {
                right = mid - 1;
            } else {
                left = mid + 1;
            }
        }

        // No exact match - time falls in a gap between words or at boundaries
        if (left >= words.length) return words.length - 1;
        if (right < 0) return 0;

        // Compare distance to both neighboring words and return the closer one
        const distToLeft = Math.abs(words[left].start - time);
        const distToRight = Math.abs(time - words[right].end);
        return distToRight <= distToLeft ? right : left;
    }

    /**
     * Highlight a specific word - O(1) by only updating changed spans
     */
    highlightWord(wordIndex) {
        if (!this.textContainer || !this.wordSpans.length) return;

        const prevIndex = this.currentWordIndex;

        // Remove current highlight from previous word
        if (prevIndex >= 0 && prevIndex < this.wordSpans.length) {
            this.wordSpans[prevIndex].classList.remove('karaoke-current');
            this.wordSpans[prevIndex].classList.add('karaoke-past');
        }

        // Add highlight to new word
        if (wordIndex >= 0 && wordIndex < this.wordSpans.length) {
            this.wordSpans[wordIndex].classList.remove('karaoke-past');
            this.wordSpans[wordIndex].classList.add('karaoke-current');
            this.scrollToWord(this.wordSpans[wordIndex]);
        }

        // If jumping backward (seek), clear future words' past class
        if (wordIndex < prevIndex) {
            for (let i = wordIndex + 1; i <= prevIndex && i < this.wordSpans.length; i++) {
                this.wordSpans[i].classList.remove('karaoke-past');
            }
        }
    }

    /**
     * Scroll to keep a word visible and centered
     */
    scrollToWord(wordElement) {
        if (!wordElement || !this.textContainer) return;

        // Get container and word positions
        const containerRect = this.textContainer.getBoundingClientRect();
        const wordRect = wordElement.getBoundingClientRect();

        // Check if word is already in center third of container
        const centerStart = containerRect.top + containerRect.height / 3;
        const centerEnd = containerRect.top + (2 * containerRect.height) / 3;

        if (wordRect.top >= centerStart && wordRect.bottom <= centerEnd) {
            // Already visible in center, no need to scroll
            return;
        }

        // Scroll to center the word
        const containerScrollTop = this.textContainer.scrollTop;
        const wordOffsetTop = wordElement.offsetTop;
        const targetScroll = wordOffsetTop - (containerRect.height / 2) + (wordRect.height / 2);

        this.textContainer.scrollTo({
            top: targetScroll,
            behavior: 'smooth'
        });
    }

    /**
     * Handle word click - seek audio to that word
     */
    onWordClick(event) {
        const wordSpan = event.target;
        const startTime = parseFloat(wordSpan.dataset.start);

        if (!isNaN(startTime)) {
            this.audio.currentTime = startTime;
            console.log(`Seeked to word "${wordSpan.textContent}" at ${startTime.toFixed(2)}s`);
        }
    }

    /**
     * Get current word index (for saving position)
     */
    getCurrentWordIndex() {
        return this.currentWordIndex;
    }

    /**
     * Seek to a specific word index
     */
    seekToWordIndex(wordIndex) {
        if (!this.currentChapter || wordIndex < 0 || wordIndex >= this.currentChapter.words.length) {
            return;
        }

        const word = this.currentChapter.words[wordIndex];
        this.audio.currentTime = word.start;
        this.currentWordIndex = wordIndex;
        this.highlightWord(wordIndex);
    }

    /**
     * Clean up resources
     */
    destroy() {
        this.disable();
        this.wordSpans.forEach(span => {
            span.removeEventListener('click', this.onWordClick);
        });
        this.wordSpans = [];
        this.textContainer = null;
    }
}

// Export for use in player.js
window.KaraokeSync = KaraokeSync;
