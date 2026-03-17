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
        this.hasAudio = false;
        this.audioSyncEnabled = false;
        this.inlineMode = false;
        this.inlineContainer = null;
        this.inlineObserver = null;

        // Default preferences
        this.prefs = {
            fontSize: 18,
            fontFamily: 'Georgia, serif',
            lineHeight: 1.8,
            theme: 'light',
            audioSync: false
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
        this.inlineMode = false;
        this.inlineContainer = null;

        const overlay = document.getElementById('reader-overlay');
        if (!overlay) return;

        overlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        this.isOpen = true;

        // Show back arrow instead of × when opened from player tab
        const closeBtn = document.getElementById('reader-close-btn');
        if (closeBtn) {
            closeBtn.textContent = this.openedFromPlayerTab ? '←' : '×';
        }

        // Sync reader theme with global dark mode
        const globalDark = document.documentElement.classList.contains('dark-mode');
        if (globalDark && this.prefs.theme === 'light') {
            this.prefs.theme = 'dark';
        } else if (!globalDark && this.prefs.theme === 'dark') {
            this.prefs.theme = 'light';
        }

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

        // Detect whether THIS book has audio (not just any audio playing)
        const bookData = window._appState?.books?.find(b => b.book_id === bookId);
        this.hasAudio = !!(bookData && bookData.has_audio && bookData.variants?.length > 0);

        // Show/hide sync button
        const syncBtn = document.getElementById('reader-audio-sync-btn');
        if (syncBtn) {
            syncBtn.classList.toggle('active', this.audioSyncEnabled);
        }

        // Show translation banner if text not in preferred language
        this.checkTranslationBanner();

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
        this.openedFromPlayerTab = false;

        if (this.observer) {
            this.observer.disconnect();
            this.observer = null;
        }

        this.unbindEvents();
        document.dispatchEvent(new CustomEvent('reader-closed'));
    }

    // ========================================================================
    // Inline Mode (for split-view panel)
    // ========================================================================

    async openInline(bookId, startChapter, totalChapters, trackId, targetContentEl) {
        this.bookId = bookId;
        this.totalChapters = totalChapters;
        this.trackId = trackId;
        this.loadedChapters = new Set();
        this.chapterData = {};
        this.inlineMode = true;
        this.inlineContainer = targetContentEl;
        this.isOpen = true;

        // Detect whether this book has audio
        const bookData = window._appState?.books?.find(b => b.book_id === bookId);
        this.hasAudio = !!(bookData && bookData.has_audio && bookData.variants?.length > 0);

        // Enable audio sync by default in inline mode when audio is available
        if (this.hasAudio) {
            this.audioSyncEnabled = true;
        }

        // Don't open fullscreen overlay — render into target container
        targetContentEl.innerHTML = '';

        // Create chapter placeholders
        for (let i = 0; i < totalChapters; i++) {
            const section = document.createElement('div');
            section.className = 'reader-chapter-section';
            section.id = `reader-chapter-${i}`;
            section.dataset.chapter = i;
            section.innerHTML = '<div class="reader-chapter-loading" style="padding: 2rem; text-align: center; color: var(--text-secondary);">Loading...</div>';
            targetContentEl.appendChild(section);
        }

        // Apply reading preferences to inline container
        targetContentEl.style.fontFamily = this.prefs.fontFamily;
        targetContentEl.style.fontSize = this.prefs.fontSize + 'px';
        targetContentEl.style.lineHeight = this.prefs.lineHeight;

        // Load initial chapters
        await this.loadChapter(startChapter);
        this.loadAdjacentChapters(startChapter);

        // Setup intersection observer for lazy loading
        this.setupInlineObserver(targetContentEl);
    }

    setupInlineObserver(container) {
        if (this.inlineObserver) this.inlineObserver.disconnect();

        this.inlineObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const chapterIdx = parseInt(entry.target.dataset.chapter);
                    if (!isNaN(chapterIdx)) {
                        this.loadChapter(chapterIdx);
                        this.loadAdjacentChapters(chapterIdx);
                    }
                }
            });
        }, {
            root: container,
            rootMargin: '200px',
            threshold: 0.01
        });

        container.querySelectorAll('.reader-chapter-section').forEach(section => {
            this.inlineObserver.observe(section);
        });
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
        // Find section in the correct container (inline or overlay)
        const container = this.inlineMode ? this.inlineContainer : document.getElementById('reader-content');
        const section = container?.querySelector(`[data-chapter="${index}"]`);
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
                    <p class="reader-paragraph" data-chapter="${index}" data-para-id="${p.para_id || p.id}">${this.renderMarkdown(p.text)}</p>
                `).join('')}
            </div>
        `;

        // Add paragraph click handlers
        section.querySelectorAll('.reader-paragraph').forEach(para => {
            para.addEventListener('click', () => {
                const chapterIdx = parseInt(para.dataset.chapter);
                const paraId = para.dataset.paraId;
                this.onParagraphClick(chapterIdx, paraId);
            });
        });

        // Observe chapter divider for visibility tracking
        const divider = section.querySelector('[data-observe]');
        const activeObserver = this.inlineMode ? this.inlineObserver : this.observer;
        if (divider && activeObserver) {
            activeObserver.observe(divider);
        }
    }

    renderChapterError(index, message) {
        const container = this.inlineMode ? this.inlineContainer : document.getElementById('reader-content');
        const section = container?.querySelector(`[data-chapter="${index}"]`);
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

    /**
     * Set up lazy-loading via IntersectionObserver.
     * Each chapter section has a data-observe sentinel. When a sentinel
     * enters the viewport (10% threshold), we update the toolbar title
     * and pre-load adjacent chapters so content is ready before the
     * user scrolls to it.
     */
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

        // Update fullscreen overlay content
        if (overlay) {
            const content = document.getElementById('reader-content');
            if (content) {
                content.style.fontSize = `${this.prefs.fontSize}px`;
                content.style.fontFamily = this.prefs.fontFamily;
                content.style.lineHeight = this.prefs.lineHeight;
            }

            // Apply theme
            overlay.classList.remove('reader-theme-light', 'reader-theme-sepia', 'reader-theme-dark');
            overlay.classList.add(`reader-theme-${this.prefs.theme}`);

            // Update overlay settings UI
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

        // Update inline container (split view)
        if (this.inlineMode && this.inlineContainer) {
            this.inlineContainer.style.fontSize = `${this.prefs.fontSize}px`;
            this.inlineContainer.style.fontFamily = this.prefs.fontFamily;
            this.inlineContainer.style.lineHeight = this.prefs.lineHeight;
        }

        // Update split-view settings UI
        const splitFontSize = document.getElementById('split-font-size-display');
        if (splitFontSize) splitFontSize.textContent = this.prefs.fontSize;

        const splitFontSelect = document.getElementById('split-font-select');
        if (splitFontSelect) splitFontSelect.value = this.prefs.fontFamily;

        const splitLineHeight = document.getElementById('split-line-height');
        if (splitLineHeight) splitLineHeight.value = this.prefs.lineHeight;
    }

    savePreferences() {
        localStorage.setItem('reader_prefs', JSON.stringify(this.prefs));
        // Sync to user profile on server
        const userId = window._appState?.currentUserId;
        if (userId) {
            fetch(`/api/users/${userId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ settings: { reader_prefs: this.prefs } })
            }).catch(() => {}); // silent — localStorage is the fallback
        }
    }

    loadPreferences() {
        // Start with localStorage (immediate, sync)
        const saved = localStorage.getItem('reader_prefs');
        if (saved) {
            try {
                const parsed = JSON.parse(saved);
                Object.assign(this.prefs, parsed);
                this.audioSyncEnabled = !!this.prefs.audioSync;
            } catch (e) {
                // Use defaults
            }
        }
        // Overlay server prefs if user is logged in (async)
        const userId = window._appState?.currentUserId;
        if (userId) {
            fetch(`/api/users/${userId}`)
                .then(r => r.ok ? r.json() : null)
                .then(user => {
                    if (user?.settings?.reader_prefs) {
                        Object.assign(this.prefs, user.settings.reader_prefs);
                        this.audioSyncEnabled = !!this.prefs.audioSync;
                        localStorage.setItem('reader_prefs', JSON.stringify(this.prefs));
                        if (this.isOpen) this.applyPreferences();
                    }
                })
                .catch(() => {}); // silent — use localStorage values
        }
    }

    toggleAudioSync() {
        this.audioSyncEnabled = !this.audioSyncEnabled;
        this.prefs.audioSync = this.audioSyncEnabled;
        this.savePreferences();

        const syncBtn = document.getElementById('reader-audio-sync-btn');
        if (syncBtn) {
            syncBtn.classList.toggle('active', this.audioSyncEnabled);
        }
    }

    checkTranslationBanner() {
        const banner = document.getElementById('reader-translate-banner');
        const textEl = document.getElementById('reader-translate-text');
        if (!banner || !textEl) return;

        // Check if user dismissed this banner for this book
        const dismissKey = `translate_banner_dismissed_${this.bookId}`;
        if (localStorage.getItem(dismissKey)) {
            banner.style.display = 'none';
            return;
        }

        // Get preferred language from app state (exposed as global)
        const prefLangCode = window._appState?.settings?.preferredLanguage || 'en';
        const LANG_NAMES = {
            'en': 'English', 'fr': 'French', 'de': 'German', 'es': 'Spanish',
            'it': 'Italian', 'pt': 'Portuguese', 'la': 'Latin', 'el': 'Greek',
            'nl': 'Dutch', 'ru': 'Russian', 'zh': 'Chinese', 'ja': 'Japanese'
        };
        const prefLangName = LANG_NAMES[prefLangCode] || 'English';

        // Get available text tracks from app state
        const textTracks = window._appState?.textTracks || [];
        const availableLangs = textTracks.map(t => t.language);

        // Check if preferred language is among available tracks
        const hasPreferred = availableLangs.some(lang =>
            lang.toLowerCase() === prefLangName.toLowerCase() ||
            lang.toLowerCase().includes(prefLangName.toLowerCase())
        );

        if (hasPreferred || availableLangs.length === 0) {
            banner.style.display = 'none';
            return;
        }

        textEl.textContent = `Available in ${availableLangs.join(', ')}. Translate to ${prefLangName}?`;
        banner.style.display = 'flex';
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
        const controls = document.getElementById('reader-player-controls');
        const noAudio = document.getElementById('reader-no-audio');

        if (!this.hasAudio) {
            if (controls) controls.style.display = 'none';
            if (noAudio) noAudio.style.display = 'flex';
            return;
        }

        if (controls) controls.style.display = '';
        if (noAudio) noAudio.style.display = 'none';

        const audio = document.getElementById('audio-player');
        const playBtn = document.getElementById('reader-play-pause');
        if (playBtn) {
            playBtn.textContent = (audio && !audio.paused) ? '\u23F8' : '\u25B6';
        }
    }

    updateMiniPlayerInfo(chapterName) {
        const nowPlaying = document.getElementById('reader-now-playing');
        if (nowPlaying && chapterName) {
            nowPlaying.textContent = chapterName;
        }
    }

    updateMiniPlayerProgress(currentTime, duration) {
        if (!this.isOpen || !this.hasAudio) return;
        const fill = document.getElementById('reader-progress-fill');
        const timeDisplay = document.getElementById('reader-time-display');
        if (fill && duration > 0) {
            fill.style.width = `${(currentTime / duration) * 100}%`;
        }
        if (timeDisplay && duration > 0) {
            timeDisplay.textContent = `${this.formatTime(currentTime)} / ${this.formatTime(duration)}`;
        }
    }

    formatTime(seconds) {
        if (!seconds || !isFinite(seconds)) return '0:00';
        const m = Math.floor(seconds / 60);
        const s = Math.floor(seconds % 60);
        return `${m}:${s.toString().padStart(2, '0')}`;
    }

    highlightCurrentParagraph(chapterIndex, paraId) {
        if (!this.isOpen || !this.audioSyncEnabled) return;

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
            if (!this.hasAudio) return;
            const audio = document.getElementById('audio-player');
            if (audio) {
                if (audio.paused) audio.play();
                else audio.pause();
            }
        };

        this._onAudioStateChange = () => this.updateMiniPlayer();

        this._onRewind = () => {
            const audio = document.getElementById('audio-player');
            if (audio) audio.currentTime = Math.max(0, audio.currentTime - 30);
        };

        this._onForward = () => {
            const audio = document.getElementById('audio-player');
            if (audio) audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 30);
        };

        this._onProgressSeek = (e) => {
            const bar = document.getElementById('reader-progress-bar');
            const audio = document.getElementById('audio-player');
            if (!bar || !audio || !audio.duration) return;
            const rect = bar.getBoundingClientRect();
            const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
            audio.currentTime = pct * audio.duration;
        };

        this._onGenerate = () => {
            if (typeof pipeline !== 'undefined' && pipeline.openGenerationModal && this.bookId) {
                pipeline.openGenerationModal(this.bookId);
            }
        };

        this._onTranslate = () => {
            if (typeof pipeline !== 'undefined' && pipeline.openGenerationModal && this.bookId) {
                pipeline.openGenerationModal(this.bookId);
            }
        };

        this._onDismissTranslate = () => {
            const banner = document.getElementById('reader-translate-banner');
            if (banner) banner.style.display = 'none';
            localStorage.setItem(`translate_banner_dismissed_${this.bookId}`, '1');
        };

        this._onMoreMenu = () => {
            const menu = document.getElementById('reader-more-menu');
            if (menu) menu.classList.toggle('hidden');
            // Show "Full Player" only when audio is loaded
            const goPlayer = document.getElementById('reader-go-player');
            if (goPlayer) goPlayer.style.display = this.hasAudio ? 'block' : 'none';
        };

        this._onGoPlayer = () => {
            document.getElementById('reader-more-menu')?.classList.add('hidden');
            this.close();
            // Navigate to full player view
            if (window._appState?.currentVariant && typeof renderPlayer === 'function') {
                renderPlayer();
                document.getElementById('library-view')?.classList.remove('active');
                document.getElementById('variant-view')?.classList.remove('active');
                document.getElementById('player-view')?.classList.add('active');
            }
        };

        this._onGoVariants = () => {
            document.getElementById('reader-more-menu')?.classList.add('hidden');
            this.close();
            // Navigate to variant view
            if (this.bookId && typeof showVariants === 'function') {
                showVariants(this.bookId);
            }
        };

        this._onSyncToggle = () => this.toggleAudioSync();

        this._onKeydown = (e) => {
            if (!this.isOpen) return;
            if (e.key === 'Escape') {
                // Close dropdowns first, then close reader
                const settings = document.getElementById('reader-settings');
                const chapterNav = document.getElementById('reader-chapter-nav');
                const moreMenu = document.getElementById('reader-more-menu');
                if (moreMenu && !moreMenu.classList.contains('hidden')) {
                    moreMenu.classList.add('hidden');
                } else if (settings && !settings.classList.contains('hidden')) {
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
        document.getElementById('reader-rewind')?.addEventListener('click', this._onRewind);
        document.getElementById('reader-forward')?.addEventListener('click', this._onForward);
        document.getElementById('reader-progress-bar')?.addEventListener('click', this._onProgressSeek);
        document.getElementById('reader-generate-btn')?.addEventListener('click', this._onGenerate);
        document.getElementById('reader-translate-btn')?.addEventListener('click', this._onTranslate);
        document.getElementById('reader-translate-dismiss')?.addEventListener('click', this._onDismissTranslate);
        document.getElementById('reader-more-btn')?.addEventListener('click', this._onMoreMenu);
        document.getElementById('reader-go-player')?.addEventListener('click', this._onGoPlayer);
        document.getElementById('reader-go-variants')?.addEventListener('click', this._onGoVariants);
        document.getElementById('reader-audio-sync-btn')?.addEventListener('click', this._onSyncToggle);

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
        document.getElementById('reader-rewind')?.removeEventListener('click', this._onRewind);
        document.getElementById('reader-forward')?.removeEventListener('click', this._onForward);
        document.getElementById('reader-progress-bar')?.removeEventListener('click', this._onProgressSeek);
        document.getElementById('reader-generate-btn')?.removeEventListener('click', this._onGenerate);
        document.getElementById('reader-translate-btn')?.removeEventListener('click', this._onTranslate);
        document.getElementById('reader-translate-dismiss')?.removeEventListener('click', this._onDismissTranslate);
        document.getElementById('reader-more-btn')?.removeEventListener('click', this._onMoreMenu);
        document.getElementById('reader-go-player')?.removeEventListener('click', this._onGoPlayer);
        document.getElementById('reader-go-variants')?.removeEventListener('click', this._onGoVariants);
        document.getElementById('reader-audio-sync-btn')?.removeEventListener('click', this._onSyncToggle);

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

    renderMarkdown(text) {
        let html = this.escapeHtml(text);
        // Headings: ## Heading → <strong>Heading</strong> (rendered inline within <p>)
        html = html.replace(/^#{1,6}\s+(.+)$/gm, '<strong>$1</strong>');
        // Bold: **text** or __text__
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/__(.+?)__/g, '<strong>$1</strong>');
        // Italic: *text* or _text_
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');
        html = html.replace(/(?<!\w)_(.+?)_(?!\w)/g, '<em>$1</em>');
        // Links: [text](url) → text (strip link, keep label)
        html = html.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
        // Horizontal rules
        html = html.replace(/^---+$/gm, '');
        return html;
    }
}

// Export
window.BookReader = BookReader;
