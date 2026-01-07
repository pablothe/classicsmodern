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
    saveInterval: null
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

    async savePlaybackPosition(bookId, variantId, position, speed, fileIndex) {
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
                    file_index: fileIndex
                })
            }
        );
        return response.ok;
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

    // Variant selection
    variantBackBtn: document.getElementById('variant-back-btn'),
    variantBookTitle: document.getElementById('variant-book-title'),
    variantTitle: document.getElementById('variant-title'),
    variantAuthor: document.getElementById('variant-author'),
    variantList: document.getElementById('variant-list'),

    // Player
    backBtn: document.getElementById('back-btn'),
    currentBookTitle: document.getElementById('current-book-title'),
    playerBookTitle: document.getElementById('player-book-title'),
    fileInfo: document.getElementById('file-info'),

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
    duration: document.getElementById('duration'),

    // Speed
    speedSlider: document.getElementById('speed-slider'),
    speedDisplay: document.getElementById('speed-display'),

    // Chapters
    chaptersSection: document.getElementById('chapters-section'),
    chaptersList: document.getElementById('chapters-list')
};

// ============================================================================
// Library Functions
// ============================================================================

async function loadLibrary() {
    try {
        state.books = await API.getBooks();
        renderLibrary();
    } catch (error) {
        console.error('Failed to load library:', error);
        ui.bookList.innerHTML = '<div class="error">Failed to load books. Please check server connection.</div>';
    }
}

function renderLibrary() {
    if (state.books.length === 0) {
        ui.bookList.innerHTML = '<div class="loading">No audiobooks found</div>';
        ui.bookCount.textContent = '0 books available';
        return;
    }

    ui.bookCount.textContent = `${state.books.length} book${state.books.length !== 1 ? 's' : ''} available`;

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

    ui.bookList.innerHTML = state.books.map((book, index) => {
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
        if (!variant) return;

        state.currentVariant = variant;
        state.currentFileIndex = 0;

        // Load saved position
        const savedPosition = await API.getPlaybackPosition(book.book_id, variantId);
        if (savedPosition) {
            state.currentFileIndex = savedPosition.file_index || 0;
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

    ui.currentBookTitle.textContent = book.title;
    ui.playerBookTitle.textContent = book.title;
    updateFileInfo();

    // Update book cover in player
    const bookCoverDiv = document.querySelector('.book-cover');
    if (book.has_cover && book.cover_image) {
        const coverURL = `${API.baseURL}/api/books/${book.book_id}/cover`;
        bookCoverDiv.innerHTML = `<img src="${coverURL}" alt="${book.title} cover" style="width: 100%; height: 100%; object-fit: cover; border-radius: 12px;" />`;
    } else {
        bookCoverDiv.textContent = '🎧';
    }

    // Render chapters if available
    if (book.has_chapters && book.chapters) {
        ui.chaptersSection.style.display = 'block';
        renderChapters();
    } else {
        ui.chaptersSection.style.display = 'none';
    }

    // Update navigation buttons
    updateNavigationButtons();
}

function updateFileInfo() {
    const variant = state.currentVariant;
    const current = state.currentFileIndex + 1;
    const total = variant.audio_files.length;
    ui.fileInfo.textContent = `File ${current} of ${total}`;
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

    ui.audio.src = audioURL;
    ui.audio.load();

    updateFileInfo();
    updateNavigationButtons();
}

function renderChapters() {
    const chapters = state.currentBook.chapters;

    ui.chaptersList.innerHTML = chapters.map((chapter, index) => `
        <div class="chapter-item" data-chapter-index="${index}">
            ${chapter.title || `Chapter ${chapter.number}`}
        </div>
    `).join('');

    // Add click handlers
    document.querySelectorAll('.chapter-item').forEach(item => {
        item.addEventListener('click', () => {
            const chapterIndex = parseInt(item.dataset.chapterIndex);
            console.log('Jump to chapter:', chapterIndex);
        });
    });
}

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
    ui.audio.currentTime = Math.max(0, ui.audio.currentTime - 15);
}

function forward() {
    ui.audio.currentTime = Math.min(ui.audio.duration, ui.audio.currentTime + 30);
}

function updateProgress() {
    if (ui.audio.duration) {
        const progress = (ui.audio.currentTime / ui.audio.duration) * 100;
        ui.progressBar.value = progress;

        ui.currentTime.textContent = formatTime(ui.audio.currentTime);
        ui.duration.textContent = formatTime(ui.audio.duration);
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

    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const speed = parseFloat(btn.dataset.speed);
            setSpeedPreset(speed);
        });
    });

    // Audio events
    ui.audio.addEventListener('play', () => {
        state.isPlaying = true;
        ui.playPauseBtn.textContent = '⏸️';
        startAutoSave();
    });

    ui.audio.addEventListener('pause', () => {
        state.isPlaying = false;
        ui.playPauseBtn.textContent = '▶️';
        savePlaybackState();
        stopAutoSave();
    });

    ui.audio.addEventListener('timeupdate', updateProgress);

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
        console.error('Audio error:', e);
        alert('Failed to load audio file');
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (ui.playerView.classList.contains('active')) {
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

    // Save state before page unload
    window.addEventListener('beforeunload', () => {
        if (state.currentBook && state.currentVariant) {
            savePlaybackState();
        }
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

    console.log('Audiobook player initialized');
}

// Start the app
init();
