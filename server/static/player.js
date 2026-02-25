/**
 * Audiobook Player - Variant-based
 *
 * Features:
 * - Book library with multiple variants per book
 * - Variant selection (full, summary, deduped)
 * - Speed control, auto-save position per variant
 * - Chapter navigation
 */

// ============================================================================
// State Management
// ============================================================================

const state = {
    books: [],
    currentBook: null,
    currentVariant: null,
    currentFileIndex: 0,
    deviceId: null,
    isPlaying: false,
    saveInterval: null,
    sleepTimer: {
        timeoutId: null,
        endTime: null,
        type: null, // 'timer' or 'end-of-chapter'
        updateIntervalId: null
    },
    currentChapterIndex: null,
    chunkManifest: null,  // Chunk-based sync data for reader highlighting
    paragraphTimings: null,  // Paragraph-level audio timing data for direct sync
    karaokeSync: null,             // KaraokeSync instance
    karaokeModeEnabled: false,     // Whether karaoke word highlighting is active
    karaokeAvailable: false,       // Whether word timing data exists for current book
    chatOpen: false,
    chatHistory: [],
    // Unified search state
    searchQuery: '',
    searchTab: 'library', // 'library', 'store', 'queue'
    // Gutenberg search state
    gutenberg: {
        catalog: [],
        filteredBooks: [],
        currentPage: 1,
        pageSize: 50,
        activeDownloads: {},
        pollInterval: null,
        available: false
    },
    // User preferences
    settings: {
        preferredLanguage: 'en',
        targetTranslationLanguage: 'Modern English'
    },
    // Language track selection (Netflix-style)
    textTracks: [],                  // Available text tracks for current book
    currentTextTrack: null,          // Currently selected text track object
    textLanguageMatchesAudio: true,  // Whether text lang matches audio lang (for karaoke)
    // Library sort & filter
    sortBy: 'title-asc',
    languageFilter: null,            // null = show all, string = filter by language
    playbackProgress: {},            // { bookId: percentage } for progress bars
    // User profiles
    currentUserId: null,             // Active user profile ID (or null for device mode)
    users: []                        // [{ user_id, name, avatar_emoji }]
};

// ============================================================================
// API Client
// ============================================================================

const API = {
    baseURL: window.location.origin,

    async getBooks() {
        const response = await fetch(`${this.baseURL}/api/books`);
        if (!response.ok) throw new Error('Failed to fetch books');
        const data = await response.json();
        return data.books;
    },

    async getBook(bookId) {
        const response = await fetch(`${this.baseURL}/api/books/${bookId}`);
        if (!response.ok) throw new Error('Failed to fetch book details');
        return response.json();
    },

    getAudioURL(bookId, variantId, fileIndex) {
        return `${this.baseURL}/api/books/${bookId}/variants/${variantId}/audio/${fileIndex}`;
    },

    _playbackHeaders() {
        const h = { 'X-Device-ID': state.deviceId };
        if (state.currentUserId) h['X-User-ID'] = state.currentUserId;
        return h;
    },

    // User profile API
    async getUsers() {
        const r = await fetch(`${this.baseURL}/api/users`);
        if (!r.ok) return [];
        const data = await r.json();
        return data.users || [];
    },

    async getUser(userId) {
        const r = await fetch(`${this.baseURL}/api/users/${userId}`);
        if (!r.ok) return null;
        return r.json();
    },

    async createUser(name, emoji) {
        const r = await fetch(`${this.baseURL}/api/users`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, avatar_emoji: emoji })
        });
        if (!r.ok) return null;
        return r.json();
    },

    async updateUser(userId, updates) {
        const r = await fetch(`${this.baseURL}/api/users/${userId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });
        if (!r.ok) return null;
        return r.json();
    },

    async deleteUser(userId) {
        const r = await fetch(`${this.baseURL}/api/users/${userId}`, { method: 'DELETE' });
        return r.ok;
    },

    // Playback API (uses X-User-ID when available)
    async getAllPlaybackPositions() {
        try {
            const response = await fetch(
                `${this.baseURL}/api/playback/all`,
                { headers: this._playbackHeaders() }
            );
            if (!response.ok) return {};
            const data = await response.json();
            return data.positions || {};
        } catch { return {}; }
    },

    async getPlaybackPosition(bookId, variantId) {
        const response = await fetch(
            `${this.baseURL}/api/playback/${bookId}/${variantId}`,
            { headers: this._playbackHeaders() }
        );
        if (!response.ok) return null;
        return response.json();
    },

    async savePlaybackPosition(bookId, variantId, position, speed, fileIndex, wordIndex = 0, paraId = null) {
        const body = {
            position,
            speed,
            file_index: fileIndex,
            word_index: wordIndex
        };
        if (paraId) body.para_id = paraId;

        const response = await fetch(
            `${this.baseURL}/api/playback/${bookId}/${variantId}`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    ...this._playbackHeaders()
                },
                body: JSON.stringify(body)
            }
        );
        return response.ok;
    },

    async getWordTimings(bookId, chapter) {
        const response = await fetch(`${this.baseURL}/api/books/${bookId}/word-timings/${chapter}`);
        if (!response.ok) return null;
        return response.json();
    },

    async getChunkManifest(bookId) {
        const response = await fetch(`${this.baseURL}/api/books/${bookId}/chunk-manifest`);
        if (!response.ok) return null;
        return response.json();
    },

    // Gutenberg API methods
    async checkGutenbergAvailable() {
        try {
            const response = await fetch(`${this.baseURL}/api/health`);
            const data = await response.json();
            return data.gutenberg_available || false;
        } catch (e) {
            return false;
        }
    },

    async getGutenbergCatalog() {
        const response = await fetch(`${this.baseURL}/api/gutenberg/catalog`);
        if (!response.ok) throw new Error('Failed to fetch Gutenberg catalog');
        return response.json();
    },

    async searchGutenberg(query, language = 'all') {
        const params = new URLSearchParams({ q: query, language });
        const response = await fetch(`${this.baseURL}/api/gutenberg/search?${params}`);
        if (!response.ok) throw new Error('Failed to search Gutenberg');
        return response.json();
    },

    async startGutenbergDownload(gutenbergId, bookSlug, language) {
        const response = await fetch(`${this.baseURL}/api/jobs/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                gutenberg_id: gutenbergId,
                book_slug: bookSlug,
                language: language
            })
        });
        if (response.status === 409) {
            const data = await response.json();
            throw new Error(data.message || 'A job is already running for this book');
        }
        if (!response.ok) throw new Error('Failed to start download');
        return response.json();
    },

    async getDownloadStatus(jobId) {
        const response = await fetch(`${this.baseURL}/api/jobs/${jobId}`);
        if (!response.ok) {
            // Include status code in error message so caller can handle 404s specially
            throw new Error(`Failed to get download status (HTTP ${response.status})`);
        }
        return response.json();
    },

    async getAllDownloads() {
        const response = await fetch(`${this.baseURL}/api/jobs?job_type=download`);
        if (!response.ok) throw new Error('Failed to get downloads');
        return response.json();
    },

    async deleteVariant(bookId, variantId) {
        const response = await fetch(`${this.baseURL}/api/books/${bookId}/variants/${variantId}`, {
            method: 'DELETE'
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to delete variant');
        }
        return response.json();
    }
};

// ============================================================================
// Dark Mode
// ============================================================================

function initDarkMode() {
    const toggle = document.getElementById('dark-mode-toggle');
    if (!toggle) return;
    const isDark = document.documentElement.classList.contains('dark-mode');
    toggle.textContent = isDark ? '\u2600' : '\u263E';
    toggle.addEventListener('click', () => {
        document.documentElement.classList.toggle('dark-mode');
        const dark = document.documentElement.classList.contains('dark-mode');
        localStorage.setItem('audiobook_dark_mode', dark ? 'dark' : 'light');
        toggle.textContent = dark ? '\u2600' : '\u263E';
        // Sync to user profile
        if (state.currentUserId) {
            API.updateUser(state.currentUserId, { settings: { dark_mode: dark ? 'dark' : 'light' } });
        }
    });
}

function applyDarkMode(mode) {
    const toggle = document.getElementById('dark-mode-toggle');
    if (mode === 'dark') {
        document.documentElement.classList.add('dark-mode');
    } else {
        document.documentElement.classList.remove('dark-mode');
    }
    localStorage.setItem('audiobook_dark_mode', mode);
    if (toggle) toggle.textContent = mode === 'dark' ? '\u2600' : '\u263E';
}

// ============================================================================
// Device ID Management
// ============================================================================

function getOrCreateDeviceId() {
    let deviceId = localStorage.getItem('audiobook_device_id');
    if (!deviceId) {
        deviceId = 'device_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
        localStorage.setItem('audiobook_device_id', deviceId);
    }
    return deviceId;
}

// ============================================================================
// User Settings
// ============================================================================

const SETTINGS_KEY = 'audiobook_settings';

const LANGUAGE_NAMES = {
    'en': 'English', 'fr': 'French', 'de': 'German',
    'es': 'Spanish', 'it': 'Italian', 'pt': 'Portuguese',
    'nl': 'Dutch', 'ru': 'Russian', 'zh': 'Chinese',
    'ja': 'Japanese', 'la': 'Latin', 'el': 'Greek',
    'fi': 'Finnish', 'hu': 'Hungarian', 'da': 'Danish',
    'sv': 'Swedish', 'no': 'Norwegian', 'pl': 'Polish',
    'cs': 'Czech', 'ca': 'Catalan', 'eo': 'Esperanto'
};

function loadSettings() {
    try {
        const saved = localStorage.getItem(SETTINGS_KEY);
        if (saved) {
            const parsed = JSON.parse(saved);
            state.settings = { ...state.settings, ...parsed };
        }
    } catch (e) {
        console.warn('Failed to load settings:', e);
    }
}

function saveSettings() {
    try {
        localStorage.setItem(SETTINGS_KEY, JSON.stringify(state.settings));
        // Sync to user profile
        if (state.currentUserId) {
            API.updateUser(state.currentUserId, {
                settings: {
                    preferred_language: state.settings.preferredLanguage,
                    target_translation_language: state.settings.targetTranslationLanguage
                }
            });
        }
    } catch (e) {
        console.warn('Failed to save settings:', e);
    }
}

function openSettings() {
    const modal = document.getElementById('settings-modal');
    const content = document.getElementById('settings-modal-content');

    const currentLang = state.settings.preferredLanguage;
    const currentTarget = state.settings.targetTranslationLanguage;

    const langOptions = Object.entries(LANGUAGE_NAMES)
        .map(([code, name]) =>
            `<option value="${code}" ${code === currentLang ? 'selected' : ''}>${name} (${code.toUpperCase()})</option>`
        ).join('');

    const targetOptions = ['Modern English', 'Simplified English', 'Spanish', 'French', 'German']
        .map(lang =>
            `<option value="${lang}" ${lang === currentTarget ? 'selected' : ''}>${lang}</option>`
        ).join('');

    content.innerHTML = `
        <div class="pipeline-step settings-form">
            <div class="form-group">
                <label>Preferred Reading Language</label>
                <select id="setting-preferred-lang" class="form-select">
                    ${langOptions}
                </select>
                <p class="help-text">Books in this language won't require translation. Used to pre-fill pipeline options.</p>
            </div>

            <div class="form-group">
                <label>Default Translation Target</label>
                <select id="setting-target-lang" class="form-select">
                    ${targetOptions}
                </select>
                <p class="help-text">Default target language when translating books.</p>
            </div>

            <div class="step-buttons">
                <button onclick="closeSettings()" class="btn-secondary">Cancel</button>
                <button onclick="applySettings()" class="btn-primary">Save</button>
            </div>
        </div>
    `;

    modal.style.display = 'block';
}

function applySettings() {
    state.settings.preferredLanguage = document.getElementById('setting-preferred-lang').value;
    state.settings.targetTranslationLanguage = document.getElementById('setting-target-lang').value;
    saveSettings();
    closeSettings();
    // Re-render store to update language indicators
    if (state.searchTab === 'store') {
        renderStoreBooks(state.gutenberg.filteredBooks.length > 0 ? state.gutenberg.filteredBooks : state.gutenberg.catalog);
    }
}

function closeSettings() {
    document.getElementById('settings-modal').style.display = 'none';
}

// ============================================================================
// UI Elements
// ============================================================================

const ui = {
    // Views
    libraryView: document.getElementById('library-view'),
    variantView: document.getElementById('variant-view'),
    playerView: document.getElementById('player-view'),

    // Library
    bookList: document.getElementById('book-list'),
    bookCount: document.getElementById('book-count'),
    sortSelect: document.getElementById('sort-select'),

    // Unified Search
    unifiedSearchInput: document.getElementById('unified-search-input'),
    tabLibrary: document.getElementById('tab-library'),
    tabStore: document.getElementById('tab-store'),
    tabQueue: document.getElementById('tab-queue'),
    tabQueueCount: document.getElementById('tab-queue-count'),
    librarySection: document.getElementById('library-section'),
    storeSection: document.getElementById('store-section'),
    queueSection: document.getElementById('queue-section'),
    libraryCount: document.getElementById('library-count'),
    storeCount: document.getElementById('store-count'),
    queueCount: document.getElementById('queue-count'),
    queueJobList: document.getElementById('queue-job-list'),
    storeBookList: document.getElementById('store-book-list'),
    storePagination: document.getElementById('store-pagination'),
    prevPageBtn: document.getElementById('prev-page-btn'),
    nextPageBtn: document.getElementById('next-page-btn'),
    pageInfo: document.getElementById('page-info'),

    // Variant selection
    variantBackBtn: document.getElementById('variant-back-btn'),
    variantBookTitle: document.getElementById('variant-book-title'),
    variantTitle: document.getElementById('variant-title'),
    variantAuthor: document.getElementById('variant-author'),
    variantList: document.getElementById('variant-list'),

    // Player
    backBtn: document.getElementById('back-btn'),
    playerBookTitle: document.getElementById('player-book-title'),

    // Audio
    audio: document.getElementById('audio-player'),
    playPauseBtn: document.getElementById('play-pause-btn'),
    prevFileBtn: document.getElementById('prev-file-btn'),
    nextFileBtn: document.getElementById('next-file-btn'),
    rewindBtn: document.getElementById('rewind-btn'),
    forwardBtn: document.getElementById('forward-btn'),

    // Progress
    progressBar: document.getElementById('progress-bar'),
    currentTime: document.getElementById('current-time'),
    timeRemaining: document.getElementById('time-remaining'),

    // Speed
    speedSlider: document.getElementById('speed-slider'),
    speedDisplay: document.getElementById('speed-display'),
    speedBtn: document.getElementById('speed-btn'),
    speedModal: document.getElementById('speed-modal'),

    // Sleep Timer
    sleepTimerBtn: document.getElementById('sleep-timer-btn'),
    sleepTimerBackdrop: document.getElementById('sleep-timer-backdrop'),
    sleepTimerModal: document.getElementById('sleep-timer-modal'),
    closeSleepTimerBtn: document.getElementById('close-sleep-timer-btn'),

    // Chapters
    secondaryControls: document.getElementById('secondary-controls-grid'),
    chaptersBtn: document.getElementById('chapters-btn'),
    chaptersBackdrop: document.getElementById('chapters-backdrop'),
    chaptersModal: document.getElementById('chapters-modal'),
    closeChaptersBtn: document.getElementById('close-chapters-btn'),
    chaptersList: document.getElementById('chapters-list'),
    currentChapterName: document.getElementById('current-chapter-name'),

    // Audio Track Selector
    audioTrackSelector: document.getElementById('audio-track-selector'),
    audioTrackBtn: document.getElementById('audio-track-btn'),
    audioTrackCurrent: document.getElementById('audio-track-current'),
    audioTrackDropdown: document.getElementById('audio-track-dropdown'),

    // AI Chat
    aiAssistantBtn: document.getElementById('ai-assistant-btn'),
    readerBtn: document.getElementById('reader-btn'),
    aiChatBackdrop: document.getElementById('ai-chat-backdrop'),
    aiChatPanel: document.getElementById('ai-chat-panel'),
    closeChatBtn: document.getElementById('close-chat-btn'),
    chatBookTitle: document.getElementById('chat-book-title'),
    chatChapterInfo: document.getElementById('chat-chapter-info'),
    chatMessages: document.getElementById('chat-messages'),
    chatToolsStatus: document.getElementById('chat-tools-status'),
    toolsStatusText: document.getElementById('tools-status-text'),
    chatForm: document.getElementById('chat-form'),
    chatInput: document.getElementById('chat-input'),
    chatSubmitBtn: document.getElementById('chat-submit-btn'),

    // Download Status
    downloadStatusPanel: document.getElementById('download-status-panel'),
    downloadStatusList: document.getElementById('download-status-list'),
    closeDownloadStatusBtn: document.getElementById('close-download-status-btn'),

    // Delete Modal
    deleteBackdrop: document.getElementById('delete-backdrop'),
    deleteModal: document.getElementById('delete-modal'),
    closeDeleteBtn: document.getElementById('close-delete-btn'),
    deleteVariantName: document.getElementById('delete-variant-name'),
    deleteVariantDetails: document.getElementById('delete-variant-details'),
    cancelDeleteBtn: document.getElementById('cancel-delete-btn'),
    confirmDeleteBtn: document.getElementById('confirm-delete-btn'),

    // Now Playing Mini Bar
    nowPlayingBar: document.getElementById('now-playing-bar'),
    npTitle: document.getElementById('np-title'),
    npChapter: document.getElementById('np-chapter'),
    npPlayPause: document.getElementById('np-play-pause'),
    npProgressFill: document.getElementById('np-progress-fill')
};

// ============================================================================
// Library Functions
// ============================================================================

async function loadLibrary() {
    try {
        state.books = await API.getBooks();

        // Fetch playback progress for all books
        const positions = await API.getAllPlaybackPositions();
        state.playbackProgress = {};
        for (const book of state.books) {
            if (!book.has_audio || !book.variants.length) continue;
            const variant = book.variants[0];
            const key = `${book.book_id}:${variant.variant_id}`;
            const pos = positions[key];
            if (pos && variant.file_count > 0) {
                state.playbackProgress[book.book_id] = Math.round(((pos.file_index || 0) / variant.file_count) * 100);
            }
        }

        renderLanguageFilters();
        renderUnifiedSearch();
    } catch (error) {
        console.error('Failed to load library:', error);
        ui.bookList.innerHTML = '<div class="error">Failed to load books. Please check server connection.</div>';
    }
}

function sortBooks(books, sortBy) {
    const sorted = [...books];
    switch (sortBy) {
        case 'title-asc':
            sorted.sort((a, b) => a.title.localeCompare(b.title));
            break;
        case 'title-desc':
            sorted.sort((a, b) => b.title.localeCompare(a.title));
            break;
        case 'author-asc':
            sorted.sort((a, b) => (a.author || '').localeCompare(b.author || ''));
            break;
        case 'year-desc':
            sorted.sort((a, b) => (b.year || 0) - (a.year || 0));
            break;
        case 'year-asc':
            sorted.sort((a, b) => (a.year || 9999) - (b.year || 9999));
            break;
    }
    return sorted;
}

function renderLanguageFilters() {
    const container = document.getElementById('language-filters');
    if (!container) return;
    const languages = [...new Set(state.books.map(b => b.language).filter(Boolean))].sort();
    container.innerHTML = languages.map(lang =>
        `<button class="filter-chip${state.languageFilter === lang ? ' active' : ''}" data-lang="${lang}">${lang}</button>`
    ).join('');
    container.querySelectorAll('.filter-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const lang = chip.dataset.lang;
            state.languageFilter = state.languageFilter === lang ? null : lang;
            renderLanguageFilters();
            renderUnifiedSearch();
        });
    });
}

function renderUnifiedSearch() {
    /**
     * Render library or store results based on active tab
     */
    const query = state.searchQuery.toLowerCase().trim();
    const tab = state.searchTab;

    // Filter library books (search + language filter)
    let filteredLibraryBooks = state.books;
    if (query) {
        filteredLibraryBooks = filteredLibraryBooks.filter(book => {
            const titleMatch = book.title.toLowerCase().includes(query);
            const authorMatch = book.author && book.author.toLowerCase().includes(query);
            return titleMatch || authorMatch;
        });
    }
    if (state.languageFilter) {
        filteredLibraryBooks = filteredLibraryBooks.filter(book => book.language === state.languageFilter);
    }

    // Sort library books
    filteredLibraryBooks = sortBooks(filteredLibraryBooks, state.sortBy);

    // Filter store books
    let filteredStoreBooks = state.gutenberg.catalog;
    if (query) {
        filteredStoreBooks = state.gutenberg.catalog.filter(book => {
            const titleMatch = book.title.toLowerCase().includes(query);
            const authorMatch = book.author && book.author.toLowerCase().includes(query);
            return titleMatch || authorMatch;
        });
    }

    // Store filtered books for pagination
    state.gutenberg.filteredBooks = filteredStoreBooks;

    // Update counts
    ui.libraryCount.textContent = filteredLibraryBooks.length;
    ui.storeCount.textContent = filteredStoreBooks.length;
    ui.bookCount.textContent = `${state.books.length} in library • ${state.gutenberg.catalog.length} in store`;

    // Show/hide sections based on tab (separate views now)
    if (tab === 'library') {
        ui.librarySection.style.display = 'block';
        ui.storeSection.style.display = 'none';
        ui.queueSection.style.display = 'none';
        renderLibraryBooks(filteredLibraryBooks);
    } else if (tab === 'store') {
        ui.librarySection.style.display = 'none';
        ui.storeSection.style.display = state.gutenberg.available ? 'block' : 'none';
        ui.queueSection.style.display = 'none';
        if (state.gutenberg.available) {
            renderStoreBooks(filteredStoreBooks);
        }
    } else if (tab === 'queue') {
        ui.librarySection.style.display = 'none';
        ui.storeSection.style.display = 'none';
        ui.queueSection.style.display = 'block';
        jobsActivity.poll();
    }
}

function renderLibraryBooks(books) {
    if (books.length === 0) {
        if (state.searchQuery) {
            ui.bookList.innerHTML = '<div class="empty-state"><div class="empty-state-icon"></div><div class="empty-state-title">No books found</div><div class="empty-state-message">Try adjusting your search</div></div>';
        } else if (state.books.length === 0) {
            ui.bookList.innerHTML = '<div class="empty-state"><div class="empty-state-icon"></div><div class="empty-state-title">Your library is empty</div><div class="empty-state-message">Browse the Store to get started!</div></div>';
        }
        return;
    }

    ui.bookList.innerHTML = books.map((book, index) => {
        const hasCover = book.has_cover && book.cover_image;
        const coverURL = hasCover ? `${API.baseURL}/api/books/${book.book_id}/cover` : null;
        const hasAudio = book.has_audio;
        const hasSourceText = book.has_source_text;
        const hasActiveJob = jobsActivity.jobsByBook[book.book_id];

        return `
            <div class="book-item" data-book-id="${book.book_id}">
                <div class="book-cover-card">
                    ${hasCover ? `
                        <img src="${coverURL}" alt="${book.title} cover" class="book-cover-image" />
                    ` : book.cover_generating ? `
                        <div class="book-cover-generating">
                            <div class="cover-shimmer"></div>
                            <div class="cover-generating-label">Generating cover...</div>
                        </div>
                    ` : `
                        <div class="book-cover-content">
                            <div class="book-cover-icon"></div>
                        </div>
                    `}
                    <div class="book-status-overlay" data-status-book="${book.book_id}" style="display:none"></div>
                    ${!book.cover_generating && !hasActiveJob ? `
                        <div class="generate-cover-badge" onclick="event.stopPropagation(); generateCoverForBook('${book.book_id}')">
                            ${hasCover ? '↻ Replace Cover' : '+ Generate Cover'}
                        </div>
                    ` : ''}
                    ${state.playbackProgress[book.book_id] > 0 ? `
                        <div class="book-progress-bar" style="width: ${state.playbackProgress[book.book_id]}%"></div>
                    ` : ''}
                </div>
                <div class="book-info-bottom">
                    <h3 class="book-title">${book.title}</h3>
                    <p class="book-author">
                        ${book.author || ''}${book.year ? ` (${book.year})` : ''}
                    </p>
                    <div class="book-meta">
                        ${book.language ? `<span class="language-badge">${book.language}</span>` : ''}
                        ${hasAudio ? `<span>${book.variant_count} version${book.variant_count !== 1 ? 's' : ''}</span>` : '<span>No audio</span>'}
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Add click handlers
    document.querySelectorAll('.book-item').forEach(item => {
        item.addEventListener('click', () => {
            openBook(item.dataset.bookId);
        });
    });
}

async function generateCoverForBook(bookId) {
    try {
        const response = await fetch(`${API.baseURL}/api/jobs/cover`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ book_id: bookId })
        });

        if (response.status === 409) {
            const data = await response.json();
            alert(data.message || 'A job is already running for this book');
            return;
        }

        if (!response.ok) {
            throw new Error(`Server error: ${response.status}`);
        }

        const data = await response.json();
        console.log('Cover generation job created:', data.job_id);

        // Force a refresh so the job status shows on the card
        loadLibrary();
    } catch (err) {
        console.error('Failed to create cover job:', err);
        alert('Failed to start cover generation: ' + err.message);
    }
}

function renderStoreBooks(books) {
    if (books.length === 0) {
        if (state.searchQuery) {
            ui.storeBookList.innerHTML = '<div class="empty-state"><div class="empty-state-icon"></div><div class="empty-state-title">No books found in store</div><div class="empty-state-message">Try adjusting your search</div></div>';
        } else {
            ui.storeBookList.innerHTML = '<div class="empty-state"><div class="empty-state-icon"></div><div class="empty-state-title">Store catalog empty</div></div>';
        }
        ui.storePagination.style.display = 'none';
        return;
    }

    // Calculate pagination
    const totalPages = Math.ceil(books.length / state.gutenberg.pageSize);
    const currentPage = state.gutenberg.currentPage;

    // Reset to page 1 if current page exceeds total pages (after search)
    if (currentPage > totalPages) {
        state.gutenberg.currentPage = 1;
    }

    // Get books for current page
    const startIndex = (state.gutenberg.currentPage - 1) * state.gutenberg.pageSize;
    const endIndex = startIndex + state.gutenberg.pageSize;
    const pageBooks = books.slice(startIndex, endIndex);

    // Render books for current page
    const userPrefLang = state.settings?.preferredLanguage || 'en';

    ui.storeBookList.innerHTML = pageBooks.map(book => {
        const slug = book.title
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '_')
            .replace(/^_+|_+$/g, '')
            .substring(0, 50);

        const isPreferredLang = book.language === userPrefLang;
        const langClass = isPreferredLang ? 'lang-match' : 'lang-needs-translation';
        const langLabel = isPreferredLang
            ? book.language.toUpperCase()
            : `${book.language.toUpperCase()} · needs translation`;

        return `
            <div class="store-book-card">
                <div class="store-book-header">
                    <div class="store-book-icon"></div>
                    <div class="store-book-info">
                        <div class="store-book-title">${escapeHtml(book.title)}</div>
                        <div class="store-book-author">${escapeHtml(book.author)}</div>
                        <div class="store-book-meta">
                            ${book.year ? `<span>${book.year}</span>` : ''}
                            <span class="${langClass}">${langLabel}</span>
                            <span>&#8595; ${book.downloads || 0}</span>
                        </div>
                    </div>
                </div>
                <button
                    class="download-book-btn"
                    data-gutenberg-id="${book.gutenberg_id}"
                    data-book-slug="${slug}"
                    data-book-title="${escapeHtml(book.title)}"
                    data-language="${book.language}"
                >
                    Download
                </button>
            </div>
        `;
    }).join('');

    // Add click handlers to download buttons
    document.querySelectorAll('.download-book-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const gutenbergId = parseInt(btn.dataset.gutenbergId);
            const bookSlug = btn.dataset.bookSlug;
            const bookTitle = btn.dataset.bookTitle;
            const language = btn.dataset.language;
            startDownload(gutenbergId, bookSlug, bookTitle, language);
        });
    });

    // Update pagination controls
    updatePaginationControls(totalPages);
}

function updatePaginationControls(totalPages) {
    /**
     * Update pagination button states and page info
     */
    const currentPage = state.gutenberg.currentPage;

    // Show/hide pagination
    if (totalPages <= 1) {
        ui.storePagination.style.display = 'none';
        return;
    }

    ui.storePagination.style.display = 'flex';

    // Update page info
    ui.pageInfo.textContent = `Page ${currentPage} of ${totalPages}`;

    // Update button states
    ui.prevPageBtn.disabled = currentPage === 1;
    ui.nextPageBtn.disabled = currentPage === totalPages;
}

function handleUnifiedSearch() {
    /**
     * Handle unified search input
     */
    state.searchQuery = ui.unifiedSearchInput.value;

    // Reset store pagination to page 1 on new search
    state.gutenberg.currentPage = 1;

    renderUnifiedSearch();
}

function switchTab(tab) {
    /**
     * Switch between Library, Store, and Queue tabs
     */
    state.searchTab = tab;

    // Update tab active states
    ui.tabLibrary.classList.toggle('active', tab === 'library');
    ui.tabStore.classList.toggle('active', tab === 'store');
    ui.tabQueue.classList.toggle('active', tab === 'queue');

    // Show/hide search input (not useful for Queue)
    ui.unifiedSearchInput.style.display = (tab === 'queue') ? 'none' : '';

    // Reset store pagination when switching to store tab
    if (tab === 'store') {
        state.gutenberg.currentPage = 1;
    }

    // Re-render
    renderUnifiedSearch();
}

function showLibrary() {
    ui.libraryView.classList.add('active');
    ui.variantView.classList.remove('active');
    ui.playerView.classList.remove('active');
    updateNowPlayingBar();
}

// ============================================================================
// Variant Selection Functions
// ============================================================================

async function showVariants(bookId) {
    try {
        const book = state.books.find(b => b.book_id === bookId);
        if (!book) return;

        state.currentBook = book;
        state.chunkManifest = null;
        state.paragraphTimings = null;

        // Update header
        ui.variantTitle.textContent = book.title;
        ui.variantAuthor.textContent = book.author || '';

        // Update cover image in variant view
        const variantCoverContainer = document.getElementById('variant-cover-container');
        if (book.has_cover && book.cover_image) {
            const coverURL = `${API.baseURL}/api/books/${book.book_id}/cover`;
            variantCoverContainer.innerHTML = `<img src="${coverURL}" alt="${book.title} cover" class="variant-cover-image" />`;
        } else if (book.cover_generating) {
            variantCoverContainer.innerHTML = `<div class="variant-cover-generating">
                <div class="cover-shimmer"></div>
                <div class="cover-generating-label">Generating cover...</div>
            </div>`;
        } else {
            const hasActiveJob = jobsActivity.jobsByBook[book.book_id];
            variantCoverContainer.innerHTML = `<div class="variant-cover-placeholder"></div>
                ${!hasActiveJob ? `<button class="generate-cover-btn" onclick="generateCoverForBook('${book.book_id}')">Generate Cover</button>` : ''}`;
        }

        // Show/hide "Generate New Version" button (hide only if job is running/pending)
        const generateBtn = document.getElementById('generate-new-version-btn');
        const activeJob = jobsActivity.jobsByBook[book.book_id];
        const hasActiveJob = activeJob && activeJob.status !== 'failed';
        if (book.has_source_text && !hasActiveJob) {
            generateBtn.style.display = 'block';
            generateBtn.onclick = () => {
                if (typeof pipeline !== 'undefined' && pipeline.openGenerationModal) {
                    pipeline.openGenerationModal(book.book_id);
                } else {
                    console.error('Pipeline not available');
                    alert('Audio generation not available. Please check server configuration.');
                }
            };
        } else {
            generateBtn.style.display = 'none';
        }

        // Render variants and job status
        renderVariants();
        updateBookJobStatus(book.book_id);

        // Show variant view
        ui.libraryView.classList.remove('active');
        ui.variantView.classList.add('active');
        ui.playerView.classList.remove('active');
        updateNowPlayingBar();

    } catch (error) {
        console.error('Failed to load variants:', error);
        alert('Failed to load book versions');
    }
}

function updateBookJobStatus(bookId) {
    const container = document.getElementById('book-job-status');
    if (!container) return;

    const job = jobsActivity.jobsByBook[bookId];
    if (!job) {
        container.style.display = 'none';
        return;
    }

    container.style.display = '';
    const icon = jobsActivity.getIcon(job);
    const typeLabel = { download: 'Downloading', translate: 'Translating', audiobook: 'Generating Audio' };
    const label = typeLabel[job.job_type] || 'Processing';

    if (job.status === 'running') {
        const pct = job.progress || 0;
        const msg = job.state?.message || 'Processing...';
        const eta = job.eta_seconds ? `~${Math.ceil(job.eta_seconds / 60)} min remaining` : '';
        container.innerHTML = `
            <div class="book-job-card running">
                <div class="book-job-header">${icon} ${label}</div>
                <div class="book-job-detail">${jobsActivity.escapeHtml(msg)}${eta ? ' &middot; ' + eta : ''}</div>
                <div class="book-job-bar"><div class="book-job-fill" style="width:${pct}%"></div></div>
                <div class="book-job-pct">${pct}%</div>
            </div>`;
    } else if (job.status === 'pending') {
        container.innerHTML = `
            <div class="book-job-card pending">
                <div class="book-job-header">${label} — Queued</div>
                <div class="book-job-detail">Waiting for other jobs to finish...</div>
            </div>`;
    }
}

function renderVariants() {
    const book = state.currentBook;

    ui.variantList.innerHTML = book.variants.map(variant => {
        const typeBadge = variant.type === 'summary' && variant.summary_pct
            ? `${variant.summary_pct}% Summary`
            : variant.type === 'deduped'
            ? 'Full (Deduped)'
            : 'Full Translation';

        const date = new Date(variant.created_at).toLocaleDateString('en-US', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });

        // Language info
        let langInfo = '';
        if (variant.source_lang && variant.target_lang) {
            langInfo = `${variant.source_lang} → ${variant.target_lang}`;
        } else if (variant.target_lang) {
            langInfo = variant.target_lang;
        } else if (book.language) {
            langInfo = book.language;
        }

        return `
            <div class="variant-item" data-variant-id="${variant.variant_id}">
                <div class="variant-header">
                    <div class="variant-title">
                        <h4>${typeBadge}</h4>
                        <p class="variant-subtitle">
                            ${langInfo ? `${langInfo} • ` : ''}${date}
                        </p>
                    </div>
                    <div class="variant-actions">
                        <div class="variant-badges">
                            <span class="variant-badge ${variant.type}">${variant.type}</span>
                            ${variant.is_combined ? '<span class="variant-badge combined">Single File</span>' : ''}
                        </div>
                        <button class="delete-variant-btn" data-variant-id="${variant.variant_id}" title="Delete this audiobook">×</button>
                    </div>
                </div>
                <div class="variant-meta">
                    <span>${variant.file_count} file${variant.file_count !== 1 ? 's' : ''}</span>
                    <span>${variant.size_mb} MB</span>
                </div>
            </div>
        `;
    }).join('');

    // Add click handlers for variant items
    document.querySelectorAll('.variant-item').forEach(item => {
        item.addEventListener('click', (e) => {
            // Don't open variant if clicking delete button (use closest() for child elements)
            if (!e.target.closest('.delete-variant-btn')) {
                const variantId = item.dataset.variantId;
                openVariant(variantId);
            }
        });
    });

    // Add click handlers for delete buttons
    document.querySelectorAll('.delete-variant-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation(); // Prevent variant item click
            const variantId = btn.dataset.variantId;
            const variant = book.variants.find(v => v.variant_id === variantId);
            if (variant) {
                showDeleteConfirmation(variant);
            }
        });
    });
}

function showVariantSelection() {
    ui.libraryView.classList.remove('active');
    ui.variantView.classList.add('active');
    ui.playerView.classList.remove('active');

    // Pause playback
    if (state.isPlaying) {
        ui.audio.pause();
    }
}

// ============================================================================
// Player Functions
// ============================================================================

async function openVariant(variantId) {
    try {
        const book = state.currentBook;
        const variant = book.variants.find(v => v.variant_id === variantId);
        if (!variant) {
            console.error('[openVariant] Variant not found:', variantId);
            return;
        }

        console.log('[openVariant]', {
            variantId: variantId,
            variant: variant,
            audio_files_count: variant.audio_files ? variant.audio_files.length : 0
        });

        state.currentVariant = variant;
        state.currentFileIndex = 0;

        // Set up text tracks from book data
        state.textTracks = book.text_tracks || [];
        autoSelectTextTrack();

        // Load saved position
        const savedPosition = await API.getPlaybackPosition(book.book_id, variantId);
        if (savedPosition) {
            // Validate saved file index is within bounds
            const savedFileIndex = savedPosition.file_index || 0;
            if (savedFileIndex >= 0 && savedFileIndex < variant.audio_files.length) {
                state.currentFileIndex = savedFileIndex;
            } else {
                console.warn('[openVariant] Saved file index out of bounds:', savedFileIndex, 'max:', variant.audio_files.length - 1);
                state.currentFileIndex = 0;
            }
        }

        renderPlayer();
        loadAudioFile();

        // Restore saved position and speed
        if (savedPosition) {
            ui.audio.playbackRate = savedPosition.speed || 1.0;
            ui.speedSlider.value = savedPosition.speed || 1.0;
            updateSpeedDisplay();

            // Set position after metadata loads
            ui.audio.addEventListener('loadedmetadata', () => {
                ui.audio.currentTime = savedPosition.position || 0;
            }, { once: true });
        }

        // Show player view
        ui.libraryView.classList.remove('active');
        ui.variantView.classList.remove('active');
        ui.playerView.classList.add('active');
        updateNowPlayingBar();

    } catch (error) {
        console.error('Failed to open variant:', error);
        alert('Failed to load audiobook');
    }
}

function renderPlayer() {
    const book = state.currentBook;
    const variant = state.currentVariant;

    ui.playerBookTitle.textContent = book.title;

    // Update narrator info
    const narratorEl = document.getElementById('player-narrator');
    if (book.author) {
        narratorEl.textContent = `Narrated by ${book.author}`;
        narratorEl.style.display = 'block';
    } else {
        narratorEl.style.display = 'none';
    }

    // Update book cover in player
    const bookCoverDiv = document.querySelector('.book-cover');
    if (book.has_cover && book.cover_image) {
        const coverURL = `${API.baseURL}/api/books/${book.book_id}/cover`;
        bookCoverDiv.innerHTML = `<img src="${coverURL}" alt="${book.title} cover" style="width: 100%; height: 100%; object-fit: cover; border-radius: 2px;" />`;
    } else {
        bookCoverDiv.textContent = '';
    }

    // Always show secondary controls (speed, timer, and optionally chapters)
    ui.secondaryControls.style.display = 'grid';

    // Show/hide chapters button based on availability
    if (book.has_chapters && book.chapters) {
        ui.chaptersBtn.style.display = 'block';
        renderChapters();
        updateCurrentChapterDisplay();
    } else {
        ui.chaptersBtn.style.display = 'none';
        ui.currentChapterName.style.display = 'none';
    }

    // Show/hide AI assistant button based on source text availability
    // Note: source text is a book-level property, not variant-level
    if (book.has_source_text) {
        ui.aiAssistantBtn.style.display = 'block';
    } else {
        ui.aiAssistantBtn.style.display = 'none';
    }

    // Show/hide reader button based on source text availability
    if (book.has_source_text) {
        ui.readerBtn.style.display = 'block';
    } else {
        ui.readerBtn.style.display = 'none';
    }

    // Render audio track selector (Netflix-style in-player variant switching)
    renderAudioTrackSelector();

    // Update navigation buttons
    updateNavigationButtons();
}

function updateNavigationButtons() {
    const variant = state.currentVariant;
    ui.prevFileBtn.disabled = state.currentFileIndex === 0;
    ui.nextFileBtn.disabled = state.currentFileIndex >= variant.audio_files.length - 1;
}

function loadAudioFile() {
    const book = state.currentBook;
    const variant = state.currentVariant;
    const audioURL = API.getAudioURL(book.book_id, variant.variant_id, state.currentFileIndex);

    console.log('[loadAudioFile]', {
        book_id: book.book_id,
        variant_id: variant.variant_id,
        fileIndex: state.currentFileIndex,
        audioURL: audioURL
    });

    ui.audio.src = audioURL;
    ui.audio.load();

    updateNavigationButtons();
    updateMediaSession();
}

function renderChapters() {
    const chapters = state.currentBook.chapters;
    const variant = state.currentVariant;

    console.log('[renderChapters]', {
        totalChapters: chapters.length,
        totalAudioFiles: variant.audio_files.length,
        chapters: chapters
    });

    ui.chaptersList.innerHTML = chapters.map((chapter, index) => {
        const isActive = state.currentChapterIndex === index;
        const chapterTitle = chapter.title || `Chapter ${chapter.number || index + 1}`;

        // Calculate chapter duration from audio files
        let duration = '';
        if (variant && variant.audio_files) {
            // Get the audio file for this chapter
            const audioFile = variant.audio_files[chapter.file_index];
            if (audioFile) {
                // If we have duration metadata, use it
                // For now, we'll show a placeholder or calculate from next chapter
                if (chapters[index + 1]) {
                    const nextChapter = chapters[index + 1];
                    if (chapter.file_index === nextChapter.file_index) {
                        // Same file, calculate duration
                        const durationSeconds = nextChapter.timestamp - chapter.timestamp;
                        duration = formatTime(durationSeconds);
                    }
                }
            }
        }

        // Clean, Audible-style layout: title on left, duration on right
        return `
            <div class="chapter-item ${isActive ? 'active' : ''}" data-chapter-index="${index}">
                <div class="chapter-item-info">
                    <div class="chapter-item-title">${chapterTitle}</div>
                </div>
                ${duration ? `<div class="chapter-item-duration">${duration}</div>` : ''}
            </div>
        `;
    }).join('');

    // Add click handlers
    document.querySelectorAll('.chapter-item').forEach(item => {
        item.addEventListener('click', () => {
            const chapterIndex = parseInt(item.dataset.chapterIndex);
            jumpToChapter(chapterIndex);
            closeChaptersModal();
        });
    });
}

function openChaptersModal() {
    ui.chaptersBackdrop.style.display = 'block';
    ui.chaptersModal.style.display = 'block';
    renderChapters(); // Re-render to update active state
}

function closeChaptersModal() {
    ui.chaptersBackdrop.style.display = 'none';
    ui.chaptersModal.style.display = 'none';
}

function jumpToChapter(chapterIndex) {
    const chapters = state.currentBook.chapters;
    if (!chapters || chapterIndex >= chapters.length) {
        console.error('Invalid chapter index:', chapterIndex);
        return;
    }

    const chapter = chapters[chapterIndex];
    const variant = state.currentVariant;

    // Find which audio file contains this chapter
    // Chapter data contains file_index and timestamp
    if (chapter.file_index !== undefined) {
        state.currentFileIndex = chapter.file_index;
        loadAudioFile();

        // Wait for audio to load, then seek to chapter timestamp
        ui.audio.addEventListener('loadedmetadata', () => {
            if (chapter.timestamp !== undefined) {
                ui.audio.currentTime = chapter.timestamp;
            }
            // Auto-play when jumping to chapter
            if (state.isPlaying || !ui.audio.paused) {
                ui.audio.play();
            }
        }, { once: true });

        // Update current chapter tracking
        state.currentChapterIndex = chapterIndex;
        updateChapterHighlight();
    } else {
        console.warn('Chapter does not have file_index:', chapter);
    }
}

function updateChapterHighlight() {
    // Update active chapter in UI
    document.querySelectorAll('.chapter-item').forEach((item, index) => {
        if (index === state.currentChapterIndex) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
}

function detectCurrentChapter() {
    // Auto-detect which chapter we're in based on current file and time
    if (!state.currentBook || !state.currentBook.chapters) return;

    const chapters = state.currentBook.chapters;
    const currentFile = state.currentFileIndex;
    const currentTime = ui.audio.currentTime;

    // Find the chapter that matches current file and is before current time
    for (let i = chapters.length - 1; i >= 0; i--) {
        const chapter = chapters[i];
        if (chapter.file_index === currentFile && chapter.timestamp <= currentTime) {
            if (state.currentChapterIndex !== i) {
                const oldChapterIndex = state.currentChapterIndex;
                state.currentChapterIndex = i;
                updateChapterHighlight();
                updateCurrentChapterDisplay();
            }
            return;
        }
    }
}

function updateCurrentChapterDisplay() {
    // Update the current chapter name shown below book title
    if (!state.currentBook || !state.currentBook.chapters || state.currentChapterIndex === null) {
        ui.currentChapterName.style.display = 'none';
        return;
    }

    const chapter = state.currentBook.chapters[state.currentChapterIndex];
    const chapterTitle = chapter.title || `Chapter ${chapter.number || state.currentChapterIndex + 1}`;

    ui.currentChapterName.textContent = chapterTitle;
    ui.currentChapterName.style.display = 'block';
}

// ============================================================================
// Text Sync Functions
// ============================================================================

// Map audio time to paragraph using chunk manifest for more accurate progress.
// Instead of assuming linear time→text mapping, this uses actual chunk durations
// to compute how far through the chapter text we are.
function findParagraphByChunkManifest(currentTime, paragraphs, chunks) {
    const chapterNum = getCurrentChapterNumber();
    const chapterChunks = chunks.filter(c => c.chapter === chapterNum);
    if (!chapterChunks.length) {
        const progress = Math.max(0, Math.min(0.999, currentTime / ui.audio.duration));
        return findParagraphByProgress(progress, paragraphs);
    }

    // Compute chapter-relative text progress using chunk boundaries
    const chapterStart = chapterChunks[0].cumulative_duration;
    const globalTime = chapterStart + currentTime;
    const chapterTextTotal = chapterChunks.reduce((sum, c) => sum + c.text_length, 0);

    let textConsumed = 0;
    for (const chunk of chapterChunks) {
        const chunkEnd = chunk.cumulative_duration + chunk.duration;
        if (globalTime <= chunkEnd) {
            // Interpolate within this chunk
            const chunkProgress = chunk.duration > 0
                ? Math.max(0, Math.min(1, (globalTime - chunk.cumulative_duration) / chunk.duration))
                : 0;
            textConsumed += chunkProgress * chunk.text_length;
            break;
        }
        textConsumed += chunk.text_length;
    }

    // Convert to 0-1 progress and use the paragraph mapping
    const progress = chapterTextTotal > 0
        ? Math.max(0, Math.min(0.999, textConsumed / chapterTextTotal))
        : 0;
    return findParagraphByProgress(progress, paragraphs);
}

// Fallback: Map a 0-1 progress value to the correct paragraph using cumulative character lengths
function findParagraphByProgress(progress, paragraphs) {
    let totalChars = 0;
    const starts = [];
    for (const p of paragraphs) {
        starts.push(totalChars);
        totalChars += p.text.length;
    }
    if (totalChars === 0) return paragraphs[0].id;

    const targetChar = progress * totalChars;
    for (let i = starts.length - 1; i >= 0; i--) {
        if (targetChar >= starts[i]) return paragraphs[i].id;
    }
    return paragraphs[0].id;
}

// Helper: Get current chapter number (1-based) from player state
function getCurrentChapterNumber() {
    if (state.currentBook?.chapters && state.currentChapterIndex !== null) {
        const ch = state.currentBook.chapters[state.currentChapterIndex];
        return ch ? ch.number : state.currentFileIndex + 1;
    }
    return state.currentFileIndex + 1;
}

// Helper: Calculate global audio position (across all chapter files)
function calculateGlobalAudioPosition() {
    // Use chunk manifest for accurate global time (chapter timestamps are all 0.0
    // because each chapter is its own audio file)
    if (state.chunkManifest && state.chunkManifest.chunks) {
        const chapterNum = getCurrentChapterNumber();
        const firstChunkOfChapter = state.chunkManifest.chunks.find(c => c.chapter === chapterNum);
        if (firstChunkOfChapter) {
            return firstChunkOfChapter.cumulative_duration + ui.audio.currentTime;
        }
    }
    return ui.audio.currentTime;
}

// Helper: Find chunk at given global time
function findChunkAtTime(globalTime, chunks) {
    if (!chunks || chunks.length === 0) return null;

    // Binary search for efficiency (chunks are sorted by cumulative_duration)
    let left = 0;
    let right = chunks.length - 1;

    while (left <= right) {
        const mid = Math.floor((left + right) / 2);
        const chunk = chunks[mid];
        const chunkEnd = chunk.cumulative_duration + chunk.duration;

        if (globalTime >= chunk.cumulative_duration && globalTime < chunkEnd) {
            return chunk;
        } else if (globalTime < chunk.cumulative_duration) {
            right = mid - 1;
        } else {
            left = mid + 1;
        }
    }

    // If not found, return last chunk (end of audiobook)
    return chunks[chunks.length - 1];
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ============================================================================
// Language Track Selection (Netflix-style)
// ============================================================================

function autoSelectTextTrack() {
    if (!state.textTracks || state.textTracks.length === 0) {
        state.currentTextTrack = null;
        state.textLanguageMatchesAudio = true;
        return;
    }

    // Determine the audio language
    const audioLang = (state.currentVariant?.target_lang || state.currentBook?.language || '').toLowerCase();

    // Try to match audio language to a text track
    const matchingTrack = state.textTracks.find(t =>
        t.language.toLowerCase() === audioLang ||
        audioLang.includes(t.language.toLowerCase()) ||
        t.language.toLowerCase().includes(audioLang)
    );

    if (matchingTrack) {
        state.currentTextTrack = matchingTrack;
        state.textLanguageMatchesAudio = true;
    } else {
        // Default to the first track (usually original)
        state.currentTextTrack = state.textTracks.find(t => t.is_default) || state.textTracks[0];
        state.textLanguageMatchesAudio = false;
    }
}

function selectTextTrack(trackId) {
    const track = state.textTracks.find(t => t.track_id === trackId);
    if (!track) return;

    state.currentTextTrack = track;

    // Check if text language matches audio language
    const audioLang = (state.currentVariant?.target_lang || state.currentBook?.language || '').toLowerCase();
    const textLang = track.language.toLowerCase();
    state.textLanguageMatchesAudio =
        textLang === audioLang ||
        textLang.includes(audioLang) ||
        audioLang.includes(textLang);
}

function renderAudioTrackSelector() {
    if (!ui.audioTrackSelector) return;

    const book = state.currentBook;
    if (!book || !book.variants || book.variants.length <= 1) {
        ui.audioTrackSelector.style.display = 'none';
        return;
    }

    ui.audioTrackSelector.style.display = 'block';

    // Display current variant language
    const currentLang = state.currentVariant?.target_lang || state.currentVariant?.source_lang || 'Audio';
    const currentType = state.currentVariant?.type === 'summary'
        ? ` (${state.currentVariant.summary_pct}%)`
        : '';
    if (ui.audioTrackCurrent) {
        ui.audioTrackCurrent.textContent = currentLang + currentType;
    }

    // Build track list from variants
    const audioTracks = book.variants.map(v => {
        const lang = v.target_lang || v.source_lang || 'Audio';
        const suffix = v.type === 'summary' ? ` (${v.summary_pct}%)` : '';
        return {
            track_id: v.variant_id,
            language: lang + suffix,
            label: lang + suffix,
            is_original: false,
        };
    });

    renderTrackDropdown(ui.audioTrackDropdown, audioTracks, { track_id: state.currentVariant?.variant_id }, (variantId) => {
        selectAudioTrack(variantId);
        closeDropdown(ui.audioTrackDropdown, ui.audioTrackBtn);
    });
}

async function selectAudioTrack(variantId) {
    if (!state.currentBook || variantId === state.currentVariant?.variant_id) return;

    const variant = state.currentBook.variants.find(v => v.variant_id === variantId);
    if (!variant) return;

    // Save current position before switching
    await savePlaybackState();

    // Remember current chapter for resuming at similar position
    const wasPlaying = state.isPlaying;
    const currentChapter = state.currentChapterIndex;

    // Pause current audio
    ui.audio.pause();
    state.isPlaying = false;

    // Switch variant
    state.currentVariant = variant;
    state.currentFileIndex = 0;

    // Auto-select matching text track for new audio language
    autoSelectTextTrack();

    // Try to load saved position for this variant
    const savedPosition = await API.getPlaybackPosition(state.currentBook.book_id, variantId);
    if (savedPosition) {
        const savedFileIndex = savedPosition.file_index || 0;
        if (savedFileIndex >= 0 && savedFileIndex < variant.audio_files.length) {
            state.currentFileIndex = savedFileIndex;
        }
    } else if (currentChapter !== null && currentChapter < variant.audio_files.length) {
        // Fall back to same chapter index
        state.currentFileIndex = currentChapter;
    }

    // Re-render player and load new audio
    renderPlayer();
    loadAudioFile();

    if (savedPosition) {
        ui.audio.playbackRate = savedPosition.speed || 1.0;
        ui.speedSlider.value = savedPosition.speed || 1.0;
        updateSpeedDisplay();
        ui.audio.addEventListener('loadedmetadata', () => {
            ui.audio.currentTime = savedPosition.position || 0;
            if (wasPlaying) ui.audio.play();
        }, { once: true });
    } else if (wasPlaying) {
        ui.audio.addEventListener('loadedmetadata', () => {
            ui.audio.play();
        }, { once: true });
    }

}

// --- Shared dropdown helpers ---

function renderTrackDropdown(dropdownEl, tracks, activeTtrack, onSelect) {
    if (!dropdownEl) return;

    dropdownEl.innerHTML = tracks.map(track => {
        const isActive = activeTtrack?.track_id === track.track_id;
        const badges = [];
        if (track.is_original) badges.push('<span class="track-option-badge original">Original</span>');

        return `
            <div class="track-option ${isActive ? 'active' : ''}"
                 data-track-id="${track.track_id}">
                <span class="track-option-name">${track.language}</span>
                ${badges.join('')}
                ${isActive ? '<span class="track-option-check">&#10003;</span>' : ''}
            </div>
        `;
    }).join('');

    dropdownEl.querySelectorAll('.track-option').forEach(option => {
        option.addEventListener('click', () => {
            onSelect(option.dataset.trackId);
        });
    });
}

function toggleDropdown(dropdownEl, btnEl) {
    const isOpen = dropdownEl.style.display === 'block';
    if (isOpen) {
        closeDropdown(dropdownEl, btnEl);
    } else {
        dropdownEl.style.display = 'block';
        const arrow = btnEl.querySelector('.track-selector-arrow');
        if (arrow) arrow.classList.add('open');
    }
}

function closeDropdown(dropdownEl, btnEl) {
    if (dropdownEl) dropdownEl.style.display = 'none';
    if (btnEl) {
        const arrow = btnEl.querySelector('.track-selector-arrow');
        if (arrow) arrow.classList.remove('open');
    }
}

// ============================================================================
// Karaoke Mode Functions
// ============================================================================

async function initKaraokeSync() {
    if (!window.KaraokeSync || !state.currentBook) return;

    // Create KaraokeSync instance if needed
    if (!state.karaokeSync) {
        state.karaokeSync = new KaraokeSync(ui.audio);
    }

    // Try to load word timings for current book
    const hasTimings = await state.karaokeSync.loadWordTimings(state.currentBook.book_id);
    state.karaokeAvailable = hasTimings;
}

function toggleKaraokeMode(enabled) {
    state.karaokeModeEnabled = enabled;

    if (state.karaokeModeEnabled) {
        enableKaraokeMode();
    } else {
        disableKaraokeMode();
    }
}

function enableKaraokeMode() {
    if (!state.karaokeSync || !state.karaokeAvailable) return;

    const chapterNum = getCurrentChapterNumber();
    if (!state.karaokeSync.setChapter(chapterNum)) return;

    state.karaokeSync.enable();
}

function disableKaraokeMode() {
    if (state.karaokeSync) {
        state.karaokeSync.disable();
    }
}

function updateKaraokeChapter() {
    if (!state.karaokeModeEnabled || !state.karaokeSync) return;

    const chapterNum = getCurrentChapterNumber();
    state.karaokeSync.setChapter(chapterNum);
}

// ============================================================================
// AI Chat Functions
// ============================================================================

async function toggleAIChat() {
    state.chatOpen = !state.chatOpen;

    if (state.chatOpen) {
        openAIChatPanel();
    } else {
        closeAIChatPanel();
    }
}

function openAIChatPanel() {
    ui.aiChatBackdrop.style.display = 'block';
    ui.aiChatPanel.style.display = 'flex';

    // Update header
    if (state.currentBook) {
        ui.chatBookTitle.textContent = state.currentBook.title;
        if (state.currentChapterIndex !== null && state.currentBook.chapters) {
            const chapter = state.currentBook.chapters[state.currentChapterIndex];
            const chapterTitle = chapter.title || `Chapter ${chapter.number || state.currentChapterIndex + 1}`;
            ui.chatChapterInfo.textContent = `Currently in ${chapterTitle}`;
        } else {
            ui.chatChapterInfo.textContent = 'AI Book Assistant';
        }
    }

    // Focus input
    ui.chatInput.focus();
}

function closeAIChatPanel() {
    ui.aiChatBackdrop.style.display = 'none';
    ui.aiChatPanel.style.display = 'none';
    state.chatOpen = false;
}

async function sendChatMessage(question) {
    if (!state.currentBook || !state.currentVariant) {
        displayMessage('error', 'No book loaded');
        return;
    }

    // Add user message to chat
    displayMessage('user', question);

    // Show loading state
    showToolsLoading('Thinking...');
    ui.chatSubmitBtn.disabled = true;

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
                question: question,
                user_language: LANGUAGE_NAMES[state.settings.preferredLanguage] || 'English'
            })
        });

        if (!response.ok) {
            const error = await response.json();
            hideToolsLoading();
            displayMessage('error', error.detail || 'Failed to get response from AI assistant');
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
        console.error('AI chat error:', error);
        displayMessage('error', 'Failed to connect to AI assistant. Make sure Ollama is running.');
    } finally {
        ui.chatSubmitBtn.disabled = false;
    }
}

function displayMessage(role, text, metadata = {}) {
    const messagesDiv = ui.chatMessages;
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
}

function showToolsLoading(text) {
    ui.toolsStatusText.textContent = text;
    ui.chatToolsStatus.style.display = 'flex';
}

function hideToolsLoading() {
    ui.chatToolsStatus.style.display = 'none';
}

// ============================================================================
// Gutenberg Search Functions
// ============================================================================

async function initGutenberg() {
    /**
     * Initialize Gutenberg browser (check availability and load catalog)
     */
    try {
        // Check if Gutenberg feature is available
        state.gutenberg.available = await API.checkGutenbergAvailable();

        if (!state.gutenberg.available) {
            console.log('[Gutenberg] Feature not available');
            return;
        }

        // Show store tab
        ui.tabStore.style.display = 'block';

        // Load catalog
        console.log('[Gutenberg] Loading catalog...');
        const data = await API.getGutenbergCatalog();
        state.gutenberg.catalog = data.books || [];

        console.log(`[Gutenberg] Loaded ${state.gutenberg.catalog.length} books`);

        // Initial render of unified search
        renderUnifiedSearch();

        // Check for active downloads
        const downloads = await API.getAllDownloads();
        if (downloads.jobs && downloads.jobs.length > 0) {
            downloads.jobs.forEach(job => {
                if (job.status !== 'completed' && job.status !== 'failed') {
                    state.gutenberg.activeDownloads[job.job_id] = job;
                }
            });

            // Start polling if there are active downloads
            if (Object.keys(state.gutenberg.activeDownloads).length > 0) {
                startDownloadPolling();
            }
        }

    } catch (error) {
        console.error('[Gutenberg] Init error:', error);
        state.gutenberg.available = false;
    }
}


async function startDownload(gutenbergId, bookSlug, bookTitle, language) {
    /**
     * Start downloading a book from Gutenberg
     */
    try {
        console.log(`[Download] Starting: ${bookTitle} (ID: ${gutenbergId}, lang: ${language})`);

        // Start download (pass language from Gutenberg catalog for metadata)
        const response = await API.startGutenbergDownload(gutenbergId, bookSlug, language);
        const jobId = response.job_id;

        // Add to active downloads
        state.gutenberg.activeDownloads[jobId] = {
            job_id: jobId,
            gutenberg_id: gutenbergId,
            book_slug: bookSlug,
            title: bookTitle,
            status: 'pending',
            progress: 0
        };

        // Show notification
        showNotification(`Downloading ${bookTitle}...`);

        // Start polling
        startDownloadPolling();

        // Update UI
        renderDownloadStatus();

    } catch (error) {
        console.error('[Download] Error:', error);
        showNotification(`Failed to start download: ${error.message}`, 'error');
    }
}

function startDownloadPolling() {
    /**
     * Start polling for download status updates
     */
    if (state.gutenberg.pollInterval) {
        return; // Already polling
    }

    console.log('[Download] Starting status polling');

    state.gutenberg.pollInterval = setInterval(async () => {
        await updateDownloadStatuses();
    }, 2000); // Poll every 2 seconds
}

function stopDownloadPolling() {
    /**
     * Stop polling for download status
     */
    if (state.gutenberg.pollInterval) {
        console.log('[Download] Stopping status polling');
        clearInterval(state.gutenberg.pollInterval);
        state.gutenberg.pollInterval = null;
    }
}

async function updateDownloadStatuses() {
    /**
     * Update status for all active downloads
     */
    const jobIds = Object.keys(state.gutenberg.activeDownloads);

    console.log('[Download] Updating statuses for', jobIds.length, 'jobs:', jobIds);

    if (jobIds.length === 0) {
        console.log('[Download] No jobs to update, stopping polling');
        stopDownloadPolling();
        return;
    }

    for (const jobId of jobIds) {
        try {
            console.log(`[Download] Fetching status for job ${jobId}...`);
            const status = await API.getDownloadStatus(jobId);
            console.log(`[Download] Job ${jobId} status:`, status);

            if (!status) {
                console.warn(`[Download] No status returned for job ${jobId}, removing from active downloads`);
                delete state.gutenberg.activeDownloads[jobId];
                continue;
            }

            // Update state
            state.gutenberg.activeDownloads[jobId] = {
                ...state.gutenberg.activeDownloads[jobId],
                ...status
            };

            // Check if complete or error
            if (status.status === 'completed') {
                const book = state.gutenberg.activeDownloads[jobId];
                console.log(`[Download] Job ${jobId} completed!`);
                const bookName = book.title || book.config?.book_slug || book.book_slug;
                showNotification(`${bookName} downloaded. Now you can generate audio.`, 'success');
                delete state.gutenberg.activeDownloads[jobId];

                // Refresh library to show newly downloaded book (if it has been processed)
                setTimeout(async () => {
                    await loadLibrary();
                }, 2000);
            } else if (status.status === 'failed') {
                const book = state.gutenberg.activeDownloads[jobId];
                const errorMsg = status.error || 'Unknown error';
                const bookName = book.title || book.config?.book_slug || book.book_slug;
                console.error(`[Download] Job ${jobId} failed:`, errorMsg);
                showNotification(`Download failed: ${bookName} - ${errorMsg}`, 'error');
                delete state.gutenberg.activeDownloads[jobId];
            }

        } catch (error) {
            console.error(`[Download] Error checking status for ${jobId}:`, error);

            // If job not found (404), remove it - it's been deleted or never existed
            if (error.message && (error.message.includes('HTTP 404') || error.message.includes('not found'))) {
                console.warn(`[Download] Job ${jobId} not found on server (404), removing from active downloads`);
                delete state.gutenberg.activeDownloads[jobId];
            }
            // Don't remove job on other network errors (500, network timeout, etc) - they might be temporary
        }
    }

    // Update UI
    renderDownloadStatus();

    // Stop polling if no active downloads
    if (Object.keys(state.gutenberg.activeDownloads).length === 0) {
        console.log('[Download] No active downloads remaining, stopping polling');
        stopDownloadPolling();
    }
}

function renderDownloadStatus() {
    /**
     * Render download status panel
     */
    const jobs = Object.values(state.gutenberg.activeDownloads);

    console.log('[Download] Rendering status panel, active jobs:', jobs.length, jobs);

    if (jobs.length === 0) {
        ui.downloadStatusPanel.style.display = 'none';
        console.log('[Download] No active jobs, hiding panel');
        return;
    }

    ui.downloadStatusPanel.style.display = 'block';
    console.log('[Download] Showing panel with', jobs.length, 'jobs');

    ui.downloadStatusList.innerHTML = jobs.map(job => {
        const statusText = {
            'pending': 'Pending...',
            'running': 'Downloading...',
            'completed': 'Complete',
            'failed': 'Error',
            'cancelled': 'Cancelled'
        }[job.status] || job.status;

        const progress = job.progress || 0;
        const statusIcon = {
            'pending': '...',
            'running': '→',
            'completed': '✓',
            'failed': '×',
            'cancelled': '—'
        }[job.status] || '→';

        const bookName = job.title || job.config?.book_slug || job.book_slug;
        return `
            <div class="download-status-item">
                <div class="download-info">
                    <strong>${statusIcon} ${escapeHtml(bookName)}</strong>
                    <span class="status-text">${statusText}</span>
                </div>
                <div class="download-progress-bar">
                    <div class="download-progress-fill" style="width: ${progress}%"></div>
                </div>
                <span class="progress-text">${progress}%</span>
            </div>
        `;
    }).join('');
}

function showNotification(message, type = 'info') {
    /**
     * Show toast notification to user
     */
    console.log(`[Notification] ${message}`);

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    // Trigger slide-in animation on next frame
    requestAnimationFrame(() => toast.classList.add('show'));

    // Auto-remove after 4 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Note: escapeHtml function is already defined in the Text Sync section above

// ============================================================================
// Audio Controls
// ============================================================================

function togglePlayPause() {
    if (ui.audio.paused) {
        ui.audio.play();
    } else {
        ui.audio.pause();
    }
}

function playPreviousFile() {
    if (state.currentFileIndex > 0) {
        state.currentFileIndex--;
        loadAudioFile();
        if (state.isPlaying) {
            ui.audio.play();
        }
    }
}

function playNextFile() {
    const variant = state.currentVariant;
    if (state.currentFileIndex < variant.audio_files.length - 1) {
        state.currentFileIndex++;
        loadAudioFile();
        if (state.isPlaying) {
            ui.audio.play();
        }
    }
}

function rewind() {
    ui.audio.currentTime = Math.max(0, ui.audio.currentTime - 30);
}

function forward() {
    ui.audio.currentTime = Math.min(ui.audio.duration, ui.audio.currentTime + 30);
}

function updateProgress() {
    if (ui.audio.duration) {
        const progress = (ui.audio.currentTime / ui.audio.duration) * 100;
        ui.progressBar.value = progress;

        ui.currentTime.textContent = formatTime(ui.audio.currentTime);

        // Calculate and display time remaining (Audible-style)
        const remaining = ui.audio.duration - ui.audio.currentTime;
        ui.timeRemaining.textContent = formatTimeRemaining(remaining);
    }
}

function seekToPosition(event) {
    if (ui.audio.duration) {
        const percent = event.target.value / 100;
        ui.audio.currentTime = percent * ui.audio.duration;
    }
}

function updateSpeed() {
    const speed = parseFloat(ui.speedSlider.value);
    ui.audio.playbackRate = speed;
    updateSpeedDisplay();
    savePlaybackState();
}

function setSpeedPreset(speed) {
    ui.speedSlider.value = speed;
    updateSpeed();
}

function updateSpeedDisplay() {
    ui.speedDisplay.textContent = `${ui.speedSlider.value}x`;
}

function toggleSpeedModal() {
    const isVisible = ui.speedModal.style.display === 'block';
    ui.speedModal.style.display = isVisible ? 'none' : 'block';
}

function openSleepTimerModal() {
    ui.sleepTimerBackdrop.style.display = 'block';
    ui.sleepTimerModal.style.display = 'block';
}

function closeSleepTimerModal() {
    ui.sleepTimerBackdrop.style.display = 'none';
    ui.sleepTimerModal.style.display = 'none';
}

// ============================================================================
// Media Session API (iOS Lock Screen Controls)
// ============================================================================

function updateMediaSession() {
    if (!('mediaSession' in navigator)) return;
    if (!state.currentBook || !state.currentVariant) return;

    const book = state.currentBook;
    const variant = state.currentVariant;
    const currentFile = variant.audio_files[state.currentFileIndex];

    // Set metadata
    navigator.mediaSession.metadata = new MediaMetadata({
        title: book.title,
        artist: book.author || 'Unknown Author',
        album: `Chapter ${state.currentFileIndex + 1}/${variant.audio_files.length}`,
        artwork: book.has_cover && book.cover_image ? [
            { src: `${API.baseURL}/api/books/${book.book_id}/cover`, sizes: '512x512', type: 'image/png' }
        ] : []
    });

    // Set action handlers
    navigator.mediaSession.setActionHandler('play', () => {
        ui.audio.play();
    });

    navigator.mediaSession.setActionHandler('pause', () => {
        ui.audio.pause();
    });

    navigator.mediaSession.setActionHandler('seekbackward', (details) => {
        const skipTime = details.seekOffset || 30;
        ui.audio.currentTime = Math.max(0, ui.audio.currentTime - skipTime);
    });

    navigator.mediaSession.setActionHandler('seekforward', (details) => {
        const skipTime = details.seekOffset || 30;
        ui.audio.currentTime = Math.min(ui.audio.duration, ui.audio.currentTime + skipTime);
    });

    navigator.mediaSession.setActionHandler('previoustrack', () => {
        if (state.currentFileIndex > 0) {
            playPreviousFile();
        } else {
            ui.audio.currentTime = 0;
        }
    });

    navigator.mediaSession.setActionHandler('nexttrack', () => {
        const variant = state.currentVariant;
        if (state.currentFileIndex < variant.audio_files.length - 1) {
            playNextFile();
        }
    });

    // Update playback position
    if (ui.audio.duration && !isNaN(ui.audio.duration)) {
        navigator.mediaSession.setPositionState({
            duration: ui.audio.duration,
            playbackRate: ui.audio.playbackRate,
            position: ui.audio.currentTime
        });
    }
}

// ============================================================================
// Playback State Persistence
// ============================================================================

function startAutoSave() {
    // Save position every 5 seconds
    state.saveInterval = setInterval(() => {
        if (state.currentBook && state.currentVariant && !ui.audio.paused) {
            savePlaybackState();
        }
    }, 5000);
}

function stopAutoSave() {
    if (state.saveInterval) {
        clearInterval(state.saveInterval);
        state.saveInterval = null;
    }
}

async function savePlaybackState() {
    if (!state.currentBook || !state.currentVariant) return;

    // Find current para_id from paragraph timings if available
    let currentParaId = null;
    if (state.paragraphTimings && state.currentChapterIndex !== null) {
        const chapterKey = `chapter_${state.currentChapterIndex + 1}`;
        const timings = state.paragraphTimings[chapterKey]?.paragraphs;
        if (timings) {
            const t = ui.audio.currentTime;
            const match = timings.find(p => t >= p.audio_start && t <= p.audio_end);
            if (match) currentParaId = match.para_id;
        }
    }

    const success = await API.savePlaybackPosition(
        state.currentBook.book_id,
        state.currentVariant.variant_id,
        ui.audio.currentTime,
        ui.audio.playbackRate,
        state.currentFileIndex,
        0, // wordIndex
        currentParaId
    );

    if (!success) {
        console.warn('Failed to save playback state');
    }
}

// ============================================================================
// Sleep Timer Functions
// ============================================================================

function setSleepTimer(minutes) {
    // Cancel any existing timer
    cancelSleepTimer();

    const endTime = Date.now() + (minutes * 60 * 1000);
    state.sleepTimer.endTime = endTime;
    state.sleepTimer.type = 'timer';

    // Set timeout to pause playback
    state.sleepTimer.timeoutId = setTimeout(() => {
        pauseAndNotify('Sleep timer ended');
    }, minutes * 60 * 1000);

    // Update status display every second
    updateTimerDisplay();
    state.sleepTimer.updateIntervalId = setInterval(updateTimerDisplay, 1000);

    // Show cancel button
    document.getElementById('cancel-timer-btn').style.display = 'block';
}

function setEndOfChapterTimer() {
    // Cancel any existing timer
    cancelSleepTimer();

    state.sleepTimer.type = 'end-of-chapter';
    state.sleepTimer.endTime = null;

    // Update status
    const timerStatus = document.getElementById('timer-status');
    timerStatus.textContent = 'Will stop at end of current chapter';
    timerStatus.classList.add('active');

    // Show cancel button
    document.getElementById('cancel-timer-btn').style.display = 'block';
}

function cancelSleepTimer() {
    // Clear timeout
    if (state.sleepTimer.timeoutId) {
        clearTimeout(state.sleepTimer.timeoutId);
        state.sleepTimer.timeoutId = null;
    }

    // Clear update interval
    if (state.sleepTimer.updateIntervalId) {
        clearInterval(state.sleepTimer.updateIntervalId);
        state.sleepTimer.updateIntervalId = null;
    }

    // Reset state
    state.sleepTimer.endTime = null;
    state.sleepTimer.type = null;

    // Update UI
    const timerStatus = document.getElementById('timer-status');
    timerStatus.textContent = 'No timer set';
    timerStatus.classList.remove('active');
    document.getElementById('cancel-timer-btn').style.display = 'none';
}

function updateTimerDisplay() {
    if (state.sleepTimer.type !== 'timer' || !state.sleepTimer.endTime) {
        return;
    }

    const remaining = state.sleepTimer.endTime - Date.now();
    if (remaining <= 0) {
        cancelSleepTimer();
        return;
    }

    const minutes = Math.floor(remaining / 60000);
    const seconds = Math.floor((remaining % 60000) / 1000);

    const timerStatus = document.getElementById('timer-status');
    timerStatus.textContent = `Sleep timer: ${minutes}:${seconds.toString().padStart(2, '0')} remaining`;
    timerStatus.classList.add('active');
}

function pauseAndNotify(message) {
    ui.audio.pause();
    cancelSleepTimer();

    // Optional: Show notification if supported
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification('Audiobook Player', {
            body: message,
            icon: '/static/icon.png'
        });
    }
}

function checkEndOfChapterTimer() {
    // Check if we should stop at end of chapter
    if (state.sleepTimer.type !== 'end-of-chapter') return;

    if (!state.currentBook || !state.currentBook.chapters) {
        // No chapters, just continue playing
        return;
    }

    const chapters = state.currentBook.chapters;
    const currentFile = state.currentFileIndex;
    const currentTime = ui.audio.currentTime;

    // Check if we're at the end of a chapter
    // Find next chapter
    let nextChapterIndex = null;
    for (let i = 0; i < chapters.length; i++) {
        const chapter = chapters[i];
        if (chapter.file_index > currentFile ||
            (chapter.file_index === currentFile && chapter.timestamp > currentTime)) {
            nextChapterIndex = i;
            break;
        }
    }

    // If no next chapter found, we're in the last chapter
    // Check if we're near the end of the current file
    if (nextChapterIndex === null || nextChapterIndex === state.currentChapterIndex + 1) {
        // We're in the last chapter or approaching next chapter
        // Check if we should stop (within 1 second of next chapter or end of file)
        if (nextChapterIndex !== null) {
            const nextChapter = chapters[nextChapterIndex];
            if (nextChapter.file_index === currentFile) {
                const timeToNextChapter = nextChapter.timestamp - currentTime;
                if (timeToNextChapter <= 1) {
                    pauseAndNotify('End of chapter reached');
                }
            }
        } else if (ui.audio.duration - currentTime <= 1) {
            // Near end of file and no next chapter
            pauseAndNotify('End of chapter reached');
        }
    }
}

// ============================================================================
// Delete Variant Functions
// ============================================================================

function showDeleteConfirmation(variant) {
    /**
     * Show delete confirmation for a variant.
     * Uses custom modal if available, falls back to window.confirm().
     */
    // Build variant display name
    const typeBadge = variant.type === 'summary' && variant.summary_pct
        ? `${variant.summary_pct}% Summary`
        : variant.type === 'deduped'
        ? 'Full (Deduped)'
        : 'Full Translation';

    const details = `${variant.file_count} file${variant.file_count !== 1 ? 's' : ''} • ${variant.size_mb} MB`;

    // Try custom modal first
    if (ui.deleteModal && ui.deleteBackdrop) {
        if (ui.deleteVariantName) ui.deleteVariantName.textContent = typeBadge;
        if (ui.deleteVariantDetails) ui.deleteVariantDetails.textContent = details;
        if (ui.confirmDeleteBtn) {
            ui.confirmDeleteBtn.dataset.variantId = variant.variant_id;
            ui.confirmDeleteBtn.disabled = false;
            ui.confirmDeleteBtn.textContent = 'Delete';
        }

        ui.deleteBackdrop.style.display = 'block';
        ui.deleteModal.style.display = 'block';
    } else {
        // Fallback: use native confirm dialog
        const confirmed = window.confirm(
            `Delete "${typeBadge}"?\n\n${details}\n\nThis action cannot be undone.`
        );
        if (confirmed) {
            executeDelete(variant.variant_id);
        }
    }
}

function closeDeleteModal() {
    /**
     * Close delete confirmation modal
     */
    if (ui.deleteBackdrop) ui.deleteBackdrop.style.display = 'none';
    if (ui.deleteModal) ui.deleteModal.style.display = 'none';
    if (ui.confirmDeleteBtn) ui.confirmDeleteBtn.dataset.variantId = '';
}

async function confirmDelete() {
    /**
     * Handle confirm button click from modal
     */
    const variantId = ui.confirmDeleteBtn?.dataset?.variantId;
    if (!variantId) return;
    await executeDelete(variantId);
}

async function executeDelete(variantId) {
    /**
     * Execute variant deletion
     */
    if (!variantId || !state.currentBook) {
        console.error('[DELETE] Missing variant ID or current book');
        return;
    }

    const bookId = state.currentBook.book_id;

    // Disable button and show loading state
    if (ui.confirmDeleteBtn) {
        ui.confirmDeleteBtn.disabled = true;
        ui.confirmDeleteBtn.textContent = 'Deleting...';
    }

    try {
        console.log(`[DELETE] Deleting variant: ${bookId}/${variantId}`);

        // Call API to delete variant
        const result = await API.deleteVariant(bookId, variantId);

        console.log(`[DELETE] Success:`, result);

        // Close modal
        closeDeleteModal();

        // Show success notification
        showNotification(`Deleted ${result.deleted_count} file(s)`, 'success');

        // Reload library to get updated book data
        await loadLibrary();

        // Find the book again (it may have been removed if no variants left)
        const updatedBook = state.books.find(b => b.book_id === bookId);

        if (!updatedBook || updatedBook.variants.length === 0) {
            // No variants left - go back to library
            console.log('[DELETE] No variants remaining, returning to library');
            showLibrary();
        } else {
            // Update current book and re-render variants
            state.currentBook = updatedBook;
            renderVariants();
            console.log(`[DELETE] ${updatedBook.variants.length} variant(s) remaining`);
        }

    } catch (error) {
        console.error('[DELETE] Error:', error);
        showNotification(`Failed to delete: ${error.message}`, 'error');

        // Re-enable button
        if (ui.confirmDeleteBtn) {
            ui.confirmDeleteBtn.disabled = false;
            ui.confirmDeleteBtn.textContent = 'Delete';
        }
    }
}

// ============================================================================
// Utility Functions
// ============================================================================

function formatTime(seconds) {
    if (!seconds || isNaN(seconds)) return '0:00';

    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);

    if (hrs > 0) {
        return `${hrs}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}

function formatTimeRemaining(seconds) {
    if (!seconds || isNaN(seconds) || seconds < 0) return '0m left';

    const hrs = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);

    // Audible-style format: "4h 45m left" or "23m left"
    if (hrs > 0) {
        return `${hrs}h ${mins}m left`;
    }
    return `${mins}m left`;
}

// ============================================================================
// Event Listeners
// ============================================================================

function setupEventListeners() {
    // Navigation
    ui.variantBackBtn.addEventListener('click', showLibrary);
    ui.backBtn.addEventListener('click', showVariantSelection);

    // Playback controls
    ui.playPauseBtn.addEventListener('click', togglePlayPause);
    ui.prevFileBtn.addEventListener('click', playPreviousFile);
    ui.nextFileBtn.addEventListener('click', playNextFile);
    ui.rewindBtn.addEventListener('click', rewind);
    ui.forwardBtn.addEventListener('click', forward);

    // Progress
    ui.progressBar.addEventListener('input', seekToPosition);

    // Speed
    ui.speedSlider.addEventListener('input', updateSpeed);
    ui.speedBtn.addEventListener('click', toggleSpeedModal);

    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const speed = parseFloat(btn.dataset.speed);
            setSpeedPreset(speed);
        });
    });

    // Sleep timer modal
    ui.sleepTimerBtn.addEventListener('click', openSleepTimerModal);
    ui.closeSleepTimerBtn.addEventListener('click', closeSleepTimerModal);
    ui.sleepTimerBackdrop.addEventListener('click', closeSleepTimerModal);

    // Chapters modal
    ui.chaptersBtn.addEventListener('click', openChaptersModal);
    ui.closeChaptersBtn.addEventListener('click', closeChaptersModal);
    ui.chaptersBackdrop.addEventListener('click', closeChaptersModal);

    // Audio track selector
    if (ui.audioTrackBtn) {
        ui.audioTrackBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleDropdown(ui.audioTrackDropdown, ui.audioTrackBtn);
        });
    }

    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (ui.audioTrackSelector && !ui.audioTrackSelector.contains(e.target)) {
            closeDropdown(ui.audioTrackDropdown, ui.audioTrackBtn);
        }
    });

    // AI Chat modal
    ui.aiAssistantBtn.addEventListener('click', toggleAIChat);
    ui.closeChatBtn.addEventListener('click', closeAIChatPanel);
    ui.aiChatBackdrop.addEventListener('click', closeAIChatPanel);

    // Delete modal
    ui.closeDeleteBtn.addEventListener('click', closeDeleteModal);
    ui.deleteBackdrop.addEventListener('click', closeDeleteModal);
    ui.cancelDeleteBtn.addEventListener('click', closeDeleteModal);
    ui.confirmDeleteBtn.addEventListener('click', confirmDelete);

    // Unified search
    ui.unifiedSearchInput.addEventListener('input', handleUnifiedSearch);
    ui.tabLibrary.addEventListener('click', () => switchTab('library'));
    ui.tabStore.addEventListener('click', () => switchTab('store'));
    ui.tabQueue.addEventListener('click', () => switchTab('queue'));

    // Sort dropdown
    if (ui.sortSelect) {
        ui.sortSelect.addEventListener('change', () => {
            state.sortBy = ui.sortSelect.value;
            renderUnifiedSearch();
        });
    }

    // Store pagination
    ui.prevPageBtn.addEventListener('click', () => {
        if (state.gutenberg.currentPage > 1) {
            state.gutenberg.currentPage--;
            renderStoreBooks(state.gutenberg.filteredBooks);
            // Scroll to top of store section
            ui.storeSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });

    ui.nextPageBtn.addEventListener('click', () => {
        const totalPages = Math.ceil(state.gutenberg.filteredBooks.length / state.gutenberg.pageSize);
        if (state.gutenberg.currentPage < totalPages) {
            state.gutenberg.currentPage++;
            renderStoreBooks(state.gutenberg.filteredBooks);
            // Scroll to top of store section
            ui.storeSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    });

    // Download status
    ui.closeDownloadStatusBtn.addEventListener('click', () => {
        // Clear all completed/error downloads and hide panel
        const activeJobs = Object.keys(state.gutenberg.activeDownloads);
        console.log('[Download] Close button clicked, active jobs:', activeJobs);

        // Remove all jobs (user manually closing panel)
        state.gutenberg.activeDownloads = {};
        stopDownloadPolling();

        ui.downloadStatusPanel.style.display = 'none';
        console.log('[Download] Panel closed and downloads cleared');
    });

    // Chat form submission
    ui.chatForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const question = ui.chatInput.value.trim();
        if (question) {
            sendChatMessage(question);
            ui.chatInput.value = '';
        }
    });

    // Suggested questions
    document.querySelectorAll('.suggestion-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const question = btn.dataset.question;
            sendChatMessage(question);
        });
    });

    // Reader button
    ui.readerBtn.addEventListener('click', openReader);

    // Reader seek events (paragraph click in reader -> audio seek)
    document.addEventListener('reader-seek', handleReaderSeek);

    // Keyboard shortcut: Cmd/Ctrl + K to open AI chat
    document.addEventListener('keydown', (e) => {
        if ((e.metaKey || e.ctrlKey) && e.key === 'k' && ui.playerView.classList.contains('active')) {
            e.preventDefault();
            toggleAIChat();
        }
    });

    // Audio events
    ui.audio.addEventListener('play', () => {
        state.isPlaying = true;
        ui.playPauseBtn.textContent = '‖';
        startAutoSave();
        updateMediaSession();
        updateNowPlayingBar();
    });

    ui.audio.addEventListener('pause', () => {
        state.isPlaying = false;
        ui.playPauseBtn.textContent = '▶';
        savePlaybackState();
        stopAutoSave();
        updateNowPlayingBar();
    });

    ui.audio.addEventListener('timeupdate', () => {
        updateProgress();
        detectCurrentChapter();
        checkEndOfChapterTimer();
        updateReaderHighlight();
        updateNowPlayingBar();

        // Update reader mini player progress
        if (window.bookReader?.isOpen) {
            window.bookReader.updateMiniPlayerProgress(ui.audio.currentTime, ui.audio.duration);
        }

        // Update Media Session position periodically (every 5 seconds)
        if ('mediaSession' in navigator && ui.audio.currentTime % 5 < 0.5) {
            updateMediaSession();
        }
    });

    ui.audio.addEventListener('loadedmetadata', () => {
        updateMediaSession();
    });

    ui.audio.addEventListener('ended', () => {
        // Auto-advance to next file
        const variant = state.currentVariant;
        if (state.currentFileIndex < variant.audio_files.length - 1) {
            playNextFile();
        } else {
            // Finished book
            ui.audio.pause();
            ui.audio.currentTime = 0;
        }
    });

    ui.audio.addEventListener('error', (e) => {
        console.error('[Audio Error]', {
            error: e,
            src: ui.audio.src,
            networkState: ui.audio.networkState,
            readyState: ui.audio.readyState,
            errorCode: ui.audio.error ? ui.audio.error.code : null,
            errorMessage: ui.audio.error ? ui.audio.error.message : null
        });
        console.error(`Failed to load: ${ui.audio.src}`);
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (ui.playerView.classList.contains('active')) {
            // Don't intercept shortcuts when typing in input fields
            const activeElement = document.activeElement;
            if (activeElement && (
                activeElement.tagName === 'INPUT' ||
                activeElement.tagName === 'TEXTAREA' ||
                activeElement.isContentEditable
            )) {
                return;
            }

            switch(e.key) {
                case ' ':
                    e.preventDefault();
                    togglePlayPause();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    rewind();
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    forward();
                    break;
            }
        }
    });

    // Sleep timer event listeners
    document.querySelectorAll('.timer-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const minutes = btn.dataset.minutes;
            const action = btn.dataset.action;

            if (action === 'end-of-chapter') {
                setEndOfChapterTimer();
            } else if (minutes) {
                setSleepTimer(parseInt(minutes));
            }
        });
    });

    document.getElementById('cancel-timer-btn').addEventListener('click', () => {
        cancelSleepTimer();
    });

    // Request notification permission on first interaction
    if ('Notification' in window && Notification.permission === 'default') {
        document.addEventListener('click', () => {
            Notification.requestPermission();
        }, { once: true });
    }

    // Save state before page unload
    window.addEventListener('beforeunload', () => {
        if (state.currentBook && state.currentVariant) {
            savePlaybackState();
        }
        // Clean up timers
        cancelSleepTimer();
    });
}

// ============================================================================
// Reader Integration
// ============================================================================

async function openReader() {
    if (!state.currentBook || !window.bookReader) return;

    // Load chunk manifest and paragraph timings for accurate audio-text sync
    if (!state.chunkManifest && state.currentBook) {
        try {
            state.chunkManifest = await API.getChunkManifest(state.currentBook.book_id);
        } catch (e) { /* linear fallback */ }
    }
    if (!state.paragraphTimings && state.currentBook) {
        try {
            const resp = await fetch(`${API.baseURL}/api/books/${state.currentBook.book_id}/paragraph-timings`);
            if (resp.ok) {
                const data = await resp.json();
                state.paragraphTimings = data.has_paragraph_timings ? data.chapters : null;
            }
        } catch (e) { /* fallback to chunk manifest sync */ }
    }

    const chapterCount = state.currentBook.chapters?.length || 1;
    const startChapter = state.currentChapterIndex || 0;
    const trackId = state.currentTextTrack?.track_id || null;
    window.bookReader.open(
        state.currentBook.book_id,
        startChapter,
        chapterCount,
        trackId
    );
    updateNowPlayingBar();
}

async function openBook(bookId) {
    const book = state.books.find(b => b.book_id === bookId);
    if (!book || !window.bookReader) return;

    state.currentBook = book;
    state.textTracks = book.text_tracks || [];
    state.chunkManifest = null;
    state.paragraphTimings = null;
    autoSelectTextTrack();

    // If book has audio, auto-load first variant
    if (book.has_audio && book.variants.length > 0) {
        await loadVariantAudio(book, book.variants[0]);
    } else {
        state.currentVariant = null;
    }

    // Discover chapter count and open reader
    try {
        const response = await fetch(`${API.baseURL}/api/books/${bookId}/text`);
        const data = await response.json();
        const chapterCount = data.total_chapters || 1;
        const trackId = state.currentTextTrack?.track_id || null;
        window.bookReader.open(bookId, 0, chapterCount, trackId);
    } catch (err) {
        console.error('[openBook] Failed to load chapters:', err);
    }
}

async function loadVariantAudio(book, variant) {
    state.currentVariant = variant;
    state.currentFileIndex = 0;

    // Load chunk manifest and paragraph timings for accurate sync
    if (!state.chunkManifest) {
        try { state.chunkManifest = await API.getChunkManifest(book.book_id); }
        catch (e) { /* linear fallback */ }
    }
    if (!state.paragraphTimings) {
        try {
            const resp = await fetch(`${API.baseURL}/api/books/${book.book_id}/paragraph-timings`);
            if (resp.ok) {
                const data = await resp.json();
                state.paragraphTimings = data.has_paragraph_timings ? data.chapters : null;
            }
        } catch (e) { /* fallback to chunk manifest sync */ }
    }

    // Restore saved playback position
    const saved = await API.getPlaybackPosition(book.book_id, variant.variant_id);
    if (saved) {
        const idx = saved.file_index || 0;
        if (idx >= 0 && idx < variant.audio_files.length) {
            state.currentFileIndex = idx;
        }
        ui.audio.playbackRate = saved.speed || 1.0;
    }

    // Load audio file
    loadAudioFile();

    // Seek to saved position after metadata loads
    if (saved?.position) {
        ui.audio.addEventListener('loadedmetadata', () => {
            ui.audio.currentTime = saved.position;
        }, { once: true });
    }

    // Detect chapter index from file index
    if (book.chapters) {
        for (let i = 0; i < book.chapters.length; i++) {
            if (book.chapters[i].file_index === state.currentFileIndex) {
                state.currentChapterIndex = i;
                break;
            }
        }
    }
}

function handleReaderSeek(e) {
    const { chapterIndex, paraId } = e.detail;
    if (!state.currentBook || !state.currentVariant) return;

    const chapters = state.currentBook.chapters;
    if (!chapters || chapterIndex >= chapters.length) return;

    // Switch audio chapter if needed
    if (state.currentChapterIndex !== chapterIndex) {
        jumpToChapter(chapterIndex);
        // After chapter loads, seek to paragraph position
        ui.audio.addEventListener('loadedmetadata', () => {
            seekReaderParagraph(chapterIndex, paraId);
            ui.audio.play();
        }, { once: true });
    } else {
        seekReaderParagraph(chapterIndex, paraId);
        if (ui.audio.paused) ui.audio.play();
    }
}

function seekReaderParagraph(chapterIndex, paraId) {
    // Try paragraph timings first for exact audio position
    const chapterKey = `chapter_${chapterIndex + 1}`;
    const timings = state.paragraphTimings?.[chapterKey]?.paragraphs;
    if (timings) {
        const match = timings.find(p => p.para_id === paraId || p.para_id === String(paraId));
        if (match) {
            ui.audio.currentTime = match.audio_start;
            return;
        }
    }

    // Fallback: character proportion estimation
    const chapterData = window.bookReader?.chapterData[chapterIndex];
    if (!chapterData || !chapterData.paragraphs) return;

    const paragraphs = chapterData.paragraphs;
    let charsBefore = 0;
    let totalChars = 0;

    totalChars = paragraphs.reduce((sum, p) => sum + p.text.length, 0);
    for (const p of paragraphs) {
        const pid = p.para_id || p.id;
        if (pid === paraId || pid === String(paraId)) break;
        charsBefore += p.text.length;
    }

    if (totalChars > 0 && ui.audio.duration) {
        const progress = charsBefore / totalChars;
        ui.audio.currentTime = progress * ui.audio.duration;
    }
}

function updateReaderHighlight() {
    if (!window.bookReader?.isOpen) return;
    if (!ui.audio.duration || state.currentChapterIndex === null) return;

    const chapterData = window.bookReader.chapterData[state.currentChapterIndex];
    if (!chapterData || !chapterData.paragraphs) return;

    let paraId;
    const chapterKey = `chapter_${state.currentChapterIndex + 1}`;
    const timings = state.paragraphTimings?.[chapterKey]?.paragraphs;

    if (timings && timings.length > 0) {
        // Direct lookup from paragraph timing data (most accurate)
        const t = ui.audio.currentTime;
        const match = timings.find(p => t >= p.audio_start && t <= p.audio_end);
        paraId = match ? match.para_id : (t < timings[0].audio_start ? timings[0].para_id : timings[timings.length - 1].para_id);
    } else if (state.chunkManifest?.chunks) {
        paraId = findParagraphByChunkManifest(
            ui.audio.currentTime, chapterData.paragraphs, state.chunkManifest.chunks
        );
    } else {
        const progress = Math.max(0, Math.min(0.999, ui.audio.currentTime / ui.audio.duration));
        paraId = findParagraphByProgress(progress, chapterData.paragraphs);
    }

    window.bookReader.highlightCurrentParagraph(state.currentChapterIndex, paraId);

    // Update mini player info
    const chapter = state.currentBook.chapters?.[state.currentChapterIndex];
    if (chapter) {
        const title = chapter.title || `Chapter ${chapter.number || state.currentChapterIndex + 1}`;
        window.bookReader.updateMiniPlayerInfo(title);
    }
}

// ============================================================================
// Now Playing Mini Bar
// ============================================================================

function updateNowPlayingBar() {
    if (!ui.nowPlayingBar) return;

    const hasAudio = ui.audio.src && !ui.audio.src.endsWith('/');
    const playerActive = ui.playerView.classList.contains('active');
    const readerOpen = window.bookReader?.isOpen;

    // Show when audio is loaded and we're NOT in player view or reader
    const shouldShow = hasAudio && state.currentVariant && !playerActive && !readerOpen;

    if (shouldShow) {
        ui.nowPlayingBar.classList.remove('hidden');
        document.body.classList.add('has-now-playing');

        // Update book title and chapter
        if (state.currentBook) {
            ui.npTitle.textContent = state.currentBook.title || 'Unknown Book';
        }
        const chapter = state.currentBook?.chapters?.[state.currentChapterIndex];
        if (chapter) {
            ui.npChapter.textContent = chapter.title || `Chapter ${chapter.number || (state.currentChapterIndex + 1)}`;
        } else if (state.currentChapterIndex !== null) {
            ui.npChapter.textContent = `Chapter ${state.currentChapterIndex + 1}`;
        }

        // Update progress
        if (ui.audio.duration > 0) {
            const pct = (ui.audio.currentTime / ui.audio.duration) * 100;
            ui.npProgressFill.style.width = `${pct}%`;
        }

        // Update play/pause icon
        ui.npPlayPause.innerHTML = state.isPlaying ? '&#9646;&#9646;' : '&#9654;';
    } else {
        ui.nowPlayingBar.classList.add('hidden');
        document.body.classList.remove('has-now-playing');
    }
}

function initNowPlayingBar() {
    const tapTarget = document.getElementById('np-tap-target');
    if (tapTarget) {
        tapTarget.addEventListener('click', () => {
            if (state.currentBook && state.currentVariant) {
                openVariant(state.currentVariant.variant_id);
            }
        });
    }

    const npPlayPause = document.getElementById('np-play-pause');
    if (npPlayPause) {
        npPlayPause.addEventListener('click', (e) => {
            e.stopPropagation();
            if (ui.audio.paused) ui.audio.play();
            else ui.audio.pause();
        });
    }

    const npRewind = document.getElementById('np-rewind');
    if (npRewind) {
        npRewind.addEventListener('click', (e) => {
            e.stopPropagation();
            ui.audio.currentTime = Math.max(0, ui.audio.currentTime - 30);
        });
    }

    const npForward = document.getElementById('np-forward');
    if (npForward) {
        npForward.addEventListener('click', (e) => {
            e.stopPropagation();
            ui.audio.currentTime = Math.min(ui.audio.duration || 0, ui.audio.currentTime + 30);
        });
    }

    // Show bar again when reader closes
    document.addEventListener('reader-closed', () => updateNowPlayingBar());
}

// ============================================================================
// Jobs Queue (Tab)
// ============================================================================

const jobsActivity = {
    list: null,
    countBadge: null,
    tabCountBadge: null,
    pollInterval: null,
    dismissedJobs: new Set(),
    jobsByBook: {},  // book_id → most relevant job

    init() {
        this.list = ui.queueJobList;
        this.countBadge = ui.queueCount;
        this.tabCountBadge = ui.tabQueueCount;

        // Start polling
        this.poll();
        this.pollInterval = setInterval(() => this.poll(), 5000);
    },

    // Priority for picking which job to show per book (higher = more important)
    jobPriority(job) {
        const p = { running: 4, pending: 3, completed: 1 };
        return p[job.status] || 0;
    },

    async poll() {
        try {
            const response = await fetch('/api/jobs');
            if (!response.ok) return;
            const data = await response.json();

            const allJobs = data.jobs || [];

            // Build book_id → job lookup (prefer running > pending > failed)
            this.jobsByBook = {};
            for (const job of allJobs) {
                if (job.status === 'completed' || job.status === 'cancelled' || job.status === 'failed') continue;
                if (this.dismissedJobs.has(job.job_id)) continue;
                const bookId = job.config?.book_id || job.config?.book_slug;
                if (!bookId) continue;
                const existing = this.jobsByBook[bookId];
                if (!existing || this.jobPriority(job) > this.jobPriority(existing)) {
                    this.jobsByBook[bookId] = job;
                }
            }

            // Update per-book status badges on cards
            this.updateBookBadges();

            // Update variant view if a book detail page is open
            if (state.currentBook) {
                updateBookJobStatus(state.currentBook.book_id);
            }

            // Filter for queue panel
            const jobs = allJobs.filter(job => {
                if (this.dismissedJobs.has(job.job_id)) return false;
                if (job.status === 'running' || job.status === 'pending') return true;
                if (job.status === 'completed' && job.completed_at) {
                    const age = Date.now() - new Date(job.completed_at).getTime();
                    return age < 30000;
                }
                return false;
            });

            this.render(jobs);
        } catch (e) {
            // Silently ignore polling errors
        }
    },

    updateBookBadges() {
        document.querySelectorAll('[data-status-book]').forEach(el => {
            const bookId = el.dataset.statusBook;
            const job = this.jobsByBook[bookId];
            if (!job) {
                el.innerHTML = '';
                el.style.display = 'none';
                return;
            }
            el.style.display = '';
            if (job.status === 'running') {
                const pct = job.progress || 0;
                const icon = this.getIcon(job);
                const msg = job.state?.message || 'Processing...';
                el.innerHTML = `
                    <div class="book-status-badge running">
                        <div class="book-status-info">${icon} ${pct}%</div>
                        <div class="book-status-msg">${this.escapeHtml(msg)}</div>
                        <div class="book-status-bar"><div class="book-status-fill" style="width:${pct}%"></div></div>
                    </div>`;
            } else if (job.status === 'pending') {
                el.innerHTML = `<div class="book-status-badge pending"><div class="book-status-info">Queued</div></div>`;
            } else {
                el.innerHTML = '';
                el.style.display = 'none';
                return;
            }
        });
    },

    render(jobs) {
        // Update tab badge (running + pending only, visible on all tabs)
        const activeCount = jobs.filter(j => j.status === 'running' || j.status === 'pending').length;
        if (this.tabCountBadge) {
            this.tabCountBadge.textContent = activeCount;
            this.tabCountBadge.style.display = activeCount > 0 ? 'inline' : 'none';
        }

        // Update section count badge
        if (this.countBadge) {
            this.countBadge.textContent = jobs.length;
        }

        if (!this.list) return;

        // Show empty state when no jobs
        if (jobs.length === 0) {
            this.list.innerHTML = '<div class="empty-state"><div class="empty-state-icon"></div><div class="empty-state-title">No active jobs</div><div class="empty-state-message">Translation and audio generation jobs will appear here</div></div>';
            return;
        }

        this.list.innerHTML = jobs.map(job => {
            const icon = this.getIcon(job);
            const name = job.config?.book_id || job.config?.book_slug || 'Unknown';
            const progress = job.progress || 0;
            const status = this.getStatusText(job);
            const statusClass = job.status;
            const showProgress = job.status === 'running';
            const showDismiss = job.status === 'failed' || job.status === 'completed';

            return `
                <div class="job-activity-item">
                    <span class="job-activity-icon">${icon}</span>
                    <div class="job-activity-info">
                        <div class="job-activity-name">${this.escapeHtml(name)}</div>
                        <div class="job-activity-status">${this.escapeHtml(status)}</div>
                        ${showProgress ? `
                            <div class="job-activity-progress">
                                <div class="job-activity-progress-fill ${statusClass}" style="width: ${progress}%"></div>
                            </div>
                        ` : ''}
                    </div>
                    ${showDismiss ? `<button class="job-activity-dismiss" onclick="jobsActivity.dismiss('${job.job_id}')" title="Dismiss">✕</button>` : ''}
                </div>
            `;
        }).join('');
    },

    getIcon(job) {
        if (job.status === 'failed') return '×';
        if (job.status === 'completed') return '✓';
        const typeIcons = { audiobook: '+', translate: 'T', download: '↓' };
        return typeIcons[job.job_type] || '·';
    },

    getStatusText(job) {
        if (job.status === 'failed') {
            const error = job.error || 'Unknown error';
            return error.length > 80 ? error.substring(0, 80) + '...' : error;
        }
        if (job.status === 'completed') return 'Done';
        if (job.status === 'pending') return 'Waiting...';

        const msg = job.state?.message || job.state?.stage || 'Processing...';
        const pct = job.progress ? `${job.progress}%` : '';
        const eta = job.eta_seconds ? ` · ~${Math.ceil(job.eta_seconds / 60)} min` : '';
        return `${pct} ${msg}${eta}`.trim();
    },

    dismiss(jobId) {
        this.dismissedJobs.add(jobId);
        this.poll();
    },

    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }
};

// ============================================================================
// User Profiles
// ============================================================================

const AVATAR_EMOJIS = [
    '🧭', '📚', '🎧', '⭐', '🌟', '📖', '🎭', '🎨', '🎵', '🚀',
    '🌙', '☀️', '🎯', '💡', '🔥', '🌊', '🏔️', '🌸', '🦋', '🐉'
];

function openProfilePicker() {
    const modal = document.getElementById('profile-picker-modal');
    if (!modal) return;
    modal.style.display = 'flex';
    renderProfilePicker();
}

function closeProfilePicker() {
    const modal = document.getElementById('profile-picker-modal');
    if (modal) modal.style.display = 'none';
}

function renderProfilePicker() {
    const content = document.getElementById('profile-picker-content');
    if (!content) return;

    let html = '<div class="profile-grid">';

    // Existing user profiles
    for (const user of state.users) {
        const active = user.user_id === state.currentUserId ? ' active' : '';
        html += `
            <button class="profile-button${active}" onclick="selectUser('${user.user_id}')">
                <span class="profile-avatar">${user.avatar_emoji}</span>
                <span class="profile-name">${user.name}</span>
            </button>`;
    }

    // Add profile button
    html += `
        <button class="profile-button add-profile-btn" onclick="openAddProfileForm()">
            <span class="profile-avatar">+</span>
            <span class="profile-name">Add Profile</span>
        </button>`;

    html += '</div>';

    // Add profile form (hidden by default)
    html += `
        <div id="add-profile-form" class="add-profile-form" style="display: none;">
            <input type="text" id="new-profile-name" class="form-input" placeholder="Name" maxlength="20" />
            <div class="emoji-grid" id="emoji-grid"></div>
            <div class="form-buttons">
                <button class="btn-secondary" onclick="renderProfilePicker()">Cancel</button>
                <button class="btn-primary" onclick="submitAddProfile()">Create</button>
            </div>
        </div>`;

    content.innerHTML = html;
}

function openAddProfileForm() {
    const form = document.getElementById('add-profile-form');
    if (!form) { renderProfilePicker(); return; }
    form.style.display = 'block';

    // Hide the profile grid
    const grid = form.parentElement.querySelector('.profile-grid');
    if (grid) grid.style.display = 'none';

    // Populate emoji grid
    const emojiGrid = document.getElementById('emoji-grid');
    if (emojiGrid) {
        emojiGrid.innerHTML = AVATAR_EMOJIS.map((e, i) =>
            `<button class="emoji-option${i === 0 ? ' selected' : ''}" data-emoji="${e}" onclick="selectEmoji(this)">${e}</button>`
        ).join('');
    }

    // Focus name input
    document.getElementById('new-profile-name')?.focus();
}

function selectEmoji(btn) {
    document.querySelectorAll('.emoji-option.selected').forEach(el => el.classList.remove('selected'));
    btn.classList.add('selected');
}

async function submitAddProfile() {
    const nameInput = document.getElementById('new-profile-name');
    const name = nameInput?.value?.trim();
    if (!name) { nameInput?.focus(); return; }

    const selectedEmoji = document.querySelector('.emoji-option.selected');
    const emoji = selectedEmoji?.dataset?.emoji || '👤';

    const user = await API.createUser(name, emoji);
    if (user) {
        state.users = await API.getUsers();
        await selectUser(user.user_id);
    }
}

async function selectUser(userId) {
    state.currentUserId = userId;
    localStorage.setItem('audiobook_last_user', userId);

    // Update header avatar
    const avatarEl = document.getElementById('user-avatar');
    const user = state.users.find(u => u.user_id === userId);
    if (avatarEl && user) avatarEl.textContent = user.avatar_emoji;

    // Fetch full user settings from server
    const fullUser = await API.getUser(userId);
    if (fullUser?.settings) {
        // Apply dark mode
        applyDarkMode(fullUser.settings.dark_mode || 'light');
        // Apply language preferences
        if (fullUser.settings.preferred_language) {
            state.settings.preferredLanguage = fullUser.settings.preferred_language;
        }
        if (fullUser.settings.target_translation_language) {
            state.settings.targetTranslationLanguage = fullUser.settings.target_translation_language;
        }
        saveSettings();
    }

    closeProfilePicker();

    // Reload library with this user's playback positions
    await loadLibrary();
}

async function initProfiles() {
    // Fetch user list from server
    state.users = await API.getUsers();

    if (state.users.length === 0) {
        // Server should auto-create Guest, but just in case
        console.warn('No user profiles found');
        return;
    }

    // Check if we have a remembered user
    const lastUserId = localStorage.getItem('audiobook_last_user');
    const remembered = lastUserId && state.users.find(u => u.user_id === lastUserId);

    // Always show picker on load (Netflix-style)
    openProfilePicker();

    // If only one user, auto-select after a brief moment
    if (state.users.length === 1) {
        await selectUser(state.users[0].user_id);
    }
}

// ============================================================================
// Initialization
// ============================================================================

async function init() {
    // Load user settings from localStorage (fallback)
    loadSettings();

    // Initialize dark mode toggle
    initDarkMode();

    // Settings button
    document.getElementById('settings-btn')?.addEventListener('click', openSettings);

    // Profile button
    document.getElementById('profile-btn')?.addEventListener('click', openProfilePicker);

    // Get or create device ID
    state.deviceId = getOrCreateDeviceId();
    console.log('Device ID:', state.deviceId);

    // Setup event listeners
    setupEventListeners();

    // Initialize user profiles — shows picker, loads library on selection
    await initProfiles();

    // Initialize Gutenberg browser (if available)
    await initGutenberg();

    // Initialize jobs activity panel
    jobsActivity.init();

    // Initialize reader
    window.bookReader = new BookReader();
    window._appState = state;

    // Initialize now playing bar
    initNowPlayingBar();

    console.log('Audiobook player initialized');
}

// Start the app
init();
