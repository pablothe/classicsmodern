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

        // Create word spans
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
     * Binary search to find word at given time
     */
    findWordAtTime(time) {
        const words = this.currentChapter.words;

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

        // If exact match not found, return closest word
        if (left >= words.length) {
            return words.length - 1;
        }
        if (right < 0) {
            return 0;
        }

        // Return the word whose start time is closest
        return left;
    }

    /**
     * Highlight a specific word
     */
    highlightWord(wordIndex) {
        if (!this.textContainer) return;

        const wordSpans = this.textContainer.querySelectorAll('.karaoke-word');

        wordSpans.forEach((span, index) => {
            span.classList.remove('karaoke-current', 'karaoke-past');

            if (index === wordIndex) {
                span.classList.add('karaoke-current');
            } else if (index < wordIndex) {
                span.classList.add('karaoke-past');
            }
        });

        // Auto-scroll to keep current word in view
        if (wordSpans[wordIndex]) {
            this.scrollToWord(wordSpans[wordIndex]);
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
        if (this.textContainer) {
            const wordSpans = this.textContainer.querySelectorAll('.karaoke-word');
            wordSpans.forEach(span => {
                span.removeEventListener('click', this.onWordClick);
            });
            this.textContainer = null;
        }
    }
}

// Export for use in player.js
window.KaraokeSync = KaraokeSync;
