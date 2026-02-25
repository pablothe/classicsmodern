/**
 * Book Reader - Fullscreen reading mode with e-reader controls
 *
 * Features:
 * - Fullscreen overlay that coexists with audio player
 * - Continuous scroll across chapters with lazy loading
 * - Font size, font family, line height, theme controls
 * - Floating mini audio player
 * - Karaoke sync integration
 * - LocalStorage persistence for preferences and scroll position
 */

class BookReader {
    constructor() {
        this.bookId = null;
        this.totalChapters = 0;
        this.loadedChapters = new Set();
        this.chapterData = {};
        this.isOpen = false;
        this.currentVisibleChapter = 0;
        this.observer = null;
        this.scrollSaveTimeout = null;
        this.trackId = null;

        // Default preferences
        this.prefs = {
            fontSize: 18,
            fontFamily: 'Georgia, serif',
            lineHeight: 1.8,
            theme: 'light'
        };

        this.loadPreferences();
    }

    // ========================================================================
    // Open / Close
    // ========================================================================

    async open(bookId, startChapter = 0, totalChapters = 0, trackId = null) {
        this.bookId = bookId;
        this.totalChapters = totalChapters;
        this.trackId = trackId;
        this.loadedChapters = new Set();
        this.chapterData = {};

        const overlay = document.getElementById('reader-overlay');
        if (!overlay) return;

        overlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        this.isOpen = true;

        this.applyPreferences();
        this.setupIntersectionObserver();
        this.bindEvents();

        // Load starting chapter and adjacent ones
        const content = document.getElementById('reader-content');
        content.innerHTML = '';

        // Create placeholders for all chapters
        for (let i = 0; i < this.totalChapters; i++) {
            const section = document.createElement('div');
            section.className = 'reader-chapter-section';
            section.id = `reader-chapter-${i}`;
            section.dataset.chapter = i;
            section.innerHTML = '<div class="reader-chapter-loading">Loading...</div>';
            content.appendChild(section);
        }

        // Load initial chapters
        await this.loadChapter(startChapter);
        this.loadAdjacentChapters(startChapter);

        // Scroll to the starting chapter
        this.scrollToChapter(startChapter, false);

        // Try to restore scroll position
        this.restoreScrollPosition();

        // Update mini player state
        this.updateMiniPlayer();
    }

    close() {
        const overlay = document.getElementById('reader-overlay');
        if (!overlay) return;

        this.saveScrollPosition();
        overlay.classList.add('hidden');
        document.body.style.overflow = '';
        this.isOpen = false;

        if (this.observer) {
            this.observer.disconnect();
            this.observer = null;
        }

        this.unbindEvents();
    }

    // ========================================================================
    // Chapter Loading
    // ========================================================================

    async loadChapter(index) {
        if (index < 0 || index >= this.totalChapters) return;
        if (this.loadedChapters.has(index)) return;

        this.loadedChapters.add(index);

        try {
            const trackParam = this.trackId ? `?track_id=${encodeURIComponent(this.trackId)}` : '';
            const response = await fetch(`/api/books/${this.bookId}/text/${index}${trackParam}`);
            if (!response.ok) {
                this.renderChapterError(index, 'Text not available');
                return;
            }

            const data = await response.json();
            this.chapterData[index] = data;
            this.renderChapter(data, index);
        } catch (error) {
            console.error(`Failed to load chapter ${index}:`, error);
            this.renderChapterError(index, error.message);
        }
    }

    renderChapter(data, index) {
        const section = document.getElementById(`reader-chapter-${index}`);
        if (!section) return;

        const title = data.title || `Chapter ${index + 1}`;
        const wordCount = data.word_count || 0;
        const readTime = Math.ceil(wordCount / 250); // ~250 wpm average reading speed

        section.innerHTML = `
            <div class="reader-chapter-divider" data-observe="${index}">
                <h2 class="reader-chapter-heading">${this.escapeHtml(title)}</h2>
                <span class="reader-chapter-meta">${wordCount.toLocaleString()} words · ~${readTime} min read</span>
            </div>
            <div class="reader-chapter-text">
                ${data.paragraphs.map(p => `
                    <p class="reader-paragraph" data-chapter="${index}" data-para-id="${p.id}">${this.escapeHtml(p.text)}</p>
                `).join('')}
            </div>
        `;

        // Add paragraph click handlers
        section.querySelectorAll('.reader-paragraph').forEach(para => {
            para.addEventListener('click', () => {
                const chapterIdx = parseInt(para.dataset.chapter);
                const paraId = parseInt(para.dataset.paraId);
                this.onParagraphClick(chapterIdx, paraId);
            });
        });

        // Observe chapter divider for visibility tracking
        const divider = section.querySelector('[data-observe]');
        if (divider && this.observer) {
            this.observer.observe(divider);
        }
    }

    renderChapterError(index, message) {
        const section = document.getElementById(`reader-chapter-${index}`);
        if (!section) return;

        section.innerHTML = `
            <div class="reader-chapter-divider">
                <h2 class="reader-chapter-heading">Chapter ${index + 1}</h2>
            </div>
            <div class="reader-chapter-error">${this.escapeHtml(message)}</div>
        `;
    }

    loadAdjacentChapters(centerIndex) {
        // Load prev and next chapters
        if (centerIndex > 0) this.loadChapter(centerIndex - 1);
        if (centerIndex < this.totalChapters - 1) this.loadChapter(centerIndex + 1);
    }

    // ========================================================================
    // Scroll & Navigation
    // ========================================================================

    setupIntersectionObserver() {
        if (this.observer) this.observer.disconnect();

        const content = document.getElementById('reader-content');
        this.observer = new IntersectionObserver((entries) => {
            for (const entry of entries) {
                if (entry.isIntersecting) {
                    const chapterIdx = parseInt(entry.target.dataset.observe);
                    if (!isNaN(chapterIdx)) {
                        this.currentVisibleChapter = chapterIdx;
                        this.updateToolbarTitle(chapterIdx);
                        this.loadAdjacentChapters(chapterIdx);
                    }
                }
            }
        }, {
            root: content,
            rootMargin: '0px',
            threshold: 0.1
        });
    }

    scrollToChapter(index, smooth = true) {
        const section = document.getElementById(`reader-chapter-${index}`);
        if (!section) return;

        const content = document.getElementById('reader-content');
        content.scrollTo({
            top: section.offsetTop - 60, // account for toolbar
            behavior: smooth ? 'smooth' : 'instant'
        });
    }

    saveScrollPosition() {
        if (!this.bookId) return;
        const content = document.getElementById('reader-content');
        if (!content) return;

        const scrollData = {
            chapterIndex: this.currentVisibleChapter,
            scrollTop: content.scrollTop,
            scrollHeight: content.scrollHeight
        };

        localStorage.setItem(`reader_scroll_${this.bookId}`, JSON.stringify(scrollData));
    }

    restoreScrollPosition() {
        if (!this.bookId) return;
        const saved = localStorage.getItem(`reader_scroll_${this.bookId}`);
        if (!saved) return;

        try {
            const data = JSON.parse(saved);
            const content = document.getElementById('reader-content');
            if (content && data.scrollTop) {
                // Wait for chapters to render, then restore
                requestAnimationFrame(() => {
                    content.scrollTop = data.scrollTop;
                });
            }
        } catch (e) {
            // Ignore invalid saved data
        }
    }

    onScroll() {
        // Save position periodically while scrolling
        clearTimeout(this.scrollSaveTimeout);
        this.scrollSaveTimeout = setTimeout(() => this.saveScrollPosition(), 1000);
    }

    // ========================================================================
    // Settings / Preferences
    // ========================================================================

    setFontSize(px) {
        this.prefs.fontSize = Math.max(12, Math.min(32, px));
        this.applyPreferences();
        this.savePreferences();
    }

    setFontFamily(family) {
        this.prefs.fontFamily = family;
        this.applyPreferences();
        this.savePreferences();
    }

    setLineHeight(value) {
        this.prefs.lineHeight = parseFloat(value);
        this.applyPreferences();
        this.savePreferences();
    }

    setTheme(theme) {
        this.prefs.theme = theme;
        this.applyPreferences();
        this.savePreferences();
    }

    applyPreferences() {
        const overlay = document.getElementById('reader-overlay');
        if (!overlay) return;

        const content = document.getElementById('reader-content');
        if (content) {
            content.style.fontSize = `${this.prefs.fontSize}px`;
            content.style.fontFamily = this.prefs.fontFamily;
            content.style.lineHeight = this.prefs.lineHeight;
        }

        // Apply theme
        overlay.classList.remove('reader-theme-light', 'reader-theme-sepia', 'reader-theme-dark');
        overlay.classList.add(`reader-theme-${this.prefs.theme}`);

        // Update settings UI
        const fontSizeDisplay = document.getElementById('reader-font-size-display');
        if (fontSizeDisplay) fontSizeDisplay.textContent = this.prefs.fontSize;

        const fontSelect = document.getElementById('reader-font-select');
        if (fontSelect) fontSelect.value = this.prefs.fontFamily;

        const lineHeightSlider = document.getElementById('reader-line-height');
        if (lineHeightSlider) lineHeightSlider.value = this.prefs.lineHeight;

        // Update theme button active states
        document.querySelectorAll('.reader-theme-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.theme === this.prefs.theme);
        });
    }

    savePreferences() {
        localStorage.setItem('reader_prefs', JSON.stringify(this.prefs));
    }

    loadPreferences() {
        const saved = localStorage.getItem('reader_prefs');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                Object.assign(this.prefs, parsed);
            } catch (e) {
                // Use defaults
            }
        }
    }

    // ========================================================================
    // Toolbar
    // ========================================================================

    updateToolbarTitle(chapterIndex) {
        const titleEl = document.getElementById('reader-chapter-title');
        if (!titleEl) return;

        const data = this.chapterData[chapterIndex];
        if (data) {
            titleEl.textContent = data.title || `Chapter ${chapterIndex + 1}`;
        } else {
            titleEl.textContent = `Chapter ${chapterIndex + 1}`;
        }
    }

    toggleSettings() {
        const panel = document.getElementById('reader-settings');
        if (panel) panel.classList.toggle('hidden');
    }

    // ========================================================================
    // Chapter Navigation Dropdown
    // ========================================================================

    toggleChapterNav() {
        const dropdown = document.getElementById('reader-chapter-nav');
        if (!dropdown) return;

        if (dropdown.classList.contains('hidden')) {
            // Build chapter list
            dropdown.innerHTML = '';
            for (let i = 0; i < this.totalChapters; i++) {
                const data = this.chapterData[i];
                const title = data ? (data.title || `Chapter ${i + 1}`) : `Chapter ${i + 1}`;
                const item = document.createElement('button');
                item.className = 'reader-chapter-nav-item';
                if (i === this.currentVisibleChapter) item.classList.add('active');
                item.textContent = title;
                item.addEventListener('click', () => {
                    this.loadChapter(i).then(() => {
                        this.scrollToChapter(i);
                        dropdown.classList.add('hidden');
                    });
                });
                dropdown.appendChild(item);
            }
            dropdown.classList.remove('hidden');
        } else {
            dropdown.classList.add('hidden');
        }
    }

    // ========================================================================
    // Audio Integration
    // ========================================================================

    onParagraphClick(chapterIndex, paraId) {
        // Dispatch event so player.js can handle seeking
        const event = new CustomEvent('reader-seek', {
            detail: { chapterIndex, paraId }
        });
        document.dispatchEvent(event);
    }

    updateMiniPlayer() {
        const audio = document.getElementById('audio-player');
        const playBtn = document.getElementById('reader-play-pause');
        if (!audio || !playBtn) return;

        playBtn.textContent = audio.paused ? '\u25B6' : '\u275A\u275A';
    }

    updateMiniPlayerInfo(chapterName) {
        const nowPlaying = document.getElementById('reader-now-playing');
        if (nowPlaying && chapterName) {
            nowPlaying.textContent = chapterName;
        }
    }

    highlightCurrentParagraph(chapterIndex, paraId) {
        if (!this.isOpen) return;

        // Remove previous highlight
        document.querySelectorAll('.reader-paragraph.reader-active').forEach(p => {
            p.classList.remove('reader-active');
        });

        // Highlight current
        const para = document.querySelector(
            `.reader-paragraph[data-chapter="${chapterIndex}"][data-para-id="${paraId}"]`
        );
        if (para) {
            para.classList.add('reader-active');
        }
    }

    // ========================================================================
    // Events
    // ========================================================================

    bindEvents() {
        this._onClose = () => this.close();
        this._onSettings = () => this.toggleSettings();
        this._onChapterNav = () => this.toggleChapterNav();
        this._onScroll = () => this.onScroll();

        this._onFontSizeChange = (e) => {
            const delta = parseInt(e.target.dataset.delta);
            if (!isNaN(delta)) this.setFontSize(this.prefs.fontSize + delta);
        };

        this._onFontFamilyChange = (e) => {
            this.setFontFamily(e.target.value);
        };

        this._onLineHeightChange = (e) => {
            this.setLineHeight(e.target.value);
        };

        this._onThemeChange = (e) => {
            const theme = e.target.closest('[data-theme]')?.dataset.theme;
            if (theme) this.setTheme(theme);
        };

        this._onPlayPause = () => {
            const audio = document.getElementById('audio-player');
            if (audio) {
                if (audio.paused) audio.play();
                else audio.pause();
            }
        };

        this._onAudioStateChange = () => this.updateMiniPlayer();

        this._onKeydown = (e) => {
            if (!this.isOpen) return;
            if (e.key === 'Escape') {
                // Close settings first if open, otherwise close reader
                const settings = document.getElementById('reader-settings');
                const chapterNav = document.getElementById('reader-chapter-nav');
                if (settings && !settings.classList.contains('hidden')) {
                    settings.classList.add('hidden');
                } else if (chapterNav && !chapterNav.classList.contains('hidden')) {
                    chapterNav.classList.add('hidden');
                } else {
                    this.close();
                }
            }
        };

        document.getElementById('reader-close-btn')?.addEventListener('click', this._onClose);
        document.getElementById('reader-settings-btn')?.addEventListener('click', this._onSettings);
        document.getElementById('reader-chapter-nav-btn')?.addEventListener('click', this._onChapterNav);
        document.getElementById('reader-content')?.addEventListener('scroll', this._onScroll);
        document.getElementById('reader-play-pause')?.addEventListener('click', this._onPlayPause);

        document.querySelectorAll('.reader-font-size-btn').forEach(btn => {
            btn.addEventListener('click', this._onFontSizeChange);
        });

        document.getElementById('reader-font-select')?.addEventListener('change', this._onFontFamilyChange);
        document.getElementById('reader-line-height')?.addEventListener('input', this._onLineHeightChange);

        document.querySelectorAll('.reader-theme-btn').forEach(btn => {
            btn.addEventListener('click', this._onThemeChange);
        });

        const audio = document.getElementById('audio-player');
        if (audio) {
            audio.addEventListener('play', this._onAudioStateChange);
            audio.addEventListener('pause', this._onAudioStateChange);
        }

        document.addEventListener('keydown', this._onKeydown);
    }

    unbindEvents() {
        document.getElementById('reader-close-btn')?.removeEventListener('click', this._onClose);
        document.getElementById('reader-settings-btn')?.removeEventListener('click', this._onSettings);
        document.getElementById('reader-chapter-nav-btn')?.removeEventListener('click', this._onChapterNav);
        document.getElementById('reader-content')?.removeEventListener('scroll', this._onScroll);
        document.getElementById('reader-play-pause')?.removeEventListener('click', this._onPlayPause);

        document.querySelectorAll('.reader-font-size-btn').forEach(btn => {
            btn.removeEventListener('click', this._onFontSizeChange);
        });

        document.getElementById('reader-font-select')?.removeEventListener('change', this._onFontFamilyChange);
        document.getElementById('reader-line-height')?.removeEventListener('input', this._onLineHeightChange);

        document.querySelectorAll('.reader-theme-btn').forEach(btn => {
            btn.removeEventListener('click', this._onThemeChange);
        });

        const audio = document.getElementById('audio-player');
        if (audio) {
            audio.removeEventListener('play', this._onAudioStateChange);
            audio.removeEventListener('pause', this._onAudioStateChange);
        }

        document.removeEventListener('keydown', this._onKeydown);
    }

    // ========================================================================
    // Utility
    // ========================================================================

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Export
window.BookReader = BookReader;
