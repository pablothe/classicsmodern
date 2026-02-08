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
    textSyncOpen: false,
    textSyncData: null,
    chatOpen: false,
    chatHistory: [],
    // Unified search state
    searchQuery: '',
    searchTab: 'library', // 'library', 'store'
    // Gutenberg search state
    gutenberg: {
        catalog: [],
        filteredBooks: [],
        currentPage: 1,
        pageSize: 50,
        activeDownloads: {},
        pollInterval: null,
        available: false
    }
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

    async getPlaybackPosition(bookId, variantId) {
        const response = await fetch(
            `${this.baseURL}/api/playback/${bookId}/${variantId}`,
            {
                headers: {
                    'X-Device-ID': state.deviceId
                }
            }
        );
        if (!response.ok) return null;
        return response.json();
    },

    async savePlaybackPosition(bookId, variantId, position, speed, fileIndex, wordIndex = 0) {
        const response = await fetch(
            `${this.baseURL}/api/playback/${bookId}/${variantId}`,
            {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Device-ID': state.deviceId
                },
                body: JSON.stringify({
                    position,
                    speed,
                    file_index: fileIndex,
                    word_index: wordIndex
                })
            }
        );
        return response.ok;
    },

    async getWordTimings(bookId, chapter) {
        const response = await fetch(`${this.baseURL}/api/books/${bookId}/word-timings/${chapter}`);
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

    async startGutenbergDownload(gutenbergId, bookSlug) {
        const response = await fetch(`${this.baseURL}/api/gutenberg/download`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                gutenberg_id: gutenbergId,
                book_slug: bookSlug
            })
        });
        if (!response.ok) throw new Error('Failed to start download');
        return response.json();
    },

    async getDownloadStatus(jobId) {
        const response = await fetch(`${this.baseURL}/api/gutenberg/downloads/${jobId}`);
        if (!response.ok) throw new Error('Failed to get download status');
        return response.json();
    },

    async getAllDownloads() {
        const response = await fetch(`${this.baseURL}/api/gutenberg/downloads`);
        if (!response.ok) throw new Error('Failed to get downloads');
        return response.json();
    }
};

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

    // Unified Search
    unifiedSearchInput: document.getElementById('unified-search-input'),
    tabLibrary: document.getElementById('tab-library'),
    tabStore: document.getElementById('tab-store'),
    librarySection: document.getElementById('library-section'),
    storeSection: document.getElementById('store-section'),
    libraryCount: document.getElementById('library-count'),
    storeCount: document.getElementById('store-count'),
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

    // Text Sync
    textSyncBtn: document.getElementById('text-sync-btn'),
    textSyncBackdrop: document.getElementById('text-sync-backdrop'),
    textSyncPanel: document.getElementById('text-sync-panel'),
    closeTextSyncBtn: document.getElementById('close-text-sync-btn'),
    textChapterTitle: document.getElementById('text-chapter-title'),
    textChapterSubtitle: document.getElementById('text-chapter-subtitle'),
    textContent: document.getElementById('text-content'),

    // AI Chat
    aiAssistantBtn: document.getElementById('ai-assistant-btn'),
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
    closeDownloadStatusBtn: document.getElementById('close-download-status-btn')
};

// ============================================================================
// Library Functions
// ============================================================================

async function loadLibrary() {
    try {
        state.books = await API.getBooks();
        renderUnifiedSearch();
    } catch (error) {
        console.error('Failed to load library:', error);
        ui.bookList.innerHTML = '<div class="error">Failed to load books. Please check server connection.</div>';
    }
}

function renderUnifiedSearch() {
    /**
     * Render library or store results based on active tab
     */
    const query = state.searchQuery.toLowerCase().trim();
    const tab = state.searchTab;

    // Filter library books
    let filteredLibraryBooks = state.books;
    if (query) {
        filteredLibraryBooks = state.books.filter(book => {
            const titleMatch = book.title.toLowerCase().includes(query);
            const authorMatch = book.author && book.author.toLowerCase().includes(query);
            return titleMatch || authorMatch;
        });
    }

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
        renderLibraryBooks(filteredLibraryBooks);
    } else if (tab === 'store') {
        ui.librarySection.style.display = 'none';
        ui.storeSection.style.display = state.gutenberg.available ? 'block' : 'none';
        if (state.gutenberg.available) {
            renderStoreBooks(filteredStoreBooks);
        }
    }
}

function renderLibraryBooks(books) {
    if (books.length === 0) {
        if (state.searchQuery) {
            ui.bookList.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔍</div><div class="empty-state-title">No books found</div><div class="empty-state-message">Try adjusting your search</div></div>';
        } else if (state.books.length === 0) {
            ui.bookList.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📚</div><div class="empty-state-title">Your library is empty</div><div class="empty-state-message">Browse the Store to get started!</div></div>';
        }
        return;
    }

    // Generate different gradient colors for each book
    const gradients = [
        'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
        'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
        'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
        'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
        'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
        'linear-gradient(135deg, #30cfd0 0%, #330867 100%)',
        'linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)',
        'linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%)',
        'linear-gradient(135deg, #ffecd2 0%, #fcb69f 100%)',
        'linear-gradient(135deg, #ff6e7f 0%, #bfe9ff 100%)'
    ];

    ui.bookList.innerHTML = books.map((book, index) => {
        const gradient = gradients[index % gradients.length];
        const hasCover = book.has_cover && book.cover_image;
        const coverURL = hasCover ? `${API.baseURL}/api/books/${book.book_id}/cover` : null;

        return `
            <div class="book-item" data-book-id="${book.book_id}">
                <div class="book-cover-card" style="background: ${gradient}">
                    ${hasCover ? `
                        <img src="${coverURL}" alt="${book.title} cover" class="book-cover-image" />
                    ` : `
                        <div class="book-cover-content">
                            <div class="book-cover-icon">📚</div>
                        </div>
                    `}
                </div>
                <div class="book-info-bottom">
                    <h3 class="book-title">${book.title}</h3>
                    ${book.author || book.year ? `
                        <p class="book-author">
                            ${book.author || 'Unknown Author'}${book.year ? ` (${book.year})` : ''}
                        </p>
                    ` : ''}
                    <div class="book-meta">
                        ${book.language ? `<span class="language-badge">${book.language}</span>` : ''}
                        <span>📋 ${book.variant_count}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    // Add click handlers
    document.querySelectorAll('.book-item').forEach(item => {
        item.addEventListener('click', () => {
            const bookId = item.dataset.bookId;
            showVariants(bookId);
        });
    });
}

function renderStoreBooks(books) {
    if (books.length === 0) {
        if (state.searchQuery) {
            ui.storeBookList.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🔍</div><div class="empty-state-title">No books found in store</div><div class="empty-state-message">Try adjusting your search</div></div>';
        } else {
            ui.storeBookList.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🏪</div><div class="empty-state-title">Store catalog empty</div></div>';
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
    ui.storeBookList.innerHTML = pageBooks.map(book => {
        const slug = book.title
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, '_')
            .replace(/^_+|_+$/g, '')
            .substring(0, 50);

        return `
            <div class="store-book-card">
                <div class="store-book-header">
                    <div class="store-book-icon">📚</div>
                    <div class="store-book-info">
                        <div class="store-book-title">${escapeHtml(book.title)}</div>
                        <div class="store-book-author">${escapeHtml(book.author)}</div>
                        <div class="store-book-meta">
                            ${book.year ? `<span>📅 ${book.year}</span>` : ''}
                            <span>🌐 ${book.language.toUpperCase()}</span>
                            <span>↓ ${book.downloads || 0}</span>
                        </div>
                    </div>
                </div>
                <button
                    class="download-book-btn"
                    data-gutenberg-id="${book.gutenberg_id}"
                    data-book-slug="${slug}"
                    data-book-title="${escapeHtml(book.title)}"
                >
                    📥 Download
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
            startDownload(gutenbergId, bookSlug, bookTitle);
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
     * Switch between Library and Store tabs
     */
    state.searchTab = tab;

    // Update tab active states
    ui.tabLibrary.classList.toggle('active', tab === 'library');
    ui.tabStore.classList.toggle('active', tab === 'store');

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

    // Pause playback when returning to library
    if (state.isPlaying) {
        ui.audio.pause();
    }
}

// ============================================================================
// Variant Selection Functions
// ============================================================================

async function showVariants(bookId) {
    try {
        const book = state.books.find(b => b.book_id === bookId);
        if (!book) return;

        state.currentBook = book;

        // Update header
        ui.variantTitle.textContent = book.title;
        ui.variantAuthor.textContent = book.author || '';

        // Update cover image in variant view
        const variantCoverContainer = document.getElementById('variant-cover-container');
        if (book.has_cover && book.cover_image) {
            const coverURL = `${API.baseURL}/api/books/${book.book_id}/cover`;
            variantCoverContainer.innerHTML = `<img src="${coverURL}" alt="${book.title} cover" class="variant-cover-image" />`;
        } else {
            variantCoverContainer.innerHTML = '<div class="variant-cover-placeholder">📚</div>';
        }

        // Render variants
        renderVariants();

        // Show variant view
        ui.libraryView.classList.remove('active');
        ui.variantView.classList.add('active');
        ui.playerView.classList.remove('active');

    } catch (error) {
        console.error('Failed to load variants:', error);
        alert('Failed to load book versions');
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
                    <div class="variant-badges">
                        <span class="variant-badge ${variant.type}">${variant.type}</span>
                        ${variant.is_combined ? '<span class="variant-badge combined">Single File</span>' : ''}
                    </div>
                </div>
                <div class="variant-meta">
                    <span>📁 ${variant.file_count} file${variant.file_count !== 1 ? 's' : ''}</span>
                    <span>💾 ${variant.size_mb} MB</span>
                </div>
            </div>
        `;
    }).join('');

    // Add click handlers
    document.querySelectorAll('.variant-item').forEach(item => {
        item.addEventListener('click', () => {
            const variantId = item.dataset.variantId;
            openVariant(variantId);
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
        bookCoverDiv.innerHTML = `<img src="${coverURL}" alt="${book.title} cover" style="width: 100%; height: 100%; object-fit: cover; border-radius: 12px;" />`;
    } else {
        bookCoverDiv.textContent = '🎧';
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

    // Show/hide text sync button based on source text availability
    if (variant.has_source_text) {
        ui.textSyncBtn.style.display = 'block';
    } else {
        ui.textSyncBtn.style.display = 'none';
    }

    // Show/hide AI assistant button based on source text availability
    if (variant.has_source_text) {
        ui.aiAssistantBtn.style.display = 'block';
    } else {
        ui.aiAssistantBtn.style.display = 'none';
    }

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

                // If text sync is open, reload the text for the new chapter
                if (state.textSyncOpen && oldChapterIndex !== null) {
                    loadChapterText(i);
                }
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

async function toggleTextSync() {
    state.textSyncOpen = !state.textSyncOpen;

    if (state.textSyncOpen) {
        openTextSyncPanel();
    } else {
        closeTextSyncPanel();
    }
}

function openTextSyncPanel() {
    ui.textSyncBackdrop.style.display = 'block';
    ui.textSyncPanel.style.display = 'block';

    // Load text for current chapter
    if (state.currentChapterIndex !== null && state.currentBook && state.currentVariant) {
        loadChapterText(state.currentChapterIndex);
    } else {
        // No chapter detected, try loading first chapter
        loadChapterText(0);
    }
}

function closeTextSyncPanel() {
    ui.textSyncBackdrop.style.display = 'none';
    ui.textSyncPanel.style.display = 'none';
    state.textSyncOpen = false;
}

async function loadChapterText(chapterIndex) {
    try {
        ui.textContent.innerHTML = '<div class="text-loading">Loading text...</div>';

        const response = await fetch(
            `${API.baseURL}/api/books/${state.currentBook.book_id}/text/${chapterIndex}`
        );

        if (!response.ok) {
            const error = await response.json();
            ui.textContent.innerHTML = `
                <div class="text-error">
                    <p>⚠️ ${error.detail || 'Text not available for this chapter'}</p>
                    <p style="font-size: 14px; color: #666;">Make sure the source markdown file exists in the book directory.</p>
                </div>
            `;
            return;
        }

        const data = await response.json();
        state.textSyncData = data;

        // Update header
        ui.textChapterTitle.textContent = data.title;
        ui.textChapterSubtitle.textContent = `${data.word_count} words • ~${Math.round(data.estimated_duration / 60)} min`;

        // Render paragraphs
        renderTextParagraphs(data.paragraphs);

    } catch (error) {
        console.error('Failed to load chapter text:', error);
        ui.textContent.innerHTML = `
            <div class="text-error">
                <p>⚠️ Failed to load text</p>
                <p style="font-size: 14px; color: #666;">${error.message}</p>
            </div>
        `;
    }
}

function renderTextParagraphs(paragraphs) {
    ui.textContent.innerHTML = paragraphs.map(para => `
        <p class="text-paragraph" data-para-id="${para.id}">
            ${escapeHtml(para.text)}
        </p>
    `).join('');

    // Add click handlers for seeking
    document.querySelectorAll('.text-paragraph').forEach(para => {
        para.addEventListener('click', () => {
            const paraId = parseInt(para.dataset.paraId);
            seekToParagraph(paraId);
        });
    });
}

function seekToParagraph(paragraphId) {
    if (!state.textSyncData || !ui.audio.duration) return;

    const totalParagraphs = state.textSyncData.paragraphs.length;
    if (totalParagraphs === 0) return;

    // Estimate audio position based on paragraph position
    const progress = paragraphId / totalParagraphs;
    const estimatedTime = progress * ui.audio.duration;

    ui.audio.currentTime = estimatedTime;

    // Highlight the paragraph immediately
    updateTextHighlight();
}

function updateTextHighlight() {
    if (!state.textSyncOpen || !state.textSyncData || !ui.audio.duration) return;

    const totalParagraphs = state.textSyncData.paragraphs.length;
    if (totalParagraphs === 0) return;

    // Calculate which paragraph we're currently in
    // Use chapter-based interpolation if audio timing is available
    let progress;

    if (state.textSyncData.audio_start !== undefined && state.textSyncData.audio_duration) {
        // Chapter-based sync: interpolate within chapter boundaries
        const chapterStart = state.textSyncData.audio_start;
        const chapterDuration = state.textSyncData.audio_duration;
        const chapterEnd = chapterStart + chapterDuration;

        // Clamp current time to chapter boundaries
        const currentTime = ui.audio.currentTime;

        if (currentTime < chapterStart) {
            // Before chapter start - highlight first paragraph
            progress = 0;
        } else if (currentTime >= chapterEnd) {
            // After chapter end - highlight last paragraph
            progress = 0.999; // Not quite 1.0 to avoid out-of-bounds
        } else {
            // Within chapter - interpolate position
            progress = (currentTime - chapterStart) / chapterDuration;
        }
    } else {
        // Fallback to linear interpolation (legacy behavior)
        progress = ui.audio.currentTime / ui.audio.duration;
    }

    const currentParagraphId = Math.floor(progress * totalParagraphs);

    // Remove previous highlights
    document.querySelectorAll('.text-paragraph').forEach(p => {
        p.classList.remove('active');
    });

    // Highlight current paragraph
    const currentPara = document.querySelector(`.text-paragraph[data-para-id="${currentParagraphId}"]`);
    if (currentPara) {
        currentPara.classList.add('active');

        // Auto-scroll to keep current paragraph in view
        currentPara.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
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
    // Close text sync if open (mutually exclusive)
    if (state.textSyncOpen) {
        closeTextSyncPanel();
    }

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
                question: question
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
                if (job.status !== 'complete' && job.status !== 'error') {
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


async function startDownload(gutenbergId, bookSlug, bookTitle) {
    /**
     * Start downloading a book from Gutenberg
     */
    try {
        console.log(`[Download] Starting: ${bookTitle} (ID: ${gutenbergId})`);

        // Start download
        const response = await API.startGutenbergDownload(gutenbergId, bookSlug);
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
        showNotification(`📥 Downloading ${bookTitle}...`);

        // Start polling
        startDownloadPolling();

        // Update UI
        renderDownloadStatus();

    } catch (error) {
        console.error('[Download] Error:', error);
        showNotification(`❌ Failed to start download: ${error.message}`, 'error');
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

    if (jobIds.length === 0) {
        stopDownloadPolling();
        return;
    }

    for (const jobId of jobIds) {
        try {
            const status = await API.getDownloadStatus(jobId);

            // Update state
            state.gutenberg.activeDownloads[jobId] = {
                ...state.gutenberg.activeDownloads[jobId],
                ...status
            };

            // Check if complete or error
            if (status.status === 'complete') {
                const book = state.gutenberg.activeDownloads[jobId];
                showNotification(`✅ ${book.title} downloaded! Now you can generate audio.`, 'success');
                delete state.gutenberg.activeDownloads[jobId];

                // Refresh library to show newly downloaded book (if it has been processed)
                setTimeout(async () => {
                    await loadLibrary();
                }, 2000);
            } else if (status.status === 'error') {
                const book = state.gutenberg.activeDownloads[jobId];
                showNotification(`❌ Download failed: ${book.title}`, 'error');
                delete state.gutenberg.activeDownloads[jobId];
            }

        } catch (error) {
            console.error(`[Download] Error checking status for ${jobId}:`, error);
        }
    }

    // Update UI
    renderDownloadStatus();

    // Stop polling if no active downloads
    if (Object.keys(state.gutenberg.activeDownloads).length === 0) {
        stopDownloadPolling();
    }
}

function renderDownloadStatus() {
    /**
     * Render download status panel
     */
    const jobs = Object.values(state.gutenberg.activeDownloads);

    if (jobs.length === 0) {
        ui.downloadStatusPanel.style.display = 'none';
        return;
    }

    ui.downloadStatusPanel.style.display = 'block';

    ui.downloadStatusList.innerHTML = jobs.map(job => {
        const statusText = {
            'pending': 'Pending...',
            'downloading': 'Downloading...',
            'processing': 'Processing...',
            'complete': 'Complete',
            'error': 'Error'
        }[job.status] || job.status;

        return `
            <div class="download-status-item">
                <div class="download-info">
                    <strong>${escapeHtml(job.title || job.book_slug)}</strong>
                    <span class="status-text">${statusText}</span>
                </div>
                <div class="download-progress-bar">
                    <div class="download-progress-fill" style="width: ${job.progress || 0}%"></div>
                </div>
                <span class="progress-text">${job.progress || 0}%</span>
            </div>
        `;
    }).join('');
}

function showNotification(message, type = 'info') {
    /**
     * Show temporary notification to user
     */
    console.log(`[Notification] ${message}`);

    // Simple alert for now (could be replaced with toast notification)
    // Just log to console for non-intrusive feedback
    if (type === 'error') {
        console.error(message);
    } else {
        console.info(message);
    }
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

    const success = await API.savePlaybackPosition(
        state.currentBook.book_id,
        state.currentVariant.variant_id,
        ui.audio.currentTime,
        ui.audio.playbackRate,
        state.currentFileIndex
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

    // Text sync modal
    ui.textSyncBtn.addEventListener('click', toggleTextSync);
    ui.closeTextSyncBtn.addEventListener('click', closeTextSyncPanel);
    ui.textSyncBackdrop.addEventListener('click', closeTextSyncPanel);

    // AI Chat modal
    ui.aiAssistantBtn.addEventListener('click', toggleAIChat);
    ui.closeChatBtn.addEventListener('click', closeAIChatPanel);
    ui.aiChatBackdrop.addEventListener('click', closeAIChatPanel);

    // Unified search
    ui.unifiedSearchInput.addEventListener('input', handleUnifiedSearch);
    ui.tabLibrary.addEventListener('click', () => switchTab('library'));
    ui.tabStore.addEventListener('click', () => switchTab('store'));

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
        ui.downloadStatusPanel.style.display = 'none';
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
        ui.playPauseBtn.textContent = '⏸️';
        startAutoSave();
        updateMediaSession();
    });

    ui.audio.addEventListener('pause', () => {
        state.isPlaying = false;
        ui.playPauseBtn.textContent = '▶️';
        savePlaybackState();
        stopAutoSave();
    });

    ui.audio.addEventListener('timeupdate', () => {
        updateProgress();
        detectCurrentChapter();
        checkEndOfChapterTimer();
        updateTextHighlight();

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
// Initialization
// ============================================================================

async function init() {
    // Get or create device ID
    state.deviceId = getOrCreateDeviceId();
    console.log('Device ID:', state.deviceId);

    // Setup event listeners
    setupEventListeners();

    // Load library
    await loadLibrary();

    // Initialize Gutenberg browser (if available)
    await initGutenberg();

    console.log('Audiobook player initialized');
}

// Start the app
init();
